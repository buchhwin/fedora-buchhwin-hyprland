"""Audio popup: output, input, and the volume of each running program.

Everything you reach for day to day, without leaving the desktop's own look.
The previous version sent you to pavucontrol for anything beyond the master
slider, and that was the complaint: a differently-styled window opening out of
a panel popup reads as a seam in the desktop rather than a feature of it.

pavucontrol is still one click away at the bottom, for channel maps and card
profiles — things that genuinely do not belong in a popup.

Volume goes through wpctl, the same tool the bar's scroll-to-change uses, so
the popup and the bar cannot drift apart. Everything that needs a list comes
from `pactl -f json`, because wpctl's status output is a human-readable tree
that would have to be scraped.
"""

from __future__ import annotations

import json
import subprocess

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk
from popup import PanelWindow, heading, launch

SINK = "@DEFAULT_AUDIO_SINK@"


def wpctl(*args: str) -> str:
    try:
        return subprocess.run(["wpctl", *args], capture_output=True,
                              text=True, check=False, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def get_volume(target: str = SINK) -> tuple[float, bool]:
    """Return (0.0-1.0, muted). wpctl prints e.g. 'Volume: 0.65 [MUTED]'."""
    out = wpctl("get-volume", target)
    if not out:
        return 0.0, False
    muted = "MUTED" in out
    for token in out.split():
        try:
            return float(token), muted
        except ValueError:
            continue
    return 0.0, muted


SOURCE = "@DEFAULT_AUDIO_SOURCE@"


def pactl_json(*args: str):
    try:
        raw = subprocess.run(["pactl", "-f", "json", *args], capture_output=True,
                             text=True, check=False, timeout=5).stdout
        return json.loads(raw) if raw.strip() else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def pactl_plain(*args: str) -> str:
    try:
        return subprocess.run(["pactl", *args], capture_output=True, text=True,
                              check=False, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def list_devices(kind: str) -> tuple[list[dict], str]:
    """Return (devices, name_of_default) for "sinks" or "sources"."""
    devices = pactl_json("list", kind)
    default = pactl_plain("get-default-sink" if kind == "sinks"
                          else "get-default-source")

    if kind == "sources":
        # Every sink has a .monitor source that records what is being played.
        # Useful for screen recording, meaningless in a list of microphones.
        devices = [d for d in devices
                   if d.get("monitor_source") is None
                   and ".monitor" not in d.get("name", "")]
    return devices, default


def device_label(device: dict) -> str:
    return (device.get("description")
            or device.get("properties", {}).get("device.description")
            or device.get("name", "?"))


def streams() -> list[dict]:
    """One entry per program currently playing something.

    This is the part people opened pavucontrol for: turning down one
    application without touching everything else.
    """
    out = []
    for s in pactl_json("list", "sink-inputs"):
        props = s.get("properties", {})
        name = (props.get("application.name")
                or props.get("media.name")
                or f"stream {s.get('index')}")
        volume = s.get("volume", {})
        # volume is a dict of channels; they are almost always in step, so the
        # first one is the honest single number to show.
        percent = 0
        for channel in volume.values():
            raw = str(channel.get("value_percent", "0%")).rstrip("%")
            try:
                percent = int(raw)
            except ValueError:
                percent = 0
            break
        out.append({"index": s.get("index"), "name": name,
                    "volume": percent, "muted": bool(s.get("mute"))})
    return out


class AudioPopup(PanelWindow):
    name = "audio"
    width = 340

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        # A container that refresh() refills. The popup is built once and lives
        # for the whole session, so anything read here would be frozen at login
        # time — the volume would be whatever it was when you logged in.
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._populate()
        return self._box

    def refresh(self) -> None:
        self._populate()

    def _populate(self) -> None:
        box = self._box
        while (child := box.get_first_child()) is not None:
            box.remove(child)

        # --- output ---------------------------------------------------------
        box.append(heading("Output"))
        volume, muted = get_volume(SINK)
        box.append(self._volume_row(volume, muted, SINK))

        sinks, default_sink = list_devices("sinks")
        if len(sinks) > 1:
            box.append(self._device_list(sinks, default_sink, "set-default-sink"))

        # --- input ----------------------------------------------------------
        sources, default_source = list_devices("sources")
        if sources:
            box.append(Gtk.Separator())
            box.append(heading("Microphone"))
            in_volume, in_muted = get_volume(SOURCE)
            box.append(self._volume_row(in_volume, in_muted, SOURCE,
                                        icon_on="audio-input-microphone-symbolic",
                                        icon_off="microphone-sensitivity-muted-symbolic"))
            if len(sources) > 1:
                box.append(self._device_list(sources, default_source,
                                             "set-default-source"))

        # --- per application -------------------------------------------------
        playing = streams()
        if playing:
            box.append(Gtk.Separator())
            box.append(heading("Applications"))
            for stream in playing:
                box.append(self._stream_row(stream))

        box.append(Gtk.Separator())
        settings = Gtk.Button(label="Advanced")
        settings.add_css_class("popup-action")
        settings.connect("clicked", lambda _b: launch(["pavucontrol"], self))
        box.append(settings)

    # -- rows ---------------------------------------------------------------

    def _volume_row(self, volume, muted, target,
                    icon_on="audio-volume-high-symbolic",
                    icon_off="audio-volume-muted-symbolic") -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        mute = Gtk.ToggleButton()
        mute.set_icon_name(icon_off if muted else icon_on)
        mute.set_active(muted)
        mute.add_css_class("popup-icon-button")
        mute.connect("toggled", self._on_mute, target, icon_on, icon_off)
        row.append(mute)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_value(round(volume * 100))
        scale.set_hexpand(True)
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.add_css_class("popup-slider")
        scale.connect("value-changed", self._on_volume, target)
        row.append(scale)
        return row

    def _stream_row(self, stream: dict) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        row.add_css_class("agenda-row")

        label = Gtk.Label(label=stream["name"], xalign=0)
        label.add_css_class("popup-subtle")
        label.set_ellipsize(3)
        row.append(label)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mute = Gtk.ToggleButton()
        mute.set_icon_name("audio-volume-muted-symbolic" if stream["muted"]
                           else "audio-volume-high-symbolic")
        mute.set_active(stream["muted"])
        mute.add_css_class("popup-icon-button")
        mute.connect("toggled", self._on_stream_mute, stream["index"])
        controls.append(mute)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.set_value(stream["volume"])
        scale.set_hexpand(True)
        scale.set_draw_value(True)
        scale.set_value_pos(Gtk.PositionType.RIGHT)
        scale.add_css_class("popup-slider")
        scale.connect("value-changed", self._on_stream_volume, stream["index"])
        controls.append(scale)
        row.append(controls)
        return row

    def _device_list(self, devices, default, command) -> Gtk.Widget:
        listbox = Gtk.ListBox()
        listbox.add_css_class("popup-list")
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for device in devices:
            name = device.get("name", "")
            button = Gtk.Button(label=device_label(device))
            button.add_css_class("popup-row")
            if name == default:
                button.add_css_class("popup-row-active")
            button.connect("clicked", self._on_pick_device, command, name)
            listbox.append(button)
        return listbox

    # -- actions -----------------------------------------------------------

    def _on_volume(self, scale: Gtk.Scale, target: str) -> None:
        # -l 1.0 caps at 100%: PipeWire happily goes past it, and software
        # amplification above 100% distorts on most hardware.
        wpctl("set-volume", "-l", "1.0", target, f"{scale.get_value() / 100:.2f}")

    def _on_mute(self, button, target, icon_on, icon_off) -> None:
        muted = button.get_active()
        wpctl("set-mute", target, "1" if muted else "0")
        button.set_icon_name(icon_off if muted else icon_on)

    def _on_stream_volume(self, scale: Gtk.Scale, index) -> None:
        subprocess.run(["pactl", "set-sink-input-volume", str(index),
                        f"{int(scale.get_value())}%"], check=False)

    def _on_stream_mute(self, button, index) -> None:
        muted = button.get_active()
        subprocess.run(["pactl", "set-sink-input-mute", str(index),
                        "1" if muted else "0"], check=False)
        button.set_icon_name("audio-volume-muted-symbolic" if muted
                             else "audio-volume-high-symbolic")

    def _on_pick_device(self, _button, command: str, name: str) -> None:
        subprocess.run(["pactl", command, name], check=False)
        self.hide()
