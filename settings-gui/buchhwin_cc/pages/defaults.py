"""Settings page: defaults.

Extracted from the single 1392-line file the settings app used to be. Each page
is one module exporting build(win); `win` is the Window, which still owns the
shared helpers (toast, add_page, _launch_row, _spawn) so a page can use them
without importing the window back and creating a cycle.
"""

from __future__ import annotations

import os
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
    p = page(_("Default apps"), "emblem-default-symbolic")
    g = group(p, _("Programs the shortcuts use"),
              _("Changing one here changes the shortcut immediately — "
                "SUPER+B starts whatever the browser is set to."))

    apps = _installed_apps()
    names = [n for n, _c in apps]
    by_name = dict(apps)
    by_cmd = {c: n for n, c in apps}

    fields = [
        ("programs.terminal",     _("Terminal"),      "SUPER+Return"),
        ("programs.browser",      _("Browser"),       "SUPER+B"),
        ("programs.file_manager", _("File manager"),  "SUPER+E"),
        ("programs.editor",       _("Editor"),        "SUPER+SHIFT+C"),
        ("programs.calendar",     _("Calendar"),      ""),
        ("programs.mail",         _("Mail"),          ""),
        ("programs.image_viewer", _("Image viewer"),  ""),
        ("programs.music",        _("Music"),         ""),
    ]
    for key, title, shortcut in fields:
        current_cmd = win.s.get(key, "") or ""
        current_name = by_cmd.get(current_cmd, _("Custom…"))
        options = [*names, _("Custom…")]
        row = combo_row(g, title, shortcut, options,
                        current_name if current_name in options else _("Custom…"),
                        lambda v, k=key, m=by_name: win._set_default(k, m.get(v)))
        if current_name == _("Custom…"):
            row.set_subtitle(f"{shortcut}  ·  {current_cmd}" if shortcut else current_cmd)

    g2 = group(p, _("File associations"),
               _("Also set the system default, so a double-click in the "
                 "file manager opens the same program. Without this you "
                 "change the browser and links keep opening the old one."))
    row = Adw.ActionRow(title=_("Apply to file associations"))
    btn = Gtk.Button(label=_("Apply"), valign=Gtk.Align.CENTER)
    btn.connect("clicked", win._apply_mime)
    row.add_suffix(btn)
    g2.add(row)

    win.add_page(p, "defaults", _("Default apps"), "emblem-default-symbolic")


def _installed_apps() -> list[tuple[str, str]]:
    """(Display name, command) for everything with a .desktop entry.

    Read from the system rather than hardcoded: offering the user a browser
    that is not installed is worse than offering none.
    """
    seen: dict[str, str] = {}
    for base in ("/usr/share/applications",
                 "/usr/local/share/applications",
                 str(Path(DATA_HOME := os.environ.get(
                     "XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"),
                 "/var/lib/flatpak/exports/share/applications"):
        d = Path(base)
        if not d.is_dir():
            continue
        for entry in sorted(d.glob("*.desktop")):
            try:
                text = entry.read_text(errors="replace")
            except OSError:
                continue
            if "NoDisplay=true" in text:
                continue
            name = cmd = ""
            for line in text.splitlines():
                if line.startswith("Name=") and not name:
                    name = line[5:].strip()
                elif line.startswith("Exec=") and not cmd:
                    # Strip the %f/%U placeholders — they are for the
                    # desktop file, not for a shell.
                    cmd = " ".join(w for w in line[5:].split()
                                   if not w.startswith("%"))
                if name and cmd:
                    break
            if name and cmd and name not in seen:
                seen[name] = cmd
    return sorted(seen.items())
