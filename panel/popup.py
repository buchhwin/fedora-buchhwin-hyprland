"""Shared scaffolding for the bar's popups.

The three popups — calendar, audio, network — differ only in what they put
inside. Everything that makes them feel like part of the bar rather than three
stray windows lives here: where they appear, how they close, and how they are
toggled.

Why a resident process
----------------------
Starting a Python + GTK4 process per click costs about 1.1 seconds, measured:
Python 42 ms, GTK4 and libadwaita 518 ms, then layer-shell, CSS and the window
itself. No amount of tuning inside that gets near "instant", because none of it
is our code. So the process starts once with the session and the click only
shows a window that already exists.

Why gtk4-layer-shell and not a plain window
-------------------------------------------
A normal GTK window under Hyprland is just another window: it lands wherever
the layout puts it and shows up in the window list. A layer-shell surface can
be anchored under the bar, sits above tiled windows without joining them, and
can hand keyboard focus back on demand — which is what a panel popup has to do.

The typelib ships in Fedora's `gtk4-layer-shell` package, so no build step. It
must be loaded before libwayland, which the buchhwin-panel wrapper arranges
with LD_PRELOAD; without it every popup silently becomes an ordinary window.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

# Side margin matches the bar's own (waybar config.jsonc), so the popup's right
# edge lines up with the right edge of the bar rather than sitting proud of it.
BAR_MARGIN_SIDE = 12

# Vertical gap between the bar and the popup — and ONLY the gap. Waybar claims
# an exclusive zone, so layer-shell already starts measuring below the bar; a
# margin of bar-offset + bar-height + gap counts the bar twice and drops the
# popup half a bar-height too low. Measured: with 52 here the surface landed at
# y=98 instead of y=52.
POPUP_GAP = 6

RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
FIFO = RUNTIME / "buchhwin-panel.fifo"


def layer_shell():
    """Return the Gtk4LayerShell module, or None if it is not usable.

    Missing layer-shell is not fatal. The popup still opens as an ordinary
    window — worse, but usable — instead of a click doing nothing at all.
    """
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell

        return Gtk4LayerShell
    except (ValueError, ImportError):
        return None


class PanelWindow:
    """One popup: a window anchored under the bar, plus its click catcher.

    Built once and then shown and hidden. Subclasses implement `build()` and
    may implement `refresh()`, which runs every time the popup is shown so the
    contents are never stale.
    """

    name = "popup"
    width = 360

    def __init__(self, app: Gtk.Application) -> None:
        self.app = app
        self._shell = layer_shell()
        self._visible = False

        # The catcher is a full-screen, fully transparent surface UNDER the
        # popup whose only job is to notice a click elsewhere. It is the only
        # thing that works here: watching notify::is-active does not, because
        # with KeyboardMode.ON_DEMAND the surface often never becomes active,
        # so the signal never fires and clicking away does nothing.
        self.catcher = Gtk.ApplicationWindow(application=app)
        self.catcher.add_css_class("popup-catcher")
        filler = Gtk.Box()
        filler.set_hexpand(True)
        filler.set_vexpand(True)
        self.catcher.set_child(filler)
        if self._shell:
            self._shell.init_for_window(self.catcher)
            self._shell.set_layer(self.catcher, self._shell.Layer.TOP)
            for edge in (self._shell.Edge.TOP, self._shell.Edge.BOTTOM,
                         self._shell.Edge.LEFT, self._shell.Edge.RIGHT):
                self._shell.set_anchor(self.catcher, edge, True)
            # NONE: the catcher must never take the keyboard, or typing a Wi-Fi
            # password into the popup above it would go nowhere.
            self._shell.set_keyboard_mode(self.catcher, self._shell.KeyboardMode.NONE)
        # The gesture goes on the CHILD, not on the window. A controller on a
        # GtkApplicationWindow gets events only once something inside has taken
        # them, which for an empty catcher is never.
        click = Gtk.GestureClick()
        click.set_button(0)                 # any button, not just the left one
        click.connect("pressed", self._on_catcher_click)
        filler.add_controller(click)

        self.window = Gtk.ApplicationWindow(application=app)
        self.window.set_default_size(self.width, -1)
        self.window.add_css_class("buchhwin-popup")
        self.window.add_css_class(f"popup-{self.name}")
        if self._shell:
            self._shell.init_for_window(self.window)
            self._shell.set_layer(self.window, self._shell.Layer.TOP)
            self._shell.set_anchor(self.window, self._shell.Edge.TOP, True)
            self._shell.set_anchor(self.window, self._shell.Edge.RIGHT, True)
            self._shell.set_margin(self.window, self._shell.Edge.TOP, POPUP_GAP)
            self._shell.set_margin(self.window, self._shell.Edge.RIGHT, BAR_MARGIN_SIDE)
            # ON_DEMAND, not EXCLUSIVE: the network popup needs a password
            # field, but a popup that swallows every keystroke while it is
            # merely visible is a trap.
            self._shell.set_keyboard_mode(self.window, self._shell.KeyboardMode.ON_DEMAND)

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        body.add_css_class("popup-body")
        body.append(self.build(self.window))
        self.window.set_child(body)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key)
        self.window.add_controller(keys)

        # Closing must go through hide(), or the catcher would be left behind:
        # an invisible full-screen surface swallowing every click on the
        # desktop is the worst possible failure for this particular trick.
        self.window.connect("close-request", lambda *_a: (self.hide(), True)[1])

    # -- visibility --------------------------------------------------------

    def _on_catcher_click(self, *_args) -> None:
        if os.environ.get("BUCHHWIN_PANEL_DEBUG"):
            print(f"{self.name}: catcher clicked", file=sys.stderr, flush=True)
        self.hide()

    def _on_key(self, _c, keyval, _code, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False

    def toggle(self) -> None:
        self.hide() if self._visible else self.show()

    def show(self) -> None:
        # Refresh on the way up rather than on a timer: a popup nobody is
        # looking at should cost nothing at all.
        try:
            self.refresh()
        except Exception as exc:                          # noqa: BLE001
            print(f"{self.name}: refresh failed: {exc}", file=sys.stderr)
        self.catcher.present()
        self.window.present()
        self._visible = True

    def hide(self) -> None:
        self.window.set_visible(False)
        self.catcher.set_visible(False)
        self._visible = False

    # -- subclass hooks ----------------------------------------------------

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        raise NotImplementedError

    def refresh(self) -> None:
        """Called every time the popup is shown. Override where it matters."""


def load_css() -> None:
    """Two providers, colours first.

    They live in different trees — the palette is generated into the config
    dir, the layout ships in the repo — so neither can @import the other by
    relative path. GTK shares @define-color across providers on a display, so
    style.css can use the names colors.css defines.
    """
    display = Gdk.Display.get_default()
    if display is None:
        return
    config_dir = Path(GLib.get_user_config_dir())
    for path in (config_dir / "buchhwin-panel" / "colors.css",
                 Path(__file__).with_name("style.css")):
        if not path.exists():
            continue
        provider = Gtk.CssProvider()
        try:
            provider.load_from_path(str(path))
        except GLib.Error as exc:
            print(f"stylesheet {path}: {exc}", file=sys.stderr)
            continue
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )


def launch(cmd: list[str], window: PanelWindow | None = None) -> None:
    """Start an application and put the popup away.

    Detached on purpose: the popup is only hidden afterwards, and the child
    should not be tied to it either way.
    """
    try:
        Gio.Subprocess.new(cmd, Gio.SubprocessFlags.NONE)
    except GLib.Error as exc:
        print(f"could not start {cmd[0]}: {exc}", file=sys.stderr)
    if window is not None:
        window.hide()


def heading(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    label.add_css_class("popup-heading")
    return label


def note(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    label.add_css_class("popup-note")
    label.set_wrap(True)
    return label
