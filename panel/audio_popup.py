"""Audio popup: volume, mute, and which device the sound comes out of.

The three things Windows puts behind the speaker icon. Anything beyond that —
per-application levels, input routing — is pavucontrol's job, and there is a
button for it at the bottom rather than a second, worse copy of it here.

Volume goes through wpctl, the same tool the bar's scroll-to-change already
uses, so the popup and the bar cannot drift apart. The device list comes from
`pactl -f json`, because wpctl's status output is a human-readable tree that
would have to be scraped.
"""

from __future__ import annotations

import json
import subprocess

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from popup import Popup, heading, launch  # noqa: E402

SINK = "@DEFAULT_AUDIO_SINK@"


def wpctl(*args: str) -> str:
    try:
        return subprocess.run(["wpctl", *args], capture_output=True,
                              text=True, check=False, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def get_volume() -> tuple[float, bool]:
    """Return (0.0-1.0, muted). wpctl prints e.g. 'Volume: 0.65 [MUTED]'."""
    out = wpctl("get-volume", SINK)
    if not out:
        return 0.0, False
    muted = "MUTED" in out
    for token in out.split():
        try:
            return float(token), muted
        except ValueError:
            continue
    return 0.0, muted


def list_sinks() -> tuple[list[dict], str]:
    """Return (sinks, name_of_default). Empty list if pactl is unavailable."""
    try:
        raw = subprocess.run(["pactl", "-f", "json", "list", "sinks"],
                             capture_output=True, text=True, check=False,
                             timeout=5).stdout
        sinks = json.loads(raw) if raw.strip() else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return [], ""

    try:
        default = subprocess.run(["pactl", "get-default-sink"],
                                 capture_output=True, text=True, check=False,
                                 timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        default = ""
    return sinks, default


class AudioPopup(Popup):
    name = "audio"
    width = 340

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        self._window = window
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        volume, muted = get_volume()

        box.append(heading("Output volume"))

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        self._mute = Gtk.ToggleButton()
        self._mute.set_icon_name("audio-volume-muted-symbolic" if muted
                                 else "audio-volume-high-symbolic")
        self._mute.set_active(muted)
        self._mute.add_css_class("popup-icon-button")
        self._mute.connect("toggled", self._on_mute)
        row.append(self._mute)

        self._scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL,
                                               0, 100, 1)
        self._scale.set_value(round(volume * 100))
        self._scale.set_hexpand(True)
        self._scale.set_draw_value(True)
        self._scale.set_value_pos(Gtk.PositionType.RIGHT)
        self._scale.add_css_class("popup-slider")
        self._scale.connect("value-changed", self._on_volume)
        row.append(self._scale)

        box.append(row)

        sinks, default = list_sinks()
        if len(sinks) > 1:
            box.append(Gtk.Separator())
            box.append(heading("Output device"))
            box.append(self._device_list(sinks, default))
        elif not sinks:
            box.append(self._note("No audio devices found"))

        box.append(Gtk.Separator())

        settings = Gtk.Button(label="Sound settings")
        settings.add_css_class("popup-action")
        settings.connect("clicked", lambda _b: launch(["pavucontrol"], window))
        box.append(settings)

        return box

    def _device_list(self, sinks: list[dict], default: str) -> Gtk.Widget:
        listbox = Gtk.ListBox()
        listbox.add_css_class("popup-list")
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        for sink in sinks:
            name = sink.get("name", "")
            label = (sink.get("description")
                     or sink.get("properties", {}).get("device.description")
                     or name)
            button = Gtk.Button(label=label)
            button.add_css_class("popup-row")
            if name == default:
                button.add_css_class("popup-row-active")
            button.connect("clicked", self._on_pick_sink, name)
            listbox.append(button)
        return listbox

    # -- actions -----------------------------------------------------------

    def _on_volume(self, scale: Gtk.Scale) -> None:
        # -l 1.0 caps at 100%: PipeWire happily goes past it, and software
        # amplification above 100% distorts on most hardware.
        wpctl("set-volume", "-l", "1.0", SINK, f"{scale.get_value() / 100:.2f}")

    def _on_mute(self, button: Gtk.ToggleButton) -> None:
        muted = button.get_active()
        wpctl("set-mute", SINK, "1" if muted else "0")
        button.set_icon_name("audio-volume-muted-symbolic" if muted
                             else "audio-volume-high-symbolic")

    def _on_pick_sink(self, _button: Gtk.Button, name: str) -> None:
        subprocess.run(["pactl", "set-default-sink", name], check=False)
        self._window.close()

    def _note(self, text: str) -> Gtk.Widget:
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("popup-note")
        label.set_wrap(True)
        return label
