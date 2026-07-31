"""Settings page: apps.

Which applications appear in the launcher. A stock system offers dozens of
entries that exist only so other software can find a handler, and the installer
hides a fixed list of those; this page is where you hide the rest — the ones
only you know you will never open.

Hiding writes a shadowing .desktop with NoDisplay=true into
~/.local/share/applications. Nothing is uninstalled, nothing is deleted, and
un-hiding is removing one file. All of that lives in scripts/menu-cleanup.py so
that hiding means the same thing whether it was asked for here or on the
command line.
"""

from __future__ import annotations

import json
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from ..helpers import REPO, group, page, run_lines  # noqa: E402


def _script() -> str:
    return str(REPO / "scripts" / "menu-cleanup.py")


def _entries() -> list[dict]:
    """Every listable application with its hidden state.

    Deliberately NOT pinnable_apps(): that filters NoDisplay=true, which is
    exactly what hiding sets — a list built on it could show you what to hide
    but never what to bring back.
    """
    try:
        out = subprocess.run([sys.executable, _script(), "--all-json"],
                             capture_output=True, text=True, check=False,
                             timeout=20).stdout
        return json.loads(out) if out.strip() else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def build(win):
    p = page(_("Applications"), "view-grid-symbolic")

    g = group(p, _("Launcher"),
              _("A stock system offers dozens of entries that exist only so "
                "other software can find a handler — one per image format, "
                "certificate prompts, geolocation agents. Those are hidden "
                "already. Below you can hide anything else. Nothing is "
                "uninstalled."))

    hidden = len(run_lines([sys.executable, _script(), "--list"])) - 1
    row = Adw.ActionRow(
        title=_("Entries hidden by the installer"),
        subtitle=_("%d entries are hidden from the launcher") % max(hidden, 0))
    button = Gtk.Button(label=_("Show them all again"), valign=Gtk.Align.CENTER)
    button.connect("clicked", lambda _b: _restore_all(win))
    row.add_suffix(button)
    g.add(row)

    # --- the list ---------------------------------------------------------
    win._apps_group = group(
        p, _("Show in the launcher"),
        _("Switch one off and it disappears from the launcher, the category "
          "browser and the default-application lists. It keeps working as a "
          "file handler, and anything that starts it by name still can."))

    search = Gtk.SearchEntry(placeholder_text=_("Filter applications"))
    search.set_margin_top(6)
    search.set_margin_bottom(6)
    search.connect("search-changed", lambda e: _rebuild(win, e.get_text()))
    win._apps_group.add(search)

    win._apps_rows = []
    _rebuild(win, "")

    g = group(p, _("More"))
    win._launch_row(g, _("Installed applications"),
                    _("Everything with a launcher entry"),
                    ["rofi", "-show", "drun"])

    win.add_page(p, "apps", _("Applications"), "view-grid-symbolic")


def _rebuild(win, needle: str) -> None:
    """Refill the switch list.

    Rows are tracked in a list rather than walked off the group: asking an
    AdwPreferencesGroup for its first child returns its own internal box, so
    "remove the first child until there are none" removes nothing and never
    finishes. That mistake once cost a window that simply never appeared.
    """
    for row in win._apps_rows:
        win._apps_group.remove(row)
    win._apps_rows = []

    needle = needle.strip().lower()
    entries = [e for e in _entries()
               if not needle
               or needle in e["name"].lower()
               or needle in e["id"].lower()]

    if not entries:
        row = Adw.ActionRow(title=_("Nothing matches"), subtitle=needle)
        win._apps_group.add(row)
        win._apps_rows.append(row)
        return

    # A hundred switches make the page unusable; the filter above is how you
    # reach the rest. The count says so rather than pretending this is all.
    shown = entries[:60]
    for entry in shown:
        row = Adw.SwitchRow(title=entry["name"], subtitle=entry["id"],
                            active=not entry["hidden"])
        row.connect("notify::active",
                    lambda r, _p, e=entry: _toggle(win, e["id"], r.get_active()))
        win._apps_group.add(row)
        win._apps_rows.append(row)

    if len(entries) > len(shown):
        more = Adw.ActionRow(
            title=_("%d more") % (len(entries) - len(shown)),
            subtitle=_("Type in the box above to narrow the list"))
        win._apps_group.add(more)
        win._apps_rows.append(more)


def _toggle(win, app_id: str, visible: bool) -> None:
    flag = "--show" if visible else "--hide"
    try:
        subprocess.run([sys.executable, _script(), flag, app_id],
                       capture_output=True, check=False, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as exc:
        win.toast(_("Could not change {}: {}").format(app_id, exc))
        return
    win.toast(_("{} is now visible").format(app_id) if visible
              else _("{} is hidden").format(app_id))


def _restore_all(win) -> None:
    subprocess.run([sys.executable, _script(), "--restore"], check=False)
    win.toast(_("All entries are visible again"))
    _rebuild(win, "")
