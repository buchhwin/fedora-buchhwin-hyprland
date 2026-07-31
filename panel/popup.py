"""Shared scaffolding for the bar's popups.

The three popups — calendar, audio, network — differ only in what they put
inside. Everything that makes them feel like part of the bar rather than three
stray windows lives here: where they appear, how they close, and the fact that
clicking the same bar module twice closes the popup instead of opening a second
one.

Why gtk4-layer-shell and not a plain window
-------------------------------------------
A normal GTK window under Hyprland is just another window: it lands wherever
the layout puts it, keeps focus until something takes it away, and shows up in
the window list. A layer-shell surface can be anchored to the top-right corner
of the screen, sits above tiled windows without joining them, and can hand
keyboard focus back on demand — which is what a panel popup has to do.

The typelib ships in Fedora's `gtk4-layer-shell` package
(`/usr/lib64/girepository-1.0/Gtk4LayerShell-1.0.typelib`), so no build step.
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

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


def _layer_shell():
    """Return the Gtk4LayerShell module, or None if it is not installed.

    Missing layer-shell is not fatal. The popup still opens as an ordinary
    window — worse, but usable — instead of the user clicking the clock and
    getting nothing at all.
    """
    try:
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk4LayerShell

        return Gtk4LayerShell
    except (ValueError, ImportError):
        return None


class Popup(Adw.Application):
    """A single-instance popup anchored under the bar.

    Subclasses implement `build()` and return the widget that goes inside.
    """

    #: Overridden by subclasses; also the name of the pidfile and the CSS class.
    name = "popup"
    #: Width in pixels. Height follows the content.
    width = 360

    def __init__(self) -> None:
        super().__init__(
            application_id=f"de.buchhwin.panel.{self.name}",
            flags=Gio.ApplicationFlags.NON_UNIQUE,
        )
        self.connect("activate", self._on_activate)

    # -- toggling ----------------------------------------------------------
    #
    # Clicking the clock a second time must close the popup. Waybar has no idea
    # whether the popup is open, so it just runs the same command again — which
    # means the *second* process is responsible for noticing the first one and
    # asking it to go away.

    @classmethod
    def _pidfile(cls) -> Path:
        return RUNTIME / f"buchhwin-panel-{cls.name}.pid"

    @classmethod
    def toggle_or_run(cls) -> int:
        pidfile = cls._pidfile()
        try:
            pid = int(pidfile.read_text().strip())
        except (OSError, ValueError):
            pid = 0

        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
                # It was open; closing it is the whole job.
                return 0
            except ProcessLookupError:
                # Stale file from a popup that died without cleaning up.
                pidfile.unlink(missing_ok=True)
            except PermissionError:
                # Someone else's process reused the pid. Do not signal it.
                pidfile.unlink(missing_ok=True)

        pidfile.write_text(str(os.getpid()))
        try:
            return cls().run([])
        finally:
            # Only remove the file if it is still ours; a newer popup may have
            # claimed it while we were shutting down.
            try:
                if pidfile.read_text().strip() == str(os.getpid()):
                    pidfile.unlink(missing_ok=True)
            except OSError:
                pass

    # -- window ------------------------------------------------------------

    def _on_activate(self, _app) -> None:
        window = Gtk.ApplicationWindow(application=self)
        window.set_default_size(self.width, -1)
        window.add_css_class("buchhwin-popup")
        window.add_css_class(f"popup-{self.name}")

        shell = _layer_shell()
        if shell:
            shell.init_for_window(window)
            shell.set_layer(window, shell.Layer.TOP)
            shell.set_anchor(window, shell.Edge.TOP, True)
            shell.set_anchor(window, shell.Edge.RIGHT, True)
            shell.set_margin(window, shell.Edge.TOP, POPUP_GAP)
            shell.set_margin(window, shell.Edge.RIGHT, BAR_MARGIN_SIDE)
            # ON_DEMAND, not EXCLUSIVE: the network popup needs a password
            # field, but a popup that swallows every keystroke while it is
            # merely visible is a trap.
            shell.set_keyboard_mode(window, shell.KeyboardMode.ON_DEMAND)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.add_css_class("popup-body")
        content.append(self.build(window))
        window.set_child(content)

        self._close_on_escape(window)
        self._close_on_focus_loss(window)
        # SIGTERM is how the second invocation asks us to close.
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM,
                             lambda: (window.close(), False)[1])

        self._load_css()
        window.present()

    def _close_on_escape(self, window: Gtk.Window) -> None:
        keys = Gtk.EventControllerKey()

        def on_key(_c, keyval, _code, _state):
            if keyval == Gdk.KEY_Escape:
                window.close()
                return True
            return False

        keys.connect("key-pressed", on_key)
        window.add_controller(keys)

    def _close_on_focus_loss(self, window: Gtk.Window) -> None:
        # Clicking anywhere else dismisses it. Without this the popup is just a
        # window you have to go and close, which is not what a panel popup is.
        def on_active(_w, _p):
            if not window.is_active():
                window.close()

        window.connect("notify::is-active", on_active)

    def _load_css(self) -> None:
        # Two providers, colours first. They live in different trees — the
        # palette is generated into the config dir, the layout ships in the
        # repo — so neither can @import the other by relative path. GTK shares
        # @define-color across providers on a display, so style.css can use the
        # names defined by colors.css.
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

    # -- subclass hook -----------------------------------------------------

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        raise NotImplementedError


def launch(cmd: list[str], window: Gtk.Window | None = None) -> None:
    """Start an application and close the popup.

    Detached on purpose: the popup exits immediately afterwards, and a child
    process in its own session survives that.
    """
    try:
        Gio.Subprocess.new(cmd, Gio.SubprocessFlags.NONE)
    except GLib.Error as exc:
        print(f"could not start {cmd[0]}: {exc}", file=sys.stderr)
    if window is not None:
        window.close()


def heading(text: str) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0)
    label.add_css_class("popup-heading")
    return label
