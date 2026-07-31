"""Settings page: theme.

Extracted from the single 1392-line file the settings app used to be. Each page
is one module exporting build(win); `win` is the Window, which still owns the
shared helpers (toast, add_page, _launch_row, _spawn) so a page can use them
without importing the window back and creating a cycle.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk

from ..helpers import (  # noqa: F401
    ACCENTS,
    FLAVOURS,
    REPO,
    STATE,
    accents_for,
    combo_row,
    cursor_themes,
    families,
    group,
    page,
    palettes,
    pinnable_apps,
    run,
    run_lines,
    slider_row,
    spin_row,
    switch_row,
)


def build(win):
    p = page(_("Theme"), "applications-graphics-symbolic")
    g = group(p, _("Colours"),
              _("One click recolours Hyprland, the bar, notifications, "
                "menus, the terminal, GTK, Qt, icons and the cursor."))

    # Family, then variant, then accent — all read from theme/palettes/, so a
    # palette dropped in there appears here without touching this file.
    available = palettes()
    current = win.s.get("theme.flavour", "mocha")
    here = next((x for x in available if x["name"] == current), None)
    current_family = here["family"] if here else "Catppuccin"

    win._theme_variant_row = None
    win._theme_accent_row = None

    combo_row(g, _("Colour family"), "", families() or ["Catppuccin"],
              current_family,
              lambda v: _on_family(win, g, v))

    _add_variant_rows(win, g, current_family, current)

    row = Adw.ActionRow(
        title=_("Variants"),
        subtitle=", ".join(f'{x["display_name"]}{" (light)" if not x["dark"] else ""}'
                           for x in available if x["family"] == current_family))
    row.set_subtitle_lines(0)
    g.add(row)

    row = Adw.ActionRow(
        title=_("Apply theme now"),
        subtitle=_("Re-renders every configuration and reloads what is running"))
    btn = Gtk.Button(label=_("Render"), valign=Gtk.Align.CENTER)
    btn.add_css_class("suggested-action")
    btn.connect("clicked", lambda *a, _f=_render_theme: _f(win, *a[1:]))
    row.add_suffix(btn)
    g.add(row)

    g2 = group(p, _("From the wallpaper"),
               _("Derive the whole palette from the picture on your desktop. "
                 "Every change follows, the slideshow included. The named "
                 "colours keep their identity — red stays red — and take their "
                 "vividness from the image, so error messages and syntax "
                 "highlighting stay readable."))
    switch_row(g2, _("Colours follow the wallpaper"),
               _("Needs matugen") if not _have_matugen() else "",
               win.s.get("theme.from_wallpaper", False),
               lambda v: win.s.set("theme.from_wallpaper", v))

    g2 = group(p, _("Wallpaper"), "")
    switch_row(g2, _("Wallpaper follows the flavour"),
               _("Switching to Latte also picks a light wallpaper"),
               win.s.get("wallpaper.follow_theme", True),
               lambda v: win.s.set("wallpaper.follow_theme", v))

    win.add_page(p, "theme", _("Theme"), "applications-graphics-symbolic")


def _have_matugen() -> bool:
    return shutil.which("matugen") is not None


def _add_variant_rows(win, g, family: str, flavour: str) -> None:
    """The variant and accent combos for one family.

    Rebuilt when the family changes: Gruvbox has no "mauve", and
    apply-theme.py exits on an accent its palette does not define — so the list
    has to follow the palette rather than offer all fourteen everywhere.
    """
    members = [x for x in palettes() if x["family"] == family]
    names = [x["name"] for x in members] or [flavour]
    if flavour not in names:
        flavour = names[0]
        win.s.set("theme.flavour", flavour)

    if win._theme_variant_row is not None:
        g.remove(win._theme_variant_row)
    if win._theme_accent_row is not None:
        g.remove(win._theme_accent_row)

    win._theme_variant_row = combo_row(
        g, _("Variant"), _("Light variants say so in the list below"),
        names, flavour,
        lambda v: _on_variant(win, g, family, v))

    allowed = accents_for(flavour)
    accent = win.s.get("theme.accent", "mauve")
    if accent not in allowed:
        accent = allowed[0]
        win.s.set("theme.accent", accent)
    win._theme_accent_row = combo_row(
        g, _("Accent colour"), "", allowed, accent,
        lambda v: win.s.set("theme.accent", v))


def _on_family(win, g, family: str) -> None:
    members = [x for x in palettes() if x["family"] == family]
    if members:
        win.s.set("theme.flavour", members[0]["name"])
    _add_variant_rows(win, g, family, win.s.get("theme.flavour", "mocha"))


def _on_variant(win, g, family: str, flavour: str) -> None:
    win.s.set("theme.flavour", flavour)
    _add_variant_rows(win, g, family, flavour)


def _render_theme(win, _btn):
    win.s.save()
    flavour = win.s.get("theme.flavour", "mocha")
    accent = win.s.get("theme.accent", "mauve")
    subprocess.run([sys.executable, str(REPO / "theme" / "apply-theme.py"),
                    "--flavour", flavour, "--accent", accent],
                   check=False)
    run("hyprctl", "reload")
    win.toast(_("Theme: {} / {}").format(flavour, accent))
