"""Settings page: wallpaper.

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
    p = page(_("Wallpaper"), "preferences-desktop-wallpaper-symbolic")
    g = group(p, _("Wallpaper"), "")

    current = win.s.get("wallpaper.path", "") or _("(matching the flavour)")
    row = Adw.ActionRow(title=_("Current"), subtitle=current)
    pick = Gtk.Button(label=_("Choose…"), valign=Gtk.Align.CENTER)
    pick.connect("clicked", lambda _b: _pick_wallpaper(win, row))
    row.add_suffix(pick)
    g.add(row)

    grid_btn = Adw.ActionRow(
        title=_("Thumbnail picker"),
        subtitle=_("The same grid as SUPER+W"))
    b = Gtk.Button(label=_("Open"), valign=Gtk.Align.CENTER)
    b.connect("clicked",
              lambda _b: run(str(REPO / "scripts" / "wallpaper-menu.sh")))
    grid_btn.add_suffix(b)
    g.add(grid_btn)

    combo_row(g, _("Transition"), "",
              ["grow", "wipe", "fade", "center", "outer", "random"],
              win.s.get("wallpaper.transition", "grow"),
              lambda v: win.s.set("wallpaper.transition", v))

    win.add_page(p, "wallpaper", _("Wallpaper"),
                  "preferences-desktop-wallpaper-symbolic")


def _pick_wallpaper(win, row):
    dialog = Gtk.FileDialog(title=_("Choose a wallpaper"))
    images = Gtk.FileFilter()
    images.set_name(_("Images"))
    for pattern in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
        images.add_pattern(pattern)
    dialog.set_default_filter(images)

    def done(dlg, result):
        try:
            gfile = dlg.open_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path:
            return
        win.s.set("wallpaper.path", path)
        row.set_subtitle(path)
        subprocess.run([str(REPO / "scripts" / "wallpaper.sh"), "set", path],
                       check=False)

    dialog.open(win, None, done)
