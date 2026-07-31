#!/usr/bin/env python3
"""Quick settings — the small panel behind the gear in the bar.

The gear used to open the full settings window straight away. That is the right
destination for "change the border width", and the wrong one for "turn the
Wi-Fi off": six of the things people reach for are switches, and a switch does
not deserve a 16-page application. So the gear opens this first, and the full
window is one button away.

Everything here is a toggle or a slider over a command-line tool that is already
installed — no daemon, no state of its own. What the tool reports IS the state,
read fresh every time the popup opens, so it can never disagree with reality.
"""

from __future__ import annotations

import shutil
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk
from popup import PanelWindow, heading, launch

REPO_SCRIPTS = "~/.local/share/fedora-buchhwin-hyprland/scripts"


def run(*cmd: str, timeout: int = 4) -> tuple[int, str]:
    """Run a tool. Returns (exit code, stdout). Never raises."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return proc.returncode, proc.stdout.strip()


# --- the individual pieces of state ----------------------------------------

def wifi_enabled() -> bool | None:
    """True/False, or None when there is no Wi-Fi hardware at all.

    None matters: a desktop with no wireless card should not be offered a
    switch that cannot do anything.
    """
    code, out = run("nmcli", "-t", "radio", "wifi")
    if code != 0 or not out:
        return None
    if out.strip() == "missing":
        return None
    return out.strip() == "enabled"


def bluetooth_enabled() -> bool | None:
    code, out = run("rfkill", "list", "bluetooth")
    if code != 0 or not out.strip():
        return None
    return "Soft blocked: no" in out


def dnd_enabled() -> bool:
    _, out = run("swaync-client", "-D")
    return out.strip() == "true"


def nightlight_enabled() -> bool:
    _code, out = run("systemctl", "--user", "is-active", "buchhwin-nightlight.service")
    return out.strip() == "active"


def caffeine_enabled() -> bool:
    """Is the idle manager suppressed?

    hypridle is the thing that locks and blanks the screen, so "keep the screen
    awake" is simply hypridle not running. Nothing extra to install, and it
    survives a crash of ours: worst case the screen locks again.
    """
    _, out = run("systemctl", "--user", "is-active", "buchhwin-idle.service")
    return out.strip() != "active"


def firewall_enabled() -> bool | None:
    """ufw's state, or None when ufw is not installed.

    `ufw status` needs root even to READ, so this asks systemd instead — which
    any user may do, and which cannot pop a password prompt just because
    somebody opened the panel.
    """
    code, out = run("systemctl", "is-enabled", "ufw.service")
    if code != 0 and not out:
        return None
    _code2, active = run("systemctl", "is-active", "ufw.service")
    return active.strip() == "active"


def gamemode_enabled() -> bool:
    import os
    from pathlib import Path as _Path
    state = _Path(os.environ.get("XDG_STATE_HOME", _Path.home() / ".local/state"))
    return (state / "buchhwin" / "gamemode.json").exists()


def brightness() -> int | None:
    """Percent, or None when the machine has no controllable backlight.

    `brightnessctl info` reports whatever device it considers current, and on a
    machine with no screen backlight that is an LED — measured in a VM, it
    returned `input1::numlock,leds,0,0%,1`, which drew a Brightness slider stuck
    at 0% for the keyboard's num-lock light. So the class has to be checked, not
    just the presence of a device.
    """
    code, out = run("brightnessctl", "-m", "-c", "backlight", "info")
    if code != 0 or not out:
        return None
    # machine readable: name,type,current,percent,max
    parts = out.split(",")
    if len(parts) < 5 or parts[1] != "backlight":
        return None
    try:
        if int(parts[4]) <= 0:
            return None
        return int(parts[3].rstrip("%"))
    except ValueError:
        return None


def volume() -> tuple[int, bool]:
    code, out = run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")
    if code != 0 or not out:
        return 0, False
    muted = "MUTED" in out
    try:
        value = float(out.split()[1])
    except (IndexError, ValueError):
        return 0, muted
    return round(value * 100), muted


class QuickPopup(PanelWindow):
    name = "quick"
    width = 340

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._state: dict = {}
        self._render()
        return self._box

    def refresh(self) -> None:
        self._populate()

    # -- layout -------------------------------------------------------------

    def _populate(self) -> None:
        """Read all nine tools OFF the main thread.

        Nine subprocesses at up to four seconds each, run inline, froze the
        panel daemon while the popup was built — measured: the window did not
        appear within a second, which for the popup behind the gear is the
        difference between "instant" and "did my click register". The
        Bluetooth popup had the same fault and the same fix.
        """
        def work() -> None:
            state = {
                "wifi": wifi_enabled(),
                "bluetooth": bluetooth_enabled(),
                "dnd": dnd_enabled(),
                "nightlight": nightlight_enabled(),
                "caffeine": caffeine_enabled(),
                "gamemode": gamemode_enabled(),
                "firewall": firewall_enabled(),
                "volume": volume(),
                "brightness": brightness(),
            }
            GLib.idle_add(self._apply_state, state)

        threading.Thread(target=work, daemon=True).start()

    def _apply_state(self, state: dict) -> bool:
        self._state = state
        self._render()
        return False

    def _render(self) -> None:
        box = self._box
        while (child := box.get_first_child()) is not None:
            box.remove(child)

        box.append(self._toggle_grid())

        vol, muted = self._state.get("volume", (0, False))
        box.append(self._slider("Volume", vol, muted,
                                "audio-volume-high-symbolic",
                                self._set_volume))

        level = self._state.get("brightness")
        if level is not None:
            box.append(self._slider("Brightness", level, False,
                                    "display-brightness-symbolic",
                                    self._set_brightness))

        box.append(Gtk.Separator())
        button = Gtk.Button(label="All settings…")
        button.add_css_class("popup-button")
        button.connect("clicked", lambda _b: launch(
            ["buchhwin-control-center"], self))
        box.append(button)

    def _toggle_grid(self) -> Gtk.Widget:
        """The switches, two per row.

        A grid rather than a list: these are six things you flip, and a list of
        six full-width rows makes a short popup into a tall one for no gain.
        """
        grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                           min_children_per_line=2,
                           max_children_per_line=2,
                           row_spacing=8, column_spacing=8,
                           homogeneous=True)

        wifi = self._state.get("wifi")
        if wifi is not None:
            grid.append(self._tile("Wi-Fi", "network-wireless-symbolic", wifi,
                                   self._toggle_wifi))

        bluetooth = self._state.get("bluetooth")
        if bluetooth is not None:
            grid.append(self._tile("Bluetooth", "bluetooth-symbolic", bluetooth,
                                   self._toggle_bluetooth))

        grid.append(self._tile("Do not disturb", "notifications-disabled-symbolic",
                               self._state.get("dnd", False), self._toggle_dnd))
        grid.append(self._tile("Night light", "night-light-symbolic",
                               self._state.get("nightlight", False),
                               self._toggle_nightlight))
        grid.append(self._tile("Keep awake", "my-caffeine-on-symbolic",
                               self._state.get("caffeine", False),
                               self._toggle_caffeine))
        grid.append(self._tile("Light theme", "weather-clear-symbolic",
                               False, self._toggle_theme, momentary=True))

        # Game mode: blur, shadows, animations and gaps off in one press.
        grid.append(self._tile("Game mode", "applications-games-symbolic",
                               self._state.get("gamemode", False),
                               self._toggle_gamemode))

        firewall = self._state.get("firewall")
        if firewall is not None:
            grid.append(self._tile("Firewall", "security-high-symbolic",
                                   firewall, self._toggle_firewall))
        return grid

    def _tile(self, label: str, icon: str, active: bool, on_click,
              momentary: bool = False) -> Gtk.Widget:
        button = Gtk.Button()
        button.add_css_class("quick-tile")
        if active:
            button.add_css_class("quick-tile-on")
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.append(Gtk.Image.new_from_icon_name(icon))
        text = Gtk.Label(label=label)
        text.add_css_class("quick-tile-label")
        text.set_wrap(True)
        text.set_justify(Gtk.Justification.CENTER)
        content.append(text)
        button.set_child(content)

        def clicked(_b):
            on_click()
            # Re-read rather than assume: a toggle that failed — no permission,
            # no hardware, service masked — must not leave the tile lit.
            if not momentary:
                self._populate()
        button.connect("clicked", clicked)
        return button

    def _slider(self, label: str, value: int, muted: bool, icon: str,
                on_change) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("popup-row")
        image = Gtk.Image.new_from_icon_name(icon)
        if muted:
            image.add_css_class("popup-subtle")
        row.append(image)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        scale.add_css_class("popup-slider")
        scale.set_hexpand(True)
        scale.set_draw_value(False)
        scale.set_value(value)
        scale.connect("value-changed", lambda s: on_change(int(s.get_value())))
        row.append(scale)

        percent = Gtk.Label(label=f"{value}%")
        percent.add_css_class("popup-subtle")
        row.append(percent)
        scale.connect("value-changed",
                      lambda s: percent.set_text(f"{int(s.get_value())}%"))

        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        wrapper.append(heading(label))
        wrapper.append(row)
        return wrapper

    # -- actions ------------------------------------------------------------

    def _toggle_wifi(self) -> None:
        run("nmcli", "radio", "wifi", "off" if wifi_enabled() else "on", timeout=8)

    def _toggle_bluetooth(self) -> None:
        run("rfkill", "block" if bluetooth_enabled() else "unblock", "bluetooth")

    def _toggle_dnd(self) -> None:
        run("swaync-client", "-d")

    def _toggle_nightlight(self) -> None:
        action = "stop" if nightlight_enabled() else "start"
        run("systemctl", "--user", action, "buchhwin-nightlight.service", timeout=8)

    def _toggle_caffeine(self) -> None:
        # Stopping hypridle is what keeps the screen awake; starting it hands
        # the machine back its normal idle behaviour.
        action = "start" if caffeine_enabled() else "stop"
        run("systemctl", "--user", action, "buchhwin-idle.service", timeout=8)

    def _toggle_theme(self) -> None:
        launch(["bhctl", "theme", "toggle"], self)

    def _toggle_gamemode(self) -> None:
        launch(["sh", "-c",
                "~/.local/share/fedora-buchhwin-hyprland/scripts/gamemode.sh"], self)

    def _toggle_firewall(self) -> None:
        # Stopping the firewall needs root, so this goes through pkexec and the
        # session's polkit agent asks properly. Never silently, and never with
        # a cached password.
        action = "stop" if firewall_enabled() else "start"
        launch(["pkexec", "systemctl", action, "ufw.service"], self)

    def _set_volume(self, percent: int) -> None:
        run("wpctl", "set-volume", "-l", "1.0",
            "@DEFAULT_AUDIO_SINK@", f"{percent}%")

    def _set_brightness(self, percent: int) -> None:
        run("brightnessctl", "-q", "set", f"{percent}%")
        # Desktop monitors have no backlight device; they take brightness over
        # the cable, via DDC/CI. Slow (a second or so per display) and not
        # supported by every screen, so it runs detached and its failure is
        # ignored — the laptop panel above must not wait on it.
        if shutil.which("ddcutil"):
            subprocess.Popen(["ddcutil", "--noverify", "setvcp", "10", str(percent)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
