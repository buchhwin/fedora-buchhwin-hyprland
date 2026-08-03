"""Settings page: displays.

This page used to only LIST the screens. Its own subtitle said so — "change them
in settings.lua under monitors" — which meant resolution, refresh rate and scale
were reachable with a text editor and nowhere else. That is fine until the
scale comes out wrong, and then the one thing you need is the one thing you
cannot do from the desktop you are looking at.

Everything is applied through scripts/monitors.py, which writes settings.lua and
reloads. ⚠️ Not through `hyprctl keyword monitor`: that does nothing under the
Lua config provider, and a resolution that lasts until the next reload is not a
resolution.

Every change is followed by a countdown that puts it back unless it is
confirmed. A mode the screen cannot show, or a scale Hyprland rejects, leaves a
display you cannot read — and the button to undo it would be on that display.
"""

from __future__ import annotations

import json
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from ..helpers import (  # noqa: F401
    REPO,
    combo_row,
    group,
    page,
    run_lines,
    switch_row,
)

# S reads settings.lua straight from disk: monitors.py writes the file
# behind this window's back, so the cached copy would be stale.
from ..store import S

# How long the "keep it?" dialog waits before putting the old value back.
REVERT_SECONDS = 12

# Offered scales. Hyprland accepts fractional values but rejects any that do not
# divide the resolution into whole pixels, so the list stays at the quarters
# every desktop offers rather than a free-text field that invites a rejection.
SCALES = ("auto", "1", "1.25", "1.5", "1.75", "2")

ROTATIONS = ("0°", "90°", "180°", "270°")
# Hyprland stores the rotation as an enum, not as degrees: 0..3 are the
# unflipped quarter turns. Read off a running compositor, where --transform 90
# came back as transform=1.
_TRANSFORM_TO_LABEL = {0: "0°", 1: "90°", 2: "180°", 3: "270°"}


def _monitors_script(*args: str):
    return subprocess.run(
        [sys.executable, str(REPO / "scripts" / "monitors.py"), *args],
        capture_output=True, text=True, check=False, timeout=25)


def _screens() -> tuple[list[dict], str]:
    """The screens, and an explanation when there are none.

    ⚠️ "no screens" and "could not ask the compositor" are the same empty list,
    and showing the first when the second happened is a lie the user cannot
    debug. monitors.py exits non-zero for the second, so the two are told apart
    here and the page says which one it is.
    """
    result = _monitors_script("show")
    if result.returncode != 0:
        why = (result.stderr or result.stdout or "").strip().splitlines()
        return [], (why[-1] if why else _("Hyprland could not be reached"))
    if not result.stdout.strip():
        return [], _("No displays reported")
    try:
        return json.loads(result.stdout), ""
    except ValueError:
        return [], _("Hyprland gave an answer that could not be read")


def _scale_label(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "auto"
    return str(int(number)) if number.is_integer() else f"{number:g}"


def build(win):
    p = page(_("Displays"), "video-display-symbolic")
    # Guard against the revert writing back into the widget it is reverting:
    # ComboRow fires notify::selected for a programmatic set too, which would
    # apply the old value again and ask about it again, forever.
    win._display_busy = False

    screens, problem = _screens()
    if not screens:
        g = group(p, _("Connected displays"), "")
        g.add(Adw.ActionRow(title=problem or _("No displays reported")))
    for screen in screens:
        _build_screen(win, p, screen, len(screens))

    _build_profiles(win, p)
    win.add_page(p, "displays", _("Displays"), "video-display-symbolic")


def _build_screen(win, p, screen: dict, total: int) -> None:
    title = f"{screen['name']} — {screen['desc']}".strip(" —")
    g = group(p, GLib.markup_escape_text(title),
              _("{w}x{h} at {x},{y}").format(w=screen["width"], h=screen["height"],
                                             x=screen["x"], y=screen["y"]))

    modes = screen.get("modes") or [screen["mode"]]
    combo_row(g, _("Resolution and refresh rate"), "",
              modes, screen["mode"],
              lambda v, s=screen: _change(win, s, "mode", v))

    combo_row(g, _("Scale"), _("Everything on screen gets bigger or smaller"),
              list(SCALES), _scale_label(screen["scale"]),
              lambda v, s=screen: _change(win, s, "scale", v))

    combo_row(g, _("Rotation"), "",
              list(ROTATIONS), _TRANSFORM_TO_LABEL.get(screen.get("transform", 0), "0°"),
              lambda v, s=screen: _change(win, s, "transform", v.rstrip("°")))

    switch_row(g, _("Variable refresh rate"),
               _("Only useful if the screen supports it"),
               screen.get("vrr", False),
               lambda v, s=screen: _change(win, s, "vrr", "on" if v else "off"))

    # A switch that turns off the only screen has no counterpart to turn it back
    # on, so it is not offered at all. monitors.py refuses it a second time —
    # this is the friendly half, that one is the safe half.
    if total > 1:
        switch_row(g, _("Active"), _("Switch this screen off"),
                   not screen.get("disabled", False),
                   lambda v, s=screen: _change(win, s, "enabled",
                                               "true" if v else "false"))


def _change(win, screen: dict, key: str, value: str) -> None:
    if win._display_busy:
        return

    before = _current_value(screen, key)
    result = _monitors_script("set", screen["name"], f"--{key}", str(value))
    win.s.data = S.read()
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip().splitlines()
        win.toast(message[-1] if message else _("Could not apply that"))
        return
    if before is None or str(before) == str(value):
        return
    _confirm(win, screen, key, before)


def _current_value(screen: dict, key: str):
    if key == "mode":
        return screen.get("mode")
    if key == "scale":
        return _scale_label(screen.get("scale"))
    if key == "transform":
        return str(screen.get("transform", 0) * 90)
    if key == "vrr":
        return "on" if screen.get("vrr") else "off"
    if key == "enabled":
        return "false" if screen.get("disabled") else "true"
    return None


def _confirm(win, screen: dict, key: str, before) -> None:
    """Keep it, or put it back on its own.

    The dialog is what makes changing a resolution safe to try: if the new mode
    shows nothing, nobody has to find a terminal — waiting is enough.
    """
    remaining = {"seconds": REVERT_SECONDS}
    dialog = Adw.MessageDialog(
        transient_for=win, modal=True,
        heading=_("Keep this display setting?"),
        body=_("Putting it back in {} seconds.").format(REVERT_SECONDS))
    dialog.add_response("revert", _("Put it back"))
    dialog.add_response("keep", _("Keep"))
    dialog.set_response_appearance("keep", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("keep")
    # Closing the dialog any other way counts as "put it back", because the most
    # likely reason it got closed without an answer is that it cannot be seen.
    dialog.set_close_response("revert")

    def tick() -> bool:
        remaining["seconds"] -= 1
        if remaining["seconds"] <= 0:
            dialog.close()
            _revert(win, screen, key, before)
            return False
        dialog.set_body(_("Putting it back in {} seconds.").format(remaining["seconds"]))
        return True

    source = GLib.timeout_add_seconds(1, tick)

    def answered(_d, response: str) -> None:
        GLib.source_remove(source)
        if response != "keep":
            _revert(win, screen, key, before)

    dialog.connect("response", answered)
    dialog.present()


def _revert(win, screen: dict, key: str, before) -> None:
    win._display_busy = True
    try:
        _monitors_script("set", screen["name"], f"--{key}", str(before))
        win.s.data = S.read()
        win.toast(_("Put back"))
    finally:
        # Cleared on the next idle, not here: the ComboRow that is being reset
        # emits its signal after this returns.
        GLib.idle_add(lambda: (setattr(win, "_display_busy", False), False)[1])


# -- saved arrangements ------------------------------------------------------


def _build_profiles(win, p) -> None:
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
