#!/usr/bin/env python3
"""The on-screen display — the bar that appears when you change the volume.

Every desktop has one, and its absence is felt immediately: pressing a volume
key and seeing nothing means checking the bar to find out whether the key even
works.

Different from the other popups in two ways, and both matter:

  * it is not anchored to the bar. It sits at the bottom centre of the screen,
    over everything, because it is feedback rather than a menu;

  * it disappears by itself. There is no click-away catcher — a catcher would
    swallow the click you were about to make elsewhere, and this is not
    something you interact with. It closes on a timer, and the timer restarts
    on each new value so holding a volume key does not make it flicker.
"""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk
from popup import PanelWindow

# Long enough to read, short enough not to sit in the way of what you are doing.
HIDE_AFTER_MS = 1400


def run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              check=False, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def volume() -> tuple[int, bool]:
    out = run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
    muted = "MUTED" in out
    try:
        return round(float(out.split()[1]) * 100), muted
    except (IndexError, ValueError):
        return 0, muted


def microphone() -> tuple[int, bool]:
    out = run("wpctl", "get-volume", "@DEFAULT_AUDIO_SOURCE@")
    muted = "MUTED" in out
    try:
        return round(float(out.split()[1]) * 100), muted
    except (IndexError, ValueError):
        return 0, muted


def brightness() -> int | None:
    out = run("brightnessctl", "-m", "-c", "backlight", "info")
    parts = out.split(",")
    if len(parts) < 5 or parts[1] != "backlight":
        return None
    try:
        return int(parts[3].rstrip("%"))
    except ValueError:
        return None


VOLUME_ICONS = ("audio-volume-muted-symbolic", "audio-volume-low-symbolic",
                "audio-volume-medium-symbolic", "audio-volume-high-symbolic")


class OsdPopup(PanelWindow):
    name = "osd"
    width = 300

    def __init__(self, app) -> None:
        super().__init__(app)
        self._timeout = 0
        if self._shell:
            # Bottom centre, over everything, and no keyboard: this must never
            # take focus away from what you are typing into.
            self._shell.set_layer(self.window, self._shell.Layer.OVERLAY)
            for edge in (self._shell.Edge.TOP, self._shell.Edge.LEFT,
                         self._shell.Edge.RIGHT):
                self._shell.set_anchor(self.window, edge, False)
            self._shell.set_anchor(self.window, self._shell.Edge.BOTTOM, True)
            self._shell.set_margin(self.window, self._shell.Edge.BOTTOM, 120)
            self._shell.set_keyboard_mode(self.window,
                                          self._shell.KeyboardMode.NONE)

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        window.add_css_class("osd")
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._icon = Gtk.Image.new_from_icon_name(VOLUME_ICONS[-1])
        self._icon.set_pixel_size(24)
        box.append(self._icon)

        self._bar = Gtk.ProgressBar()
        self._bar.add_css_class("osd-bar")
        self._bar.set_hexpand(True)
        self._bar.set_valign(Gtk.Align.CENTER)
        box.append(self._bar)

        self._value = Gtk.Label(label="")
        self._value.add_css_class("osd-value")
        box.append(self._value)
        return box

    def show_for(self, kind: str) -> None:
        """Show the value of one thing, and start the countdown."""
        if kind == "brightness":
            level = brightness()
            if level is None:
                return                  # no backlight: nothing to show
            icon, percent, muted = "display-brightness-symbolic", level, False
        elif kind == "microphone":
            percent, muted = microphone()
            icon = ("microphone-sensitivity-muted-symbolic" if muted
                    else "audio-input-microphone-symbolic")
        else:
            percent, muted = volume()
            icon = (VOLUME_ICONS[0] if muted or percent == 0 else
                    VOLUME_ICONS[min(3, percent // 34 + 1)])

        self._icon.set_from_icon_name(icon)
        self._bar.set_fraction(min(1.0, percent / 100))
        self._value.set_text("muted" if muted else f"{percent}%")

        # The catcher stays down: this is feedback, not a menu, and a
        # full-screen catcher would eat the next click on the desktop.
        self.window.present()
        self._visible = True

        if self._timeout:
            GLib.source_remove(self._timeout)
        self._timeout = GLib.timeout_add(HIDE_AFTER_MS, self._auto_hide)

    def _auto_hide(self) -> bool:
        self._timeout = 0
        self.window.set_visible(False)
        self._visible = False
        return False

    # Shown by show_for(), never by the generic toggle: a media key that toggled
    # this off again on the second press would be maddening.
    def show(self) -> None:
        self.show_for("volume")

    def toggle(self) -> None:
        self.show_for("volume")
