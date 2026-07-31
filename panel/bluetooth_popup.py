#!/usr/bin/env python3
"""Bluetooth — pair, connect, disconnect, from the bar.

Network and sound already have a popup; Bluetooth was the conspicuous hole, and
the only way to reach it was blueman's own window, which looks like nothing else
here.

Everything goes through `bluetoothctl`, which is part of bluez and therefore
already installed. Its output is prose, not a data format, so each reader below
parses exactly the shape it needs and nothing more — a parser that tries to
understand all of bluetoothctl's output would break on the next release.
"""

from __future__ import annotations

import re
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk
from popup import PanelWindow, heading, launch, note

MAC = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", re.I)


def bt(*args: str, timeout: int = 8) -> str:
    try:
        return subprocess.run(["bluetoothctl", *args], capture_output=True,
                              text=True, check=False, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def adapter() -> dict | None:
    """The controller, or None when the machine has no Bluetooth at all.

    None and "off" are different answers and must look different: a desktop
    with no radio should not be shown a switch, and a laptop with the radio off
    should not be told it has no Bluetooth.
    """
    out = bt("show")
    if not out.strip():
        return None
    powered = "Powered: yes" in out
    name = ""
    for line in out.splitlines():
        if "Name:" in line:
            name = line.split("Name:", 1)[1].strip()
            break
    return {"name": name or "Bluetooth", "powered": powered}


def devices() -> list[dict]:
    """Paired and nearby devices, with their connection state."""
    found = []
    for line in bt("devices").splitlines():
        parts = line.split(maxsplit=2)
        if len(parts) < 3 or parts[0] != "Device" or not MAC.match(parts[1]):
            continue
        mac, name = parts[1], parts[2]
        info = bt("info", mac, timeout=5)
        found.append({
            "mac": mac,
            "name": name,
            "connected": "Connected: yes" in info,
            "paired": "Paired: yes" in info,
            "icon": _icon_for(info),
        })
    # Connected first, then paired, then the rest — the order you want them in.
    found.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
    return found


def _icon_for(info: str) -> str:
    kind = ""
    for line in info.splitlines():
        if "Icon:" in line:
            kind = line.split("Icon:", 1)[1].strip()
            break
    return {
        "audio-headset": "audio-headset-symbolic",
        "audio-headphones": "audio-headphones-symbolic",
        "audio-card": "audio-speakers-symbolic",
        "input-keyboard": "input-keyboard-symbolic",
        "input-mouse": "input-mouse-symbolic",
        "phone": "phone-symbolic",
        "computer": "computer-symbolic",
    }.get(kind, "bluetooth-symbolic")


class BluetoothPopup(PanelWindow):
    name = "bluetooth"
    width = 340

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._scanning = False
        self._show(None, [])
        return self._box

    def refresh(self) -> None:
        self._populate()

    def _populate(self) -> None:
        """Read the adapter and the devices OFF the main thread.

        bluetoothctl takes seconds — `show` on a machine with no adapter runs
        to its timeout, and `info` is one call per device. Doing that inline
        froze the whole panel daemon: the Bluetooth popup did not appear at
        all within three seconds, and while it was building, every other popup
        was frozen too. Measured; it is why this is threaded and the others are
        not.
        """
        self._set_loading()

        def work() -> None:
            state = adapter()
            found = devices() if state and state["powered"] else []
            GLib.idle_add(self._show, state, found)

        threading.Thread(target=work, daemon=True).start()

    def _set_loading(self) -> None:
        box = self._box
        while (child := box.get_first_child()) is not None:
            box.remove(child)
        box.append(heading("Bluetooth"))
        box.append(note("Reading adapter…"))

    def _show(self, adapter_state, found) -> bool:
        box = self._box
        while (child := box.get_first_child()) is not None:
            box.remove(child)

        if adapter_state is None:
            box.append(heading("Bluetooth"))
            box.append(note("This machine has no Bluetooth adapter"))
            return False

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("popup-row")
        row.append(Gtk.Image.new_from_icon_name(
            "bluetooth-symbolic" if adapter_state["powered"]
            else "bluetooth-disabled-symbolic"))
        label = Gtk.Label(label=adapter_state["name"], xalign=0)
        label.set_hexpand(True)
        row.append(label)
        switch = Gtk.Switch(active=adapter_state["powered"],
                            valign=Gtk.Align.CENTER)
        switch.connect("notify::active", self._on_power)
        row.append(switch)
        box.append(row)

        if not adapter_state["powered"]:
            box.append(note("Turn Bluetooth on to see devices"))
            return False

        if found:
            box.append(Gtk.Separator())
            box.append(heading("Devices"))
            for device in found:
                box.append(self._device_row(device))
        else:
            box.append(note("No devices yet — scan to find one"))

        box.append(Gtk.Separator())
        scan = Gtk.Button(label="Stop scanning" if self._scanning else "Scan for devices")
        scan.add_css_class("popup-action")
        scan.connect("clicked", self._on_scan)
        box.append(scan)

        settings = Gtk.Button(label="Bluetooth settings")
        settings.add_css_class("popup-action")
        settings.connect("clicked", lambda _b: launch(["blueman-manager"], self))
        box.append(settings)
        return False

    def _device_row(self, device: dict) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("popup-row")
        if device["connected"]:
            row.add_css_class("popup-row-active")
        row.append(Gtk.Image.new_from_icon_name(device["icon"]))

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        labels.set_hexpand(True)
        labels.append(Gtk.Label(label=device["name"], xalign=0))
        state = Gtk.Label(
            label="connected" if device["connected"]
            else ("paired" if device["paired"] else "not paired"),
            xalign=0)
        state.add_css_class("popup-subtle")
        labels.append(state)
        row.append(labels)

        button = Gtk.Button(label="Disconnect" if device["connected"] else "Connect",
                            valign=Gtk.Align.CENTER)
        button.connect("clicked", self._on_connect, device)
        row.append(button)
        return row

    # -- actions ------------------------------------------------------------

    def _on_power(self, switch, _param) -> None:
        bt("power", "on" if switch.get_active() else "off")
        GLib.timeout_add(600, lambda: (self._populate(), False)[1])

    def _on_scan(self, _button) -> None:
        # Scanning is a long-running bluetoothctl session, so it runs detached
        # and is stopped the same way. Five seconds of discovery is enough to
        # find something that is in pairing mode and short enough that nobody
        # is left staring at a spinner.
        self._scanning = not self._scanning
        if self._scanning:
            subprocess.Popen(["bluetoothctl", "--timeout", "12", "scan", "on"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            GLib.timeout_add_seconds(5, self._rescan)
        else:
            bt("scan", "off")
            self._populate()

    def _rescan(self) -> bool:
        if not self._visible:
            return False                # popup closed: stop polling
        self._populate()
        return self._scanning           # keep going while scanning

    def _on_connect(self, _button, device: dict) -> None:
        if device["connected"]:
            bt("disconnect", device["mac"], timeout=15)
        else:
            if not device["paired"]:
                bt("pair", device["mac"], timeout=25)
                bt("trust", device["mac"])
            bt("connect", device["mac"], timeout=25)
        self._populate()
