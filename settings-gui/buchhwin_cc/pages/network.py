"""Settings page: network.

Extracted from the single 1392-line file the settings app used to be. Each page
is one module exporting build(win); `win` is the Window, which still owns the
shared helpers (toast, add_page, _launch_row, _spawn) so a page can use them
without importing the window back and creating a cycle.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from ..helpers import (ACCENTS, FLAVOURS, REPO, STATE, combo_row,  # noqa: F401
                       cursor_themes, group, page, pinnable_apps, run,
                       run_lines, slider_row, spin_row, switch_row)
from ..keycapture import KeyCaptureDialog  # noqa: E402


def build(win):
    p = page(_("Network"), "network-wireless-symbolic")

    g = group(p, _("Connections"), _("What this machine is connected to."))
    rows = 0
    for line in run_lines(["nmcli", "-t", "-f",
                           "TYPE,STATE,CONNECTION,DEVICE", "device"]):
        parts = line.split(":")
        if len(parts) < 4 or parts[0] in ("loopback", "bridge"):
            continue
        kind, state, conn, device = parts[0], parts[1], parts[2], parts[3]
        title = conn or device
        g.add(Adw.ActionRow(
            title=title,
            subtitle=f"{kind} · {device} · {state}"))
        rows += 1
    if not rows:
        g.add(Adw.ActionRow(title=_("NetworkManager is not answering")))

    g = group(p, _("Addresses"))
    for line in run_lines(["ip", "-brief", "address", "show"]):
        parts = line.split()
        if not parts or parts[0] == "lo":
            continue
        g.add(Adw.ActionRow(title=parts[0],
                            subtitle=" ".join(parts[2:]) or _("no address")))

    g = group(p, _("More"))
    win._launch_row(g, _("Wi-Fi and connection editor"),
                     _("Add networks, VPNs and static addresses"),
                     ["nm-connection-editor"])

    win.add_page(p, "network", _("Network"), "network-wireless-symbolic")

# -- Displays ------------------------------------------------------------
