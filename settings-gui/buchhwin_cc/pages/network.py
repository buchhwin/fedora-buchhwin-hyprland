"""Settings page: network.

Extracted from the single 1392-line file the settings app used to be. Each page
is one module exporting build(win); `win` is the Window, which still owns the
shared helpers (toast, add_page, _launch_row, _spawn) so a page can use them
without importing the window back and creating a cycle.
"""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk

from ..helpers import (  # noqa: F401
    ACCENTS,
    FLAVOURS,
    REPO,
    STATE,
    combo_row,
    cursor_themes,
    group,
    page,
    pinnable_apps,
    run,
    run_lines,
    slider_row,
    spin_row,
    switch_row,
)


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

    # --- VPN ---------------------------------------------------------------
    win._vpn_group = group(
        p, _("VPN"),
        _("WireGuard configurations are imported into NetworkManager, which "
          "speaks the protocol itself — no extra service, and the tunnel comes "
          "up with the network. Switch one on in the bar's network popup."))
    win._vpn_rows = []
    _rebuild_vpn(win)

    row = Adw.ActionRow(
        title=_("Import a WireGuard configuration"),
        subtitle=_("A .conf file from your provider or your own server"))
    button = Gtk.Button(label=_("Import…"), valign=Gtk.Align.CENTER)
    button.connect("clicked", lambda _b: _import_vpn(win))
    row.add_suffix(button)
    win._vpn_group.add(row)
    win._vpn_rows.append(row)

    g = group(p, _("Weather"),
              _("Shown in the calendar popup. Empty means off — a weather "
                "service with no location looks up whoever asked, so leaving "
                "this blank keeps this machine's address to itself."))
    row = Adw.EntryRow(title=_("Location"),
                       text=win.s.get("weather.location", "") or "")
    row.connect("changed",
                lambda r: win.s.set("weather.location", r.get_text().strip()))
    g.add(row)
    g.add(Adw.ActionRow(
        title=_("Example"), subtitle=_("Bremen · Bremen,DE · 28195")))

    g = group(p, _("More"))
    win._launch_row(g, _("Wi-Fi and connection editor"),
                     _("Add networks, VPNs and static addresses"),
                     ["nm-connection-editor"])

    win.add_page(p, "network", _("Network"), "network-wireless-symbolic")


def _vpn_list() -> list[str]:
    names = []
    for line in run_lines(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"]):
        parts = line.rsplit(":", 1)
        if len(parts) == 2 and parts[1] in ("wireguard", "vpn"):
            names.append(parts[0])
    return names


def _rebuild_vpn(win) -> None:
    for row in win._vpn_rows:
        win._vpn_group.remove(row)
    win._vpn_rows = []
    for name in _vpn_list():
        row = Adw.ActionRow(title=name, subtitle=_("WireGuard"))
        remove = Gtk.Button(icon_name="user-trash-symbolic",
                            valign=Gtk.Align.CENTER)
        remove.connect("clicked", lambda _b, n=name: _remove_vpn(win, n))
        row.add_suffix(remove)
        win._vpn_group.add(row)
        win._vpn_rows.append(row)
    if not win._vpn_rows:
        row = Adw.ActionRow(title=_("No VPN configured"))
        win._vpn_group.add(row)
        win._vpn_rows.append(row)


def _import_vpn(win) -> None:
    chooser = Gtk.FileDialog(title=_("Choose a WireGuard configuration"))
    filters = Gio.ListStore.new(Gtk.FileFilter)
    conf = Gtk.FileFilter()
    conf.set_name(_("WireGuard configuration (*.conf)"))
    conf.add_pattern("*.conf")
    filters.append(conf)
    chooser.set_filters(filters)

    def picked(dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return                      # cancelled
        if gfile is None:
            return
        path = gfile.get_path()
        if not path:
            return
        proc = subprocess.run(
            ["nmcli", "connection", "import", "type", "wireguard", "file", path],
            capture_output=True, text=True, check=False, timeout=30)
        if proc.returncode != 0:
            win.toast(_("Import failed: {}").format(
                (proc.stderr or proc.stdout).strip().splitlines()[-1:] or ""))
            return
        _rebuild_vpn(win)
        # The .conf holds the private key in plain text. NetworkManager has now
        # copied it into /etc/NetworkManager/system-connections/ (root, 0600),
        # so the copy in Downloads is a spare key lying on the doormat.
        win.toast(_("Imported. Delete the .conf file — it contains your "
                    "private key in plain text."))

    chooser.open(win, None, picked)


def _remove_vpn(win, name: str) -> None:
    dialog = Adw.AlertDialog(
        heading=_("Remove {}?").format(name),
        body=_("The connection and its keys are deleted from NetworkManager. "
               "This cannot be undone without the original .conf file."))
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("remove", _("Remove"))
    dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

    def answered(_d, response):
        if response != "remove":
            return
        subprocess.run(["nmcli", "connection", "delete", name],
                       capture_output=True, check=False, timeout=20)
        _rebuild_vpn(win)
        win.toast(_("{} removed").format(name))

    dialog.connect("response", answered)
    dialog.present(win)

# -- Displays ------------------------------------------------------------
