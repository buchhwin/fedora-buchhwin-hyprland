"""Settings page: about.

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
from ..store import S  # noqa: E402


def build(win):
    p = page(_("About"), "help-about-symbolic")
    g = group(p, _("Versions"), "")
    for name, cmd in (("Hyprland", ["Hyprland", "--version"]),
                      ("Waybar", ["waybar", "--version"]),
                      ("rofi", ["rofi", "-version"]),
                      ("kitty", ["kitty", "--version"])):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=5).stdout.splitlines()
            value = out[0].strip() if out else _("not installed")
        except (OSError, subprocess.TimeoutExpired):
            value = _("not installed")
        g.add(Adw.ActionRow(title=name, subtitle=value))

    g2 = group(p, _("Configuration"), "")
    g2.add(Adw.ActionRow(title=_("Settings file"), subtitle=str(S.SETTINGS)))
    g2.add(Adw.ActionRow(title=_("Repository"), subtitle=str(REPO)))

    g3 = group(p, _("Language"),
               _("English is the source language; German is a translation."))
    combo_row(g3, _("Interface language"), "", ["en", "de"],
              (STATE / "lang").read_text().strip()
              if (STATE / "lang").exists() else "en",
              win._set_lang)

    win.add_page(p, "about", _("About"), "help-about-symbolic")
