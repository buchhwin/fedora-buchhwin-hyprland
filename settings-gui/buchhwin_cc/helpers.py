"""Shared constants, subprocess helpers and preference-row builders.

Split out of the single file the application used to be, so that a page module
can build a row without importing the window — and so the window is not 1400
lines of everything.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent
STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "buchhwin"

FLAVOURS = ["mocha", "macchiato", "frappe", "latte"]
ACCENTS = ["rosewater", "flamingo", "pink", "mauve", "red", "maroon", "peach",
           "yellow", "green", "teal", "sky", "sapphire", "blue", "lavender"]


def run(*cmd: str) -> None:
    try:
        subprocess.run(cmd, check=False, timeout=20,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        pass


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
