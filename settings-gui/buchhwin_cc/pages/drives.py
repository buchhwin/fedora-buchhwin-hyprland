"""Settings page: drives.

Extracted from the single 1392-line file the settings app used to be. Each page
is one module exporting build(win); `win` is the Window, which still owns the
shared helpers (toast, add_page, _launch_row, _spawn) so a page can use them
without importing the window back and creating a cycle.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")


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
    p = page(_("Drives"), "drive-harddisk-symbolic")

    win.cloud_group = group(
        p, _("Cloud"),
        _("Google Drive files do NOT come from the Accounts page — GNOME 50 "
          "removed that. They come from here, through rclone. You sign in "
          "in your browser; no password is stored by this application."))
    win.net_group = group(
        p, _("Network"),
        _("SMB, NFS, WebDAV or SFTP. Mounted as you, without root. "
          "Passwords go to the keyring."))
    win._rebuild_drives()
    win.add_page(p, "drives", _("Drives"), "drive-harddisk-symbolic")
