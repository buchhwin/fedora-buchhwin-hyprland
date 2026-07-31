"""Settings page: autostart.

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
    p = page(_("Autostart"), "system-run-symbolic")
    win.auto_group = group(
        p, _("Start with the session"),
        _("The bar, notifications, clipboard, wallpaper and idle manager "
          "are systemd services — they are not listed here and restart on "
          "their own."))
    win._rebuild_autostart()
    win.add_page(p, "autostart", _("Autostart"), "system-run-symbolic")
