"""Settings page: displays.

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
    p = page(_("Displays"), "video-display-symbolic")

    g = group(p, _("Connected displays"),
              _("Read from the compositor. Change them in settings.lua "
                "under monitors; this page shows what is actually active."))
    import json as _json
    raw = "\n".join(run_lines(["hyprctl", "-j", "monitors"]))
    try:
        monitors = _json.loads(raw) if raw.strip() else []
    except ValueError:
        monitors = []
    if monitors:
        for m in monitors:
            g.add(Adw.ActionRow(
                title=f"{m.get('name', '?')} — {m.get('description', '')}".strip(" —"),
                subtitle=(f"{m.get('width')}×{m.get('height')} "
                          f"@ {round(m.get('refreshRate', 0))} Hz · "
                          f"scale {m.get('scale')} · "
                          f"at {m.get('x')},{m.get('y')}")))
    else:
        g.add(Adw.ActionRow(title=_("No displays reported")))

    win.add_page(p, "displays", _("Displays"), "video-display-symbolic")

# -- Applications --------------------------------------------------------
