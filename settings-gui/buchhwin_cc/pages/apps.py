"""Settings page: apps.

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
    p = page(_("Applications"), "view-grid-symbolic")

    g = group(p, _("Launcher"),
              _("A stock system offers dozens of entries that exist only so "
                "other software can find a handler — one per image format, "
                "certificate prompts, geolocation agents. Hiding them "
                "uninstalls nothing."))
    script = str(REPO / "scripts" / "menu-cleanup.py")
    hidden = len(run_lines([sys.executable, script, "--list"])) - 1
    row = Adw.ActionRow(
        title=_("Hidden entries"),
        subtitle=_("%d entries are hidden from the launcher") % max(hidden, 0))
    button = Gtk.Button(label=_("Show them all again"), valign=Gtk.Align.CENTER)
    button.connect("clicked", lambda *a, _f=_on_restore_menu: _f(win, *a[1:]))
    row.add_suffix(button)
    g.add(row)

    g = group(p, _("More"))
    win._launch_row(g, _("Installed applications"),
                     _("Everything with a launcher entry"),
                     ["rofi", "-show", "drun"])

    win.add_page(p, "apps", _("Applications"), "view-grid-symbolic")


def _on_restore_menu(win, _b):
    script = str(REPO / "scripts" / "menu-cleanup.py")
    subprocess.run([sys.executable, script, "--restore"], check=False)
    win.toast(_("All entries are visible again"))

# -- shared --------------------------------------------------------------
