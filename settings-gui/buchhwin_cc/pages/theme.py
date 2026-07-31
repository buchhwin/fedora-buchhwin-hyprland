"""Settings page: theme.

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
    p = page(_("Theme"), "applications-graphics-symbolic")
    g = group(p, _("Catppuccin"),
              _("One click recolours Hyprland, the bar, notifications, "
                "menus, the terminal, GTK, Qt, icons and the cursor."))

    combo_row(g, _("Flavour"), _("Latte is the light one"), FLAVOURS,
              win.s.get("theme.flavour", "mocha"),
              lambda v: win.s.set("theme.flavour", v))
    combo_row(g, _("Accent colour"), "", ACCENTS,
              win.s.get("theme.accent", "mauve"),
              lambda v: win.s.set("theme.accent", v))

    row = Adw.ActionRow(
        title=_("Apply theme now"),
        subtitle=_("Re-renders every configuration and reloads what is running"))
    btn = Gtk.Button(label=_("Render"), valign=Gtk.Align.CENTER)
    btn.add_css_class("suggested-action")
    btn.connect("clicked", lambda *a, _f=_render_theme: _f(win, *a[1:]))
    row.add_suffix(btn)
    g.add(row)

    g2 = group(p, _("Wallpaper"), "")
    switch_row(g2, _("Wallpaper follows the flavour"),
               _("Switching to Latte also picks a light wallpaper"),
               win.s.get("wallpaper.follow_theme", True),
               lambda v: win.s.set("wallpaper.follow_theme", v))

    win.add_page(p, "theme", _("Theme"), "applications-graphics-symbolic")


def _render_theme(win, _btn):
    win.s.save()
    flavour = win.s.get("theme.flavour", "mocha")
    accent = win.s.get("theme.accent", "mauve")
    subprocess.run([sys.executable, str(REPO / "theme" / "apply-theme.py"),
                    "--flavour", flavour, "--accent", accent],
                   check=False)
    run("hyprctl", "reload")
    win.toast(_("Theme: {} / {}").format(flavour, accent))
