"""Settings page: welcome.

Shown first on a fresh install, and reachable afterwards from the sidebar. A
tiling desktop with a compositor most people have never used needs five minutes
of orientation, and putting that in a README nobody opens is the same as not
writing it.

Not a wizard. It asks nothing and changes nothing by itself: every row either
explains a key or opens the page that does the work. A first-run wizard that
demands decisions before you have seen the desktop asks them in the worst
possible order.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..helpers import STATE, group, page

# Written once the page has been seen, so it stops being the landing page.
SEEN = "welcome-seen"


def seen() -> bool:
    return (STATE / SEEN).exists()


def mark_seen() -> None:
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        (STATE / SEEN).touch()
    except OSError:
        pass


def build(win):
    p = page(_("Welcome"), "emblem-favorite-symbolic")

    g = group(p, _("The five keys that matter"),
              _("Everything else is in Keys, and SUPER+/ shows the whole list "
                "at any time."))
    for keys, what in (
            ("SUPER + Return", _("A terminal")),
            ("SUPER + D", _("The launcher — applications, files, windows, sums")),
            ("SUPER + Q", _("Close the focused window")),
            ("SUPER + Tab", _("Everything that is open, on one screen")),
            ("SUPER + /", _("Every shortcut there is"))):
        row = Adw.ActionRow(title=what, subtitle=keys)
        row.add_css_class("property")
        g.add(row)

    g = group(p, _("Two things that surprise people"),
              _("Neither is a fault; both are how a tiling desktop works."))
    g.add(Adw.ActionRow(
        title=_("Windows arrange themselves"),
        subtitle=_("Open two and the screen splits. To drag windows around "
                   "freely instead, SUPER+SHIFT+Space makes the current "
                   "workspace floating — the rest stay as they are.")))
    g.add(Adw.ActionRow(
        title=_("Minimize puts a window on a shelf"),
        subtitle=_("There is nowhere to minimize TO in a tiling layout, so "
                   "minimized windows go to a hidden workspace. The dock at "
                   "the bottom lists them, and SUPER+SHIFT+M shows the shelf.")))

    g = group(p, _("Make it yours"),
              _("The three that change the most for the least effort."))
    _jump_row(win, g, _("Colours and wallpaper"), "theme")
    _jump_row(win, g, _("Keyboard shortcuts"), "keys")
    _jump_row(win, g, _("Bar, dock, borders and blur"), "look")

    g = group(p, _("If something looks wrong"))
    g.add(Adw.ActionRow(
        title=_("bhctl doctor"),
        subtitle=_("Checks the services, the config and the theme, and says "
                   "what is off. Run it in a terminal.")))

    win.add_page(p, "welcome", _("Welcome"), "emblem-favorite-symbolic")
    mark_seen()


def _jump_row(win, g, title: str, page_name: str) -> None:
    row = Adw.ActionRow(title=title)
    button = Gtk.Button(label=_("Open"), valign=Gtk.Align.CENTER)
    button.connect("clicked", lambda _b: _jump(win, page_name))
    row.add_suffix(button)
    g.add(row)


def _jump(win, page_name: str) -> None:
    index = 0
    while (row := win.sidebar.get_row_at_index(index)) is not None:
        if row.get_name() == page_name:
            win.sidebar.select_row(row)
            return
        index += 1
