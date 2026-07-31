"""Settings page: input.

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
    p = page(_("Input"), "input-mouse-symbolic")

    g = group(p, _("Keyboard"), "")
    combo_row(g, _("Layout"), "", ["de", "us", "gb", "fr", "es", "it", "ch"],
              win.s.get("input.kb_layout", "de"),
              lambda v: win.s.set("input.kb_layout", v))
    spin_row(g, _("Repeat rate"), _("Characters per second"), 10, 80, 1,
             win.s.get("input.repeat_rate", 40),
             lambda v: win.s.set("input.repeat_rate", int(v)))
    spin_row(g, _("Repeat delay"), _("Milliseconds"), 150, 800, 10,
             win.s.get("input.repeat_delay", 300),
             lambda v: win.s.set("input.repeat_delay", int(v)))

    g = group(p, _("Mouse and touchpad"), "")
    slider_row(g, _("Sensitivity"), _("-1 slower, +1 faster"), -1.0, 1.0, 0.05,
               win.s.get("input.sensitivity", 0),
               lambda v: win.s.set("input.sensitivity", v))
    switch_row(g, _("Natural scrolling"), "",
               win.s.get("input.natural_scroll", True),
               lambda v: win.s.set("input.natural_scroll", v))
    switch_row(g, _("Tap to click"), "",
               win.s.get("input.tap_to_click", True),
               lambda v: win.s.set("input.tap_to_click", v))
    switch_row(g, _("Focus follows the mouse"), "",
               bool(win.s.get("input.follow_mouse", 1)),
               lambda v: win.s.set("input.follow_mouse", 1 if v else 0))

    win.add_page(p, "input", _("Input"), "input-mouse-symbolic")

# -- Sound ---------------------------------------------------------------
