"""Shared constants, subprocess helpers and preference-row builders.

Split out of the single file the application used to be, so that a page module
can build a row without importing the window — and so the window is not 1400
lines of everything.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

REPO = Path(__file__).resolve().parent.parent.parent
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "buchhwin"

def palettes() -> list[dict]:
    """Every palette on disk, newest read each call.

    Read from theme/palettes/ rather than listed here. The four Catppuccin
    names used to be a constant in this file, in bin/bhctl and in install.sh —
    three places, so a new palette was invisible in the settings window until
    all three were edited, and nothing said so.
    """
    found = []
    directory = REPO / "theme" / "palettes"
    if not directory.is_dir():
        return found
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        found.append({
            "name": data.get("name", path.stem),
            "family": data.get("family", "Catppuccin"),
            "display_name": data.get("display_name", path.stem),
            "dark": bool(data.get("dark", True)),
            "accents": data.get("accents") or sorted(data.get("colors", {})),
        })
    return found


def families() -> list[str]:
    seen: list[str] = []
    for palette in palettes():
        if palette["family"] not in seen:
            seen.append(palette["family"])
    return seen


def accents_for(flavour: str) -> list[str]:
    """The accents THIS palette offers.

    They differ: Gruvbox has no "mauve", and apply-theme.py exits on an accent
    the palette does not define. Offering all fourteen everywhere would let the
    settings window write one that cannot be rendered.
    """
    for palette in palettes():
        if palette["name"] == flavour:
            return palette["accents"]
    return ACCENTS


# Kept as the fallback for a missing or unreadable palette directory.
FLAVOURS = ["mocha", "macchiato", "frappe", "latte"]
ACCENTS = ["rosewater", "flamingo", "pink", "mauve", "red", "maroon", "peach",
           "yellow", "green", "teal", "sky", "sapphire", "blue", "lavender"]


def run(*cmd: str) -> tuple[bool, str]:
    """Run a helper. Never raises — but never hides a failure either.

    This used to send stdout and stderr to /dev/null and swallow every
    exception, which is how a generator that died with a Python traceback still
    produced a cheerful "Applied". Callers that do not care can ignore the
    result; apply() does care and reports it.
    """
    try:
        p = subprocess.run(cmd, check=False, timeout=20,
                           capture_output=True, text=True)
    except OSError as exc:
        return False, str(exc)
    except subprocess.TimeoutExpired:
        return False, "timed out"
    if p.returncode != 0:
        lines = (p.stderr or p.stdout or "").strip().splitlines()
        return False, lines[-1] if lines else f"exit {p.returncode}"
    return True, ""


def cursor_themes() -> list[str]:
    """Pointer themes actually installed, not a hard-coded list.

    A theme is a directory under an icons path that contains a cursors/ folder;
    icon themes without one would be offered and then not work.
    """
    found: set[str] = set()
    for base in (Path("/usr/share/icons"), Path.home() / ".icons",
                 Path.home() / ".local/share/icons"):
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if (entry / "cursors").is_dir():
                found.add(entry.name)
    return sorted(found) or ["breeze_cursors"]


def run_lines(cmd: list[str], timeout: int = 6) -> list[str]:
    """Run a command and return its output lines, or nothing on any failure.

    Every settings page that shows live system state uses this. A settings
    window must never hang or crash because a tool is missing or slow — an
    empty section is a fair answer, a frozen window is not.
    """
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False,
                             timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line for line in out.splitlines() if line.strip()]


def page(title: str, icon: str) -> Adw.PreferencesPage:
    return Adw.PreferencesPage(title=title, icon_name=icon)


def group(page: Adw.PreferencesPage, title: str, subtitle: str = "") -> Adw.PreferencesGroup:
    g = Adw.PreferencesGroup(title=title, description=subtitle)
    page.add(g)
    return g


def spin_row(group, title, subtitle, lo, hi, step, value, on_change) -> Adw.SpinRow:
    adj = Gtk.Adjustment(lower=lo, upper=hi, step_increment=step,
                         page_increment=step * 4, value=value)
    row = Adw.SpinRow(title=title, subtitle=subtitle, adjustment=adj)
    row.connect("changed", lambda r: on_change(r.get_value()))
    group.add(row)
    return row


def switch_row(group, title, subtitle, value, on_change) -> Adw.SwitchRow:
    row = Adw.SwitchRow(title=title, subtitle=subtitle, active=bool(value))
    row.connect("notify::active", lambda r, _p: on_change(r.get_active()))
    group.add(row)
    return row


def combo_row(group, title, subtitle, options, current, on_change) -> Adw.ComboRow:
    model = Gtk.StringList.new(options)
    row = Adw.ComboRow(title=title, subtitle=subtitle, model=model)
    if current in options:
        row.set_selected(options.index(current))
    row.connect("notify::selected",
                lambda r, _p: on_change(options[r.get_selected()]))
    group.add(row)
    return row


def slider_row(group, title, subtitle, lo, hi, step, value, on_change, digits=2):
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    adj = Gtk.Adjustment(lower=lo, upper=hi, step_increment=step, value=value)
    scale = Gtk.Scale(adjustment=adj, digits=digits, draw_value=True,
                      value_pos=Gtk.PositionType.RIGHT, hexpand=True,
                      width_request=260)
    scale.connect("value-changed", lambda s: on_change(round(s.get_value(), 2)))
    row.add_suffix(scale)
    group.add(row)
    return row


def pinnable_apps() -> list[str]:
    """Desktop entry ids for the dock's pinned list.

    Named apart from the defaults page's _installed_apps on purpose: that one
    returns (name, command) pairs, this one returns ids. Both were called
    _installed_apps in the same class, so Python kept only the second and the
    dock's list was silently handed pairs where it expected names. Splitting
    the file is what made the collision visible.
    """
    found: set[str] = set()
    for directory in (Path("/usr/share/applications"),
                      Path("/usr/local/share/applications"),
                      Path.home() / ".local/share/applications",
                      Path("/var/lib/flatpak/exports/share/applications")):
        if not directory.is_dir():
            continue
        for entry in directory.glob("*.desktop"):
            try:
                if "NoDisplay=true" in entry.read_text(errors="replace"):
                    continue
            except OSError:
                continue
            found.add(entry.stem)
    return sorted(found)
