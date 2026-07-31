"""Settings page: look.

Extracted from the single 1392-line file the settings app used to be. Each page
is one module exporting build(win); `win` is the Window, which still owns the
shared helpers (toast, add_page, _launch_row, _spawn) so a page can use them
without importing the window back and creating a cycle.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

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


def build(win):
    p = page(_("Look"), "preferences-desktop-appearance-symbolic")

    g = group(p, _("Windows"),
              _("Borders, gaps and corners. Changes apply on Apply."))
    spin_row(g, _("Border width"), _("Pixels"), 0, 12, 1,
             win.s.get("look.border_size", 2),
             lambda v: win.s.set("look.border_size", int(v)))
    spin_row(g, _("Corner radius"), _("Pixels"), 0, 30, 1,
             win.s.get("look.rounding", 12),
             lambda v: win.s.set("look.rounding", int(v)))
    spin_row(g, _("Gap between windows"), _("Pixels"), 0, 40, 1,
             win.s.get("look.gaps_in", 5),
             lambda v: win.s.set("look.gaps_in", int(v)))
    spin_row(g, _("Gap to the screen edge"), _("Pixels"), 0, 60, 1,
             win.s.get("look.gaps_out", 12),
             lambda v: win.s.set("look.gaps_out", int(v)))

    g = group(p, _("Transparency"),
              _("The focused window stays opaque on purpose — that is the "
                "one you are reading."))
    slider_row(g, _("Unfocused windows"), "", 0.5, 1.0, 0.01,
               win.s.get("look.inactive_opacity", 0.94),
               lambda v: win.s.set("look.inactive_opacity", v))
    slider_row(g, _("Terminal"), "", 0.5, 1.0, 0.01,
               win.s.get("look.terminal_opacity", 0.90),
               lambda v: win.s.set("look.terminal_opacity", v))

    g = group(p, _("Effects"),
              _("Blur applies to the bar, menus and the terminal — not to "
                "every window, which costs performance for no visual gain."))
    switch_row(g, _("Blur"), "", win.s.get("look.blur", True),
               lambda v: win.s.set("look.blur", v))
    spin_row(g, _("Blur strength"), "", 0, 20, 1,
             win.s.get("look.blur_size", 6),
             lambda v: win.s.set("look.blur_size", int(v)))
    spin_row(g, _("Blur passes"), _("More is softer and more expensive"), 1, 4, 1,
             win.s.get("look.blur_passes", 2),
             lambda v: win.s.set("look.blur_passes", int(v)))
    switch_row(g, _("Shadows"), "", win.s.get("look.shadow", True),
               lambda v: win.s.set("look.shadow", v))
    switch_row(g, _("Animations"), "", win.s.get("look.animations", True),
               lambda v: win.s.set("look.animations", v))

    g = group(p, _("Windows"),
              _("Tiling is the default. A workspace switched to floating "
                "behaves like Windows: windows drag freely and snap "
                "magnetically to edges and to each other."))
    switch_row(g, _("Magnetic snapping"),
               _("Floating windows click into place near an edge"),
               win.s.get("layout.snap", True),
               lambda v: win.s.set("layout.snap", v))
    spin_row(g, _("Snap distance"), _("Pixels"), 0, 40, 1,
             win.s.get("layout.snap_window_gap", 12),
             lambda v: win.s.set("layout.snap_window_gap", int(v)))
    combo_row(g, _("Tiling layout"), _("dwindle splits, master keeps one big"),
              ["dwindle", "master"], win.s.get("layout.default", "dwindle"),
              lambda v: win.s.set("layout.default", v))

    floating = win.s.get("layout.floating_workspaces", []) or []
    row = Adw.ActionRow(
        title=_("Floating workspaces"),
        subtitle=(", ".join(str(x) for x in floating) if floating
                  else _("none — SUPER+SHIFT+Space switches the current one")))
    row.set_subtitle_lines(0)
    g.add(row)

    spin_row(g, _("Gap when only one window is open"), _("Pixels"), 0, 40, 1,
             win.s.get("look.gaps_single", 4),
             lambda v: win.s.set("look.gaps_single", int(v)))

    g = group(p, _("Mouse pointer"),
              _("Any theme under /usr/share/icons with a cursors folder."))
    combo_row(g, _("Pointer theme"), "", cursor_themes(),
              win.s.get("look.cursor_theme", "breeze_cursors"),
              lambda v: win.s.set("look.cursor_theme", v))
    spin_row(g, _("Pointer size"), _("Pixels"), 16, 64, 4,
             win.s.get("look.cursor_size", 24),
             lambda v: win.s.set("look.cursor_size", int(v)))

    g = group(p, _("Dock"),
              _("A second bar at the bottom edge showing open windows."))
    switch_row(g, _("Show the dock"), "",
               win.s.get("dock.enabled", False),
               lambda v: win.s.set("dock.enabled", v))
    combo_row(g, _("Edge"), "", ["bottom", "top", "left", "right"],
              win.s.get("dock.position", "bottom"),
              lambda v: win.s.set("dock.position", v))
    spin_row(g, _("Icon size"), _("Pixels"), 16, 64, 4,
             win.s.get("dock.icon_size", 32),
             lambda v: win.s.set("dock.icon_size", int(v)))
    win._dock_pins = group(p, _("Pinned applications"),
                            _("Always in the dock, whether they are running "
                              "or not."))
    _rebuild_pins(win)

    switch_row(g, _("Let windows tile underneath"),
               _("Waybar has no true autohide. This drops the reserved "
                 "space so the dock floats over your windows instead of "
                 "pushing them up — it does not slide away."),
               win.s.get("dock.autohide", False),
               lambda v: win.s.set("dock.autohide", v))

    g = group(p, _("Profile"),
              _("Work is quick and restrained. Showcase is slower with more "
                "blur and deeper shadows — for screenshots and video."))
    combo_row(g, _("Visual profile"), "", ["work", "showcase"],
              win.s.get("look.profile", "work"),
              lambda v: win.s.set("look.profile", v))

    win.add_page(p, "look", _("Look"), "preferences-desktop-appearance-symbolic")

# -- dock pins -----------------------------------------------------------


def _rebuild_pins(win):
    """Refill the pinned list.

    The rows are tracked in a list rather than walked with get_first_child():
    AdwPreferencesGroup returns its own internal box from that, so removing
    "the first child" removes nothing, the loop never ends, and the whole
    window never appears. It failed exactly that way — 30 seconds of nothing
    and a stream of "tried to remove non-child" criticals.
    """
    g = win._dock_pins
    for row in getattr(win, "_dock_pin_rows", []):
        g.remove(row)
    win._dock_pin_rows = []

    pinned = win.s.get("dock.pinned", []) or []
    for app in pinned:
        # Escaped: a desktop id can contain & and Adw parses titles as markup.
        row = Adw.ActionRow(title=GLib.markup_escape_text(app))
        remove = Gtk.Button(icon_name="list-remove-symbolic",
                            valign=Gtk.Align.CENTER)
        remove.connect("clicked", lambda *a, _f=_on_unpin: _f(win, *a[1:]), app)
        row.add_suffix(remove)
        g.add(row)
        win._dock_pin_rows.append(row)

    add = Adw.ActionRow(title=_("Add an application"))
    button = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER)
    button.connect("clicked", lambda *a, _f=_on_pin_add: _f(win, *a[1:]))
    add.add_suffix(button)
    g.add(add)
    win._dock_pin_rows.append(add)



def _on_pin_add(win, _button):
    apps = [a for a in pinnable_apps()
            if a not in (win.s.get("dock.pinned", []) or [])]
    if not apps:
        win.toast(_("Everything installed is already pinned"))
        return

    dialog = Adw.AlertDialog(heading=_("Add to the dock"))
    combo = Adw.ComboRow(title=_("Application"),
                         model=Gtk.StringList.new(apps))
    listbox = Adw.PreferencesGroup()
    listbox.add(combo)
    dialog.set_extra_child(listbox)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("add", _("Add"))
    dialog.set_default_response("add")

    def answered(_d, response):
        if response == "add":
            pinned = list(win.s.get("dock.pinned", []) or [])
            pinned.append(apps[combo.get_selected()])
            win.s.set("dock.pinned", pinned)
            _rebuild_pins(win)

    dialog.connect("response", answered)
    dialog.present(win)


def _on_unpin(win, _button, app: str):
    pinned = [a for a in (win.s.get("dock.pinned", []) or []) if a != app]
    win.s.set("dock.pinned", pinned)
    _rebuild_pins(win)
