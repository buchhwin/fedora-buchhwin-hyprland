"""Settings page: power.

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
    p = page(_("Power"), "preferences-system-power-symbolic")
    g = group(p, _("Idle"),
              _("Seconds of inactivity. Zero switches a step off."))
    spin_row(g, _("Dim the screen after"), "", 0, 3600, 30,
             win.s.get("idle.dim_after", 300),
             lambda v: win.s.set("idle.dim_after", int(v)))
    spin_row(g, _("Lock after"), "", 0, 7200, 60,
             win.s.get("idle.lock_after", 600),
             lambda v: win.s.set("idle.lock_after", int(v)))
    spin_row(g, _("Turn the screen off after"), "", 0, 7200, 60,
             win.s.get("idle.screen_off", 900),
             lambda v: win.s.set("idle.screen_off", int(v)))
    spin_row(g, _("Suspend after"), _("Zero: never on its own"), 0, 14400, 300,
             win.s.get("idle.suspend_after", 0),
             lambda v: win.s.set("idle.suspend_after", int(v)))

    g = group(p, _("Night light"), "")
    switch_row(g, _("Enabled"), "", win.s.get("nightlight.enabled", True),
               lambda v: win.s.set("nightlight.enabled", v))
    spin_row(g, _("Daytime temperature"), _("Kelvin"), 3000, 6500, 100,
             win.s.get("nightlight.day_temp", 6500),
             lambda v: win.s.set("nightlight.day_temp", int(v)))
    spin_row(g, _("Night temperature"), _("Kelvin"), 2500, 6500, 100,
             win.s.get("nightlight.night_temp", 4000),
             lambda v: win.s.set("nightlight.night_temp", int(v)))

    win.add_page(p, "power", _("Power"), "preferences-system-power-symbolic")
