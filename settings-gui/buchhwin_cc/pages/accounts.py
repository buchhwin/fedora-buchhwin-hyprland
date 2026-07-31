"""Settings page: accounts.

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
    p = page(_("Accounts"), "system-users-symbolic")
    g = group(p, _("Online accounts"),
              _("Sign in once, and Evolution and the calendar have your "
                "mail, calendar and contacts."))

    row = Adw.ActionRow(
        title=_("Online accounts"),
        subtitle=_("Google, Microsoft, Nextcloud, IMAP/CalDAV"))
    btn = Gtk.Button(label=_("Open"), valign=Gtk.Align.CENTER)
    btn.add_css_class("suggested-action")
    btn.connect("clicked", lambda _b: run("gnome-online-accounts-gtk"))
    row.add_suffix(btn)
    g.add(row)

    # This banner exists because the alternative is half an hour of looking
    # for a Drive folder that is never going to appear.
    g2 = group(p, _("About Google Drive"), "")
    note = Adw.ActionRow(
        title=_("Files do not come from here"),
        subtitle=_("GNOME 50 removed Google Drive file access — the library "
                   "behind it had been unmaintained for years. Calendar, "
                   "contacts and mail still work. For FILES use the Drives "
                   "page, which uses rclone."))
    note.set_subtitle_lines(0)
    goto = Gtk.Button(label=_("Drives"), valign=Gtk.Align.CENTER)
    goto.connect("clicked", lambda _b: win.stack.set_visible_child_name("drives"))
    note.add_suffix(goto)
    g2.add(note)

    win.add_page(p, "accounts", _("Accounts"), "system-users-symbolic")
