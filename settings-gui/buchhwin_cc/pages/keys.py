"""Settings page: keys.

Extracted from the single 1392-line file the settings app used to be. Each page
is one module exporting build(win); `win` is the Window, which still owns the
shared helpers (toast, add_page, _launch_row, _spawn) so a page can use them
without importing the window back and creating a cycle.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..helpers import (  # noqa: F401
    ACCENTS,
    FLAVOURS,
    REPO,
    STATE,
    combo_row,
    cursor_themes,
    group,
    page,
    pinnable_apps,
    run,
    run_lines,
    slider_row,
    spin_row,
    switch_row,
)
from ..keycapture import KeyCaptureDialog


def build(win):
    p = page(_("Keys"), "input-keyboard-symbolic")
    win.keys_group = group(
        p, _("Key bindings"),
        _("Click a binding to record a new combination. Conflicts are "
          "flagged straight away."))
    _rebuild_keys(win)
    win.add_page(p, "keys", _("Keys"), "input-keyboard-symbolic")


def _rebuild_keys(win):
    while (child := win.keys_group.get_first_child()) is not None:
        # PreferencesGroup wraps its rows; remove only real rows.
        if isinstance(child, Adw.PreferencesRow):
            win.keys_group.remove(child)
        else:
            break
    for index, bind in enumerate(win.s.get("binds", []) or []):
        win.keys_group.add(_key_row(win, index, bind))


def _key_row(win, index: int, bind: dict) -> Adw.ActionRow:
    desc = bind.get("desc") or bind.get("arg", "")
    row = Adw.ActionRow(title=desc, subtitle=bind.get("arg", ""))
    label = Gtk.Label(label=bind.get("key", ""))
    label.add_css_class("dim-label")
    label.add_css_class("monospace")
    row.add_suffix(label)

    btn = Gtk.Button(icon_name="document-edit-symbolic",
                     valign=Gtk.Align.CENTER, tooltip_text=_("Record"))
    btn.add_css_class("flat")

    def record(_b):
        def captured(combo: str):
            clash = [b for i, b in enumerate(win.s.get("binds", []) or [])
                     if b.get("key") == combo and i != index]
            win.s.set(f"binds.{index}.key", combo)
            label.set_label(combo)
            if clash:
                other = clash[0].get("desc") or clash[0].get("arg", "?")
                win.toast(_("{} is already used for “{}”").format(combo, other))
                label.add_css_class("error")
            else:
                label.remove_css_class("error")
        KeyCaptureDialog(win, captured).present()

    btn.connect("clicked", record)
    row.add_suffix(btn)
    return row
