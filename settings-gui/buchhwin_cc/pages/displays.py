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
# S reads settings.lua straight from disk: monitors.py writes the file
# behind this window's back, so the cached copy would be stale.
from ..store import S  # noqa: E402


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

    # --- profiles -----------------------------------------------------------
    win._monitor_group = group(
        p, _("Arrangements"),
        _("Save how the screens are laid out and put it back later. Matched on "
          "which screens are plugged in, not on which port they are in — so "
          "docking restores the right one even if a cable moved."))
    win._monitor_rows = []
    _rebuild_profiles(win)

    row = Adw.EntryRow(title=_("Save the current arrangement as"))
    save = Gtk.Button(label=_("Save"), valign=Gtk.Align.CENTER)
    save.add_css_class("suggested-action")
    save.connect("clicked", lambda _b, r=row: _save_profile(win, r))
    row.add_suffix(save)
    win._monitor_group.add(row)
    win._monitor_rows.append(row)

    win.add_page(p, "displays", _("Displays"), "video-display-symbolic")


def _monitors_script(*args: str):
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "monitors.py"), *args],
        capture_output=True, text=True, check=False, timeout=20)


def _rebuild_profiles(win) -> None:
    for row in win._monitor_rows:
        win._monitor_group.remove(row)
    win._monitor_rows = []

    saved = (win.s.get("monitor_profiles", {}) or {})
    if not saved:
        row = Adw.ActionRow(title=_("No arrangements saved yet"))
        win._monitor_group.add(row)
        win._monitor_rows.append(row)
        return

    for name, entry in saved.items():
        screens = entry.get("screens") or []
        row = Adw.ActionRow(title=name,
                            subtitle=", ".join(screens) or _("no screens recorded"))
        row.set_subtitle_lines(0)
        apply_btn = Gtk.Button(label=_("Apply"), valign=Gtk.Align.CENTER)
        apply_btn.connect("clicked", lambda _b, n=name: _apply_profile(win, n))
        row.add_suffix(apply_btn)
        remove = Gtk.Button(icon_name="user-trash-symbolic",
                            valign=Gtk.Align.CENTER)
        remove.connect("clicked", lambda _b, n=name: _remove_profile(win, n))
        row.add_suffix(remove)
        win._monitor_group.add(row)
        win._monitor_rows.append(row)


def _save_profile(win, row) -> None:
    name = row.get_text().strip()
    if not name:
        win.toast(_("Give the arrangement a name first"))
        return
    _monitors_script("save", name)
    # The script wrote settings.lua directly, so the window's copy is stale.
    win.s.data = S.read()
    row.set_text("")
    _rebuild_profiles(win)
    win.toast(_("Saved as {}").format(name))


def _apply_profile(win, name: str) -> None:
    _monitors_script("apply", name)
    win.s.data = S.read()
    win.toast(_("Applied {}").format(name))


def _remove_profile(win, name: str) -> None:
    _monitors_script("remove", name)
    win.s.data = S.read()
    _rebuild_profiles(win)
    win.toast(_("Removed {}").format(name))

# -- Applications --------------------------------------------------------
