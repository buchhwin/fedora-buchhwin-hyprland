"""Network popup: what you are connected to, and how to connect to Wi-Fi.

Clicking the network icon in Windows shows the current connection and a list of
networks you can join. This is that, on nmcli. Everything more involved — a
static address, a VPN, an 802.1X certificate — is nm-connection-editor's job,
and there is a button for it.

Security note that matters: the Wi-Fi password is NEVER passed as a command
line argument. Arguments are world-readable in /proc while the process runs, so
`nmcli device wifi connect SSID password hunter2` leaks it to every user on the
machine. `nmcli --ask` reads it from stdin instead.
"""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk  # noqa: E402

from popup import PanelWindow, heading, launch, note  # noqa: E402


def nmcli(*args: str, timeout: int = 10) -> tuple[int, str]:
    try:
        proc = subprocess.run(["nmcli", *args], capture_output=True, text=True,
                              check=False, timeout=timeout)
        return proc.returncode, proc.stdout.strip()
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""


def current_connection() -> tuple[str, str, str]:
    """Return (kind, name, detail) where kind is wifi / ethernet / none."""
    # -t -f gives stable, colon-separated output; parsing `nmcli` prose breaks
    # the moment someone runs it in another language.
    rc, out = nmcli("-t", "-f", "TYPE,STATE,CONNECTION,DEVICE", "device")
    if rc != 0:
        return "none", "NetworkManager unavailable", ""

    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        kind, state, name, device = parts[0], parts[1], parts[2], parts[3]
        if state != "connected":
            continue
        if kind == "wifi":
            return "wifi", name, device
        if kind == "ethernet":
            # NetworkManager names an auto-created wired profile after the
            # interface, so `name` is usually just "ens18" — printing that as
            # the headline and again as the detail says the same cryptic thing
            # twice. Only show the profile name when someone chose one.
            label = name if name and name != device else "Wired connection"
            return "ethernet", label, device
    return "none", "Not connected", ""


def wifi_networks() -> list[dict]:
    """Visible Wi-Fi networks, strongest first, one entry per SSID."""
    rc, out = nmcli("-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY",
                    "device", "wifi", "list", timeout=15)
    if rc != 0:
        return []

    seen: dict[str, dict] = {}
    for line in out.splitlines():
        # SSIDs can contain colons; nmcli escapes them as \:  Split on
        # unescaped separators only.
        parts = _split_escaped(line)
        if len(parts) < 4:
            continue
        in_use, ssid, signal, security = parts[0], parts[1], parts[2], parts[3]
        if not ssid:
            continue                      # hidden network, nothing to click
        try:
            strength = int(signal)
        except ValueError:
            strength = 0
        entry = {
            "ssid": ssid,
            "signal": strength,
            "secure": security not in ("", "--"),
            "active": in_use.strip() == "*",
        }
        if ssid not in seen or strength > seen[ssid]["signal"]:
            seen[ssid] = entry

    return sorted(seen.values(), key=lambda e: -e["signal"])


def _split_escaped(line: str) -> list[str]:
    parts, current, escaped = [], [], False
    for char in line:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return parts


def radio_state() -> dict:
    """Wi-Fi and WWAN radio state. "missing" means no such hardware."""
    rc, out = nmcli("-t", "radio")
    if rc != 0:
        return {}
    parts = out.split(":")
    keys = ("wifi_hw", "wifi", "wwan_hw", "wwan")
    return dict(zip(keys, parts)) if len(parts) >= 4 else {}


def ip_details(device: str) -> list[str]:
    """Address, gateway and DNS, in the words a person would use."""
    if not device:
        return []
    rc, out = nmcli("-t", "-f", "IP4.ADDRESS,IP4.GATEWAY,IP4.DNS",
                    "device", "show", device)
    if rc != 0:
        return []
    labels = {"IP4.ADDRESS[1]": "Address", "IP4.GATEWAY": "Gateway",
              "IP4.DNS[1]": "DNS", "IP4.DNS[2]": "DNS"}
    rows = []
    for line in out.splitlines():
        key, _, value = line.partition(":")
        if value and value != "--" and key in labels:
            rows.append(f"{labels[key]}: {value}")
    return rows


def saved_connections() -> list[tuple[str, str]]:
    """(name, type) of stored Wi-Fi profiles."""
    rc, out = nmcli("-t", "-f", "NAME,TYPE", "connection", "show")
    if rc != 0:
        return []
    result = []
    for line in out.splitlines():
        parts = _split_escaped(line)
        if len(parts) >= 2 and parts[1] in ("802-11-wireless", "wifi"):
            result.append((parts[0], parts[1]))
    return result


def signal_icon(strength: int) -> str:
    if strength >= 75:
        return "network-wireless-signal-excellent-symbolic"
    if strength >= 50:
        return "network-wireless-signal-good-symbolic"
    if strength >= 25:
        return "network-wireless-signal-ok-symbolic"
    return "network-wireless-signal-weak-symbolic"


class NetworkPopup(PanelWindow):
    name = "network"
    width = 360

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._populate()
        return self._box

    def refresh(self) -> None:
        # Scanning for networks on every show, not on a timer: a Wi-Fi list
        # that is thirty seconds old is worse than useless, and scanning while
        # nobody is looking wastes radio time.
        self._populate()

    def _populate(self) -> None:
        while (child := self._box.get_first_child()) is not None:
            self._box.remove(child)

        kind, name, device = current_connection()

        status = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        status.add_css_class("popup-status")
        icon = {
            "wifi": "network-wireless-signal-excellent-symbolic",
            "ethernet": "network-wired-symbolic",
        }.get(kind, "network-offline-symbolic")
        status.append(Gtk.Image.new_from_icon_name(icon))

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        title = Gtk.Label(label=name, xalign=0)
        title.add_css_class("popup-heading")
        text.append(title)
        subtitle = Gtk.Label(
            label={"wifi": "Wi-Fi", "ethernet": "Wired"}.get(kind, "Offline")
                  + (f" · {device}" if device else ""),
            xalign=0)
        subtitle.add_css_class("popup-subtle")
        text.append(subtitle)
        status.append(text)
        self._box.append(status)

        # Addresses, in the words a person would use rather than nmcli's keys.
        for line in ip_details(device):
            row = Gtk.Label(label=line, xalign=0)
            row.add_css_class("popup-subtle")
            self._box.append(row)

        radio = radio_state()
        has_wifi = radio.get("wifi_hw") not in (None, "missing")

        if has_wifi:
            self._box.append(Gtk.Separator())

            toggle = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            toggle.append(heading("Wi-Fi"))
            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            toggle.append(spacer)
            switch = Gtk.Switch(valign=Gtk.Align.CENTER)
            switch.set_active(radio.get("wifi") == "enabled")
            switch.connect("notify::active", self._on_wifi_toggle)
            toggle.append(switch)
            self._box.append(toggle)

            if radio.get("wifi") == "enabled":
                networks = wifi_networks()
                if networks:
                    self._box.append(self._network_list(networks))
                else:
                    self._box.append(note("Looking for networks…"))

                if kind == "wifi":
                    disconnect = Gtk.Button(label="Disconnect")
                    disconnect.add_css_class("popup-action")
                    disconnect.connect("clicked", self._on_disconnect, device)
                    self._box.append(disconnect)

                saved = saved_connections()
                if saved:
                    self._box.append(Gtk.Separator())
                    self._box.append(heading("Saved networks"))
                    self._box.append(self._saved_list(saved))
        elif kind == "ethernet":
            # A desktop on a cable has no Wi-Fi radio; saying "no networks
            # found" there would read like a fault.
            self._box.append(note("No Wi-Fi adapter"))

        self._box.append(Gtk.Separator())

        settings = Gtk.Button(label="Network settings")
        settings.add_css_class("popup-action")
        settings.connect("clicked",
                         lambda _b: launch(["nm-connection-editor"], self))
        self._box.append(settings)

    def _saved_list(self, saved) -> Gtk.Widget:
        listbox = Gtk.ListBox()
        listbox.add_css_class("popup-list")
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        for name, _kind in saved:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            label = Gtk.Label(label=name, xalign=0)
            label.set_ellipsize(3)
            label.set_hexpand(True)
            row.append(label)
            forget = Gtk.Button(label="Forget", valign=Gtk.Align.CENTER)
            forget.connect("clicked", self._on_forget, name)
            row.append(forget)
            wrapper = Gtk.Box()
            wrapper.add_css_class("popup-row")
            wrapper.append(row)
            row.set_hexpand(True)
            listbox.append(wrapper)
        return listbox

    def _on_wifi_toggle(self, switch, _param) -> None:
        nmcli("radio", "wifi", "on" if switch.get_active() else "off")
        # Turning the radio on takes a moment to produce a scan; rebuilding at
        # once would show an empty list and look broken.
        GLib.timeout_add_seconds(2, lambda: (self._populate(), False)[1])

    def _on_disconnect(self, _button, device: str) -> None:
        nmcli("device", "disconnect", device, timeout=20)
        self._populate()

    def _on_forget(self, _button, name: str) -> None:
        # Deleting a saved network is not undoable and a mis-click on a work
        # network is expensive, so it asks first.
        dialog = Gtk.AlertDialog()
        dialog.set_message(f"Forget “{name}”?")
        dialog.set_detail("The saved password will be deleted. "
                          "You will need it again to reconnect.")
        dialog.set_buttons(["Cancel", "Forget"])
        dialog.set_cancel_button(0)
        dialog.set_default_button(0)

        def answered(d, result):
            try:
                if d.choose_finish(result) == 1:
                    nmcli("connection", "delete", name, timeout=20)
                    self._populate()
            except GLib.Error:
                pass

        dialog.choose(self.window, None, answered)

    def _network_list(self, networks: list[dict]) -> Gtk.Widget:
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_max_content_height(260)
        scroller.set_propagate_natural_height(True)

        listbox = Gtk.ListBox()
        listbox.add_css_class("popup-list")
        listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        for net in networks:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.append(Gtk.Image.new_from_icon_name(signal_icon(net["signal"])))

            label = Gtk.Label(label=net["ssid"], xalign=0)
            label.set_ellipsize(3)
            label.set_hexpand(True)
            row.append(label)

            if net["secure"]:
                row.append(Gtk.Image.new_from_icon_name(
                    "network-wireless-encrypted-symbolic"))

            button = Gtk.Button(child=row)
            button.add_css_class("popup-row")
            if net["active"]:
                button.add_css_class("popup-row-active")
            button.connect("clicked", self._on_pick, net)
            listbox.append(button)

        scroller.set_child(listbox)
        return scroller

    # -- connecting --------------------------------------------------------

    def _on_pick(self, _button: Gtk.Button, net: dict) -> None:
        if net["active"]:
            self.hide()
            return
        if net["secure"] and not self._known(net["ssid"]):
            self._ask_password(net)
        else:
            self._connect(net["ssid"], None)

    def _known(self, ssid: str) -> bool:
        rc, out = nmcli("-t", "-f", "NAME", "connection", "show")
        return rc == 0 and ssid in out.splitlines()

    def _ask_password(self, net: dict) -> None:
        dialog = Gtk.Window(title=net["ssid"], transient_for=self.window,
                            modal=True)
        dialog.set_default_size(300, -1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.append(Gtk.Label(label=f"Password for {net['ssid']}", xalign=0))

        entry = Gtk.PasswordEntry()
        entry.set_show_peek_icon(True)
        box.append(entry)

        self._status = Gtk.Label(label="", xalign=0)
        self._status.add_css_class("popup-subtle")
        box.append(self._status)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _b: dialog.close())
        buttons.append(cancel)

        connect = Gtk.Button(label="Connect")
        connect.add_css_class("suggested-action")
        connect.connect("clicked",
                        lambda _b: self._connect(net["ssid"], entry.get_text(),
                                                 dialog))
        buttons.append(connect)
        box.append(buttons)

        entry.connect("activate",
                      lambda _e: self._connect(net["ssid"], entry.get_text(),
                                               dialog))

        dialog.set_child(box)
        dialog.present()

    def _connect(self, ssid: str, password: str | None,
                 dialog: Gtk.Window | None = None) -> None:
        args = ["nmcli"]
        if password:
            # --ask makes nmcli read the secret from stdin. Never put it in
            # argv: /proc/<pid>/cmdline is readable by every local user.
            args.append("--ask")
        args += ["device", "wifi", "connect", ssid]

        try:
            proc = subprocess.run(args, input=(password + "\n") if password else None,
                                  capture_output=True, text=True, check=False,
                                  timeout=45)
        except (OSError, subprocess.TimeoutExpired) as exc:
            self._report(dialog, f"Could not connect: {exc}")
            return

        if proc.returncode == 0:
            if dialog:
                dialog.close()
            self.hide()
        else:
            message = (proc.stderr or proc.stdout or "unknown error").strip()
            self._report(dialog, message.splitlines()[-1] if message else "failed")

    def _report(self, dialog: Gtk.Window | None, message: str) -> None:
        if dialog and hasattr(self, "_status"):
            self._status.set_label(message)
        else:
            GLib.idle_add(lambda: print(message))

