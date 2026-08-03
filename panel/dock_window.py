"""The dock: pinned applications and running windows as ONE row of icons.

Why this is not a waybar config any more
----------------------------------------
It was, and it could not become what a dock has to be. waybar's `wlr/taskbar`
lists running windows and a `custom`/`image` module launches a pinned one, and
the two know nothing about each other — so a pinned Brave that is running showed
up twice, once as a launcher and once as a window. There is no right-click menu
in waybar at all, so pinning from the dock was impossible, and the two module
groups carry separate backgrounds, which is why a newly opened window's icon
appeared floating outside the dock's rounded island.

None of that is a bug in waybar. A dock is simply an application, and this is
it: one icon per APPLICATION, whether it is pinned, running, or both.

  * one icon per application, with dots underneath for how many windows it has
  * left click focuses the most recently used window, or launches it
  * right click pins, unpins, closes everything, or picks one window by title
  * windows on other workspaces are listed too — a window you cannot see is
    exactly the one you need the dock for

It lives in the panel daemon rather than in a process of its own for the reason
that daemon exists at all: GTK4 and libadwaita cost about half a second to start,
and paying that once per session is the difference between a dock that is there
at login and one that appears a moment later.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
# Gdk and GdkPixbuf need saying too, or PyGObject warns on every start about
# importing them without a version — a line in the journal for every login.
gi.require_version("Gdk", "4.0")
gi.require_version("GdkPixbuf", "2.0")

import icons
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk
from popup import layer_shell

REPO = Path(__file__).resolve().parent.parent
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "buchhwin"

DEFAULTS = {
    "enabled": True,
    "position": "bottom",
    "icon_size": 32,
    "margin": 8,
    "autohide": False,
    "pinned": [],
}


# --------------------------------------------------------------------------
# Talking to Hyprland
# --------------------------------------------------------------------------

def _hypr_env() -> dict:
    """hyprctl does not find the running instance by itself; fill it in.

    Without HYPRLAND_INSTANCE_SIGNATURE hyprctl answers "is hyprland running?"
    and every query comes back empty — which a dock would render as "nothing is
    open". Same lookup scripts/minimize.py does for the event socket.
    """
    env = dict(os.environ)
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return env
    runtime = Path(env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    try:
        sockets = sorted((runtime / "hypr").glob("*/.socket.sock"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        sockets = []
    if sockets:
        env["HYPRLAND_INSTANCE_SIGNATURE"] = sockets[0].parent.name
    return env


def _clients() -> list[dict]:
    try:
        out = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True,
                             text=True, check=False, timeout=5,
                             env=_hypr_env()).stdout
        return json.loads(out) if out.strip() else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def _dispatch(lua: str) -> None:
    """⚠️ Lua, not the old word syntax.

    `hyprctl dispatch focuswindow address:0x...` is a Lua syntax error under the
    Lua config provider, and hyprctl prints it to stdout and exits 0 — so it
    fails silently and forever. tests/test-dispatch.sh keeps that from coming
    back.
    """
    try:
        subprocess.run(["hyprctl", "dispatch", lua], capture_output=True,
                       text=True, check=False, timeout=5, env=_hypr_env())
    except (OSError, subprocess.TimeoutExpired):
        pass


def _event_socket() -> Path | None:
    env = _hypr_env()
    signature = env.get("HYPRLAND_INSTANCE_SIGNATURE")
    runtime = Path(env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    if signature:
        candidate = runtime / "hypr" / signature / ".socket2.sock"
        if candidate.exists():
            return candidate
    try:
        found = sorted((runtime / "hypr").glob("*/.socket2.sock"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return None
    return found[0] if found else None


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

def _settings() -> dict:
    try:
        out = subprocess.run([sys.executable, str(REPO / "scripts" / "settings.py"), "dump"],
                             capture_output=True, text=True, check=False,
                             timeout=15).stdout
        return (json.loads(out) if out.strip() else {}).get("dock") or {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, AttributeError):
        return {}


def _pinned(dock: dict) -> list[str]:
    value = dock.get("pinned")
    if isinstance(value, dict):        # Lua tables arrive as {"1": "kitty", ...}
        value = [value[k] for k in sorted(value)]
    if not isinstance(value, list):
        return []
    return [str(v) for v in value if str(v).strip()]


def _write_pinned(apps: list[str]) -> None:
    """Write the pin list back through settings.py.

    Through the script rather than by editing settings.lua here: it is real Lua
    and is read back through the lua interpreter, so a home-grown writer would
    be wrong the first time somebody puts a comment in an unusual place.
    """
    value = "[" + ",".join(json.dumps(a) for a in apps) + "]"
    try:
        subprocess.run([sys.executable, str(REPO / "scripts" / "settings.py"),
                        "set", f"dock.pinned={value}"],
                       capture_output=True, text=True, check=False, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _icon_theme() -> str:
    try:
        state = json.loads((STATE / "theme.json").read_text())
        palette = json.loads(
            (REPO / "theme" / "palettes" / f"{state['flavour']}.json").read_text())
        return "Papirus-Dark" if palette.get("dark", True) else "Papirus-Light"
    except (OSError, KeyError, json.JSONDecodeError):
        return "Papirus-Dark"


# --------------------------------------------------------------------------
# The model: one entry per application
# --------------------------------------------------------------------------

class Entry:
    """One application in the dock, with whatever windows it has."""

    def __init__(self, app: str, pinned: bool) -> None:
        self.app = app
        self.pinned = pinned
        self.windows: list[dict] = []

    @property
    def running(self) -> bool:
        return bool(self.windows)

    @property
    def label(self) -> str:
        return icons.display_name(self.app)


def build_entries(dock: dict) -> list[Entry]:
    """Pinned applications and running windows, merged.

    The merge is the whole point of this file. A window is attached to a pinned
    entry when its class matches; anything left over becomes an entry of its
    own, because a window the dock cannot name is still a window the user has
    open — dropping it silently would be worse than showing it with a generic
    icon.
    """
    pinned = _pinned(dock)
    entries = [Entry(app, pinned=True) for app in pinned]
    by_app = {e.app: e for e in entries}

    for window in _clients():
        if not window.get("mapped", True):
            continue
        # Both are checked: `class` is what the window says now, `initialClass`
        # what it said when it opened, and applications that rename themselves
        # at runtime only match on the second.
        found = (icons.match_app(window.get("initialClass", ""), pinned)
                 or icons.match_app(window.get("class", ""), pinned))
        if found is None:
            key = icons.normalise(window.get("initialClass") or window.get("class") or "?")
            entry = by_app.get(key)
            if entry is None:
                entry = Entry(key, pinned=False)
                by_app[key] = entry
                entries.append(entry)
        else:
            entry = by_app[found]
        entry.windows.append(window)

    return entries


# --------------------------------------------------------------------------
# The window
# --------------------------------------------------------------------------

class Dock:
    """A layer-shell surface at the bottom edge, rebuilt when anything changes."""

    def __init__(self, app: Gtk.Application) -> None:
        self.app = app
        self._shell = layer_shell()
        self._dock = _settings()
        self._theme = _icon_theme()
        self._menu: Gtk.Popover | None = None

        self.window = Gtk.ApplicationWindow(application=app)
        self.window.add_css_class("buchhwin-dock")
        if self._shell:
            edge = self._edge()
            self._shell.init_for_window(self.window)
            self._shell.set_layer(self.window, self._shell.Layer.TOP)
            self._shell.set_anchor(self.window, edge, True)
            self._shell.set_margin(self.window, edge,
                                   int(self._dock.get("margin", DEFAULTS["margin"])))
            # NONE: a dock that takes the keyboard would swallow every shortcut
            # while the pointer is anywhere near the bottom of the screen.
            self._shell.set_keyboard_mode(self.window, self._shell.KeyboardMode.NONE)
            # An exclusive zone would reserve space and shrink every window by
            # the dock's height. Deliberately not taken: this dock overlaps, the
            # same choice the old one made through `"exclusive": false`.
            self._shell.set_exclusive_zone(self.window, 0)

        self.row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.row.add_css_class("dock-row")
        self.window.set_child(self.row)

        self.refresh()
        self._watch()

    def _edge(self):
        position = str(self._dock.get("position", DEFAULTS["position"]))
        return {
            "bottom": self._shell.Edge.BOTTOM,
            "top": self._shell.Edge.TOP,
            "left": self._shell.Edge.LEFT,
            "right": self._shell.Edge.RIGHT,
        }.get(position, self._shell.Edge.BOTTOM)

    # -- drawing ----------------------------------------------------------

    def refresh(self) -> None:
        self._dock = _settings()
        if not self._dock.get("enabled", DEFAULTS["enabled"]):
            self.window.set_visible(False)
            return

        while (child := self.row.get_first_child()) is not None:
            self.row.remove(child)

        size = int(self._dock.get("icon_size", DEFAULTS["icon_size"]))
        entries = build_entries(self._dock)
        for entry in entries:
            self.row.append(self._button(entry, size))

        # An empty dock is a bar of nothing hovering over the wallpaper.
        self.window.set_visible(bool(entries))

    def _button(self, entry: Entry, size: int) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.add_css_class("dock-item")
        if entry.running:
            box.add_css_class("running")
        if any(w.get("focusHistoryID") == 0 for w in entry.windows):
            box.add_css_class("active")

        image = Gtk.Image()
        path = icons.icon_path(entry.app, self._theme)
        if path:
            # Loaded at a fixed size rather than handed to set_from_file: GTK
            # would otherwise scale an SVG to its natural size, which for
            # Papirus is whatever the file happens to say.
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
                image.set_from_paintable(Gdk.Texture.new_for_pixbuf(pixbuf))
            except GLib.Error:
                image.set_from_icon_name("application-x-executable")
        else:
            image.set_from_icon_name("application-x-executable")
        image.set_pixel_size(size)
        box.append(image)

        # The running indicator: one dot per window, up to three, so a dozen
        # terminals do not turn into a dozen dots.
        dots = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        dots.add_css_class("dock-dots")
        dots.set_halign(Gtk.Align.CENTER)
        for _ in range(min(len(entry.windows), 3)):
            dot = Gtk.Box()
            dot.add_css_class("dock-dot")
            dots.append(dot)
        box.append(dots)

        button = Gtk.Button()
        button.set_child(box)
        button.add_css_class("dock-button")
        button.set_has_frame(False)
        button.set_tooltip_text(self._tooltip(entry))
        button.connect("clicked", lambda _b, e=entry: self._activate(e))

        right = Gtk.GestureClick()
        right.set_button(3)
        right.connect("pressed", lambda *_a, e=entry, b=button: self._menu_for(e, b))
        button.add_controller(right)

        middle = Gtk.GestureClick()
        middle.set_button(2)
        middle.connect("pressed", lambda *_a, e=entry: self._launch(e))
        button.add_controller(middle)
        return button

    def _tooltip(self, entry: Entry) -> str:
        if not entry.running:
            return entry.label
        if len(entry.windows) == 1:
            return f"{entry.label} — {entry.windows[0].get('title', '')}".strip(" —")
        return f"{entry.label} ({len(entry.windows)})"

    # -- actions ----------------------------------------------------------

    def _activate(self, entry: Entry) -> None:
        if not entry.running:
            self._launch(entry)
            return
        # focusHistoryID 0 is the current window, 1 the one before it. Picking
        # the smallest that is not already focused makes a second click on the
        # same icon go somewhere rather than nowhere.
        windows = sorted(entry.windows, key=lambda w: w.get("focusHistoryID", 999))
        target = windows[0]
        if target.get("focusHistoryID") == 0 and len(windows) > 1:
            target = windows[1]
        self._focus(target)

    def _focus(self, window: dict) -> None:
        address = window.get("address", "")
        if not address:
            return
        _dispatch(f'hl.dsp.focus({{ window = "address:{address}" }})')

    def _launch(self, entry: Entry) -> None:
        try:
            Gio.Subprocess.new(["gtk-launch", entry.app], Gio.SubprocessFlags.NONE)
        except GLib.Error as exc:
            print(f"dock: could not start {entry.app}: {exc}", file=sys.stderr)

    def _menu_for(self, entry: Entry, button: Gtk.Button) -> None:
        menu = Gio.Menu()

        if len(entry.windows) > 1:
            windows = Gio.Menu()
            for index, window in enumerate(entry.windows):
                title = (window.get("title") or entry.label)[:60]
                windows.append(title, f"dock.focus{index}")
            menu.append_section(None, windows)

        actions = Gio.Menu()
        actions.append(_("Unpin") if entry.pinned else _("Pin to dock"), "dock.pin")
        if entry.running:
            actions.append(_("Close all windows"), "dock.close")
        menu.append_section(None, actions)

        group = Gio.SimpleActionGroup()
        pin = Gio.SimpleAction.new("pin", None)
        pin.connect("activate", lambda *_a, e=entry: self._toggle_pin(e))
        group.add_action(pin)
        close = Gio.SimpleAction.new("close", None)
        close.connect("activate", lambda *_a, e=entry: self._close_all(e))
        group.add_action(close)
        for index, window in enumerate(entry.windows):
            action = Gio.SimpleAction.new(f"focus{index}", None)
            action.connect("activate", lambda *_a, w=window: self._focus(w))
            group.add_action(action)

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(button)
        popover.insert_action_group("dock", group)
        popover.set_autohide(True)
        # Kept on the instance: a popover that is only a local goes away with
        # the function and never appears.
        self._menu = popover
        popover.popup()

    def _toggle_pin(self, entry: Entry) -> None:
        pinned = _pinned(self._dock)
        if entry.pinned:
            pinned = [a for a in pinned if a != entry.app]
        else:
            pinned.append(entry.app)
        _write_pinned(pinned)
        GLib.idle_add(lambda: (self.refresh(), False)[1])

    def _close_all(self, entry: Entry) -> None:
        for window in entry.windows:
            address = window.get("address", "")
            if address:
                _dispatch(f'hl.dsp.window.close({{ window = "address:{address}" }})')
        GLib.timeout_add(300, lambda: (self.refresh(), False)[1])

    # -- staying up to date -----------------------------------------------

    def _watch(self) -> None:
        """Redraw when Hyprland says something changed.

        A plain reader thread rather than GLib.io_add_watch: an IOChannel cannot
        do read_line() unbuffered, and this socket is a stream of lines that
        matter the moment they arrive. The panel daemon learned that the hard
        way with its FIFO.
        """
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        path = _event_socket()
        if path is None:
            print("dock: no Hyprland event socket, the dock will not update",
                  file=sys.stderr)
            return
        # ⚠️ `minimized>>`, with the d. "minimized>>…".startswith("minimize>>")
        # is false, and that cost an hour once already.
        interesting = ("openwindow>>", "closewindow>>", "activewindow>>",
                       "movewindow>>", "workspace>>", "minimized>>",
                       "windowtitle>>", "openlayer>>")
        try:
            import socket as socketlib
            sock = socketlib.socket(socketlib.AF_UNIX, socketlib.SOCK_STREAM)
            sock.connect(str(path))
            with sock.makefile("r", buffering=1) as stream:
                for line in stream:
                    if line.startswith(interesting):
                        GLib.idle_add(self._debounced)
        except OSError as exc:
            print(f"dock: event socket closed: {exc}", file=sys.stderr)

    def _debounced(self) -> bool:
        """Coalesce a burst into one redraw.

        Opening a window emits several events within a few milliseconds, and
        rebuilding the row for each of them is both wasteful and visibly jumpy.
        """
        if getattr(self, "_pending", False):
            return False
        self._pending = True

        def go() -> bool:
            self._pending = False
            self.refresh()
            return False

        GLib.timeout_add(80, go)
        return False
