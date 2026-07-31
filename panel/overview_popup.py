#!/usr/bin/env python3
"""Workspace overview — everything that is open, on one screen.

SUPER+Tab. A grid of workspaces, each listing the windows on it; click a window
to go to it, click a workspace to switch. Type to filter.

Honest about what it is NOT
---------------------------
There are no live thumbnails. Hyprland's screencopy can capture an OUTPUT, not
a window, so a real preview would mean switching to each workspace in turn and
photographing it — visible flicker, on every press, to produce pictures that
are out of date by the time you look at them. The plugins that do this properly
(hyprexpo) are compiled against one exact Hyprland version: the packaged one
wants 0.51.1 against our 0.55.4, so it cannot even be installed.

What people actually use an overview for is "which desktop is that window on",
and an application icon plus its title answers that instantly and always
correctly. That is what this does.
"""

from __future__ import annotations

import json
import subprocess

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, GLib, Gtk
from popup import PanelWindow


def hyprctl_json(*args: str):
    try:
        out = subprocess.run(["hyprctl", "-j", *args], capture_output=True,
                             text=True, check=False, timeout=5).stdout
        return json.loads(out)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return []


def dispatch(lua: str) -> None:
    subprocess.run(["hyprctl", "dispatch", lua], capture_output=True, check=False)


def icon_for(window: dict) -> str:
    """A themed icon name for the window's class.

    Desktop entries are not consulted on purpose: matching a Wayland app_id to
    a .desktop file is guesswork that fails for exactly the applications people
    have a lot of windows of. The icon theme's own lookup by lower-cased class
    is right far more often, and the fallback is honest rather than wrong.
    """
    name = (window.get("initialClass") or window.get("class") or "").lower()
    return name or "application-x-executable"


class OverviewPopup(PanelWindow):
    name = "overview"
    width = 0                       # full screen; the anchors below decide

    def __init__(self, app) -> None:
        super().__init__(app)
        if self._shell:
            self._shell.set_layer(self.window, self._shell.Layer.OVERLAY)
            for edge in (self._shell.Edge.TOP, self._shell.Edge.BOTTOM,
                         self._shell.Edge.LEFT, self._shell.Edge.RIGHT):
                self._shell.set_anchor(self.window, edge, True)
            # EXCLUSIVE: typing filters the list, so the keyboard has to come
            # here in full — including Escape, which is how you leave.
            self._shell.set_keyboard_mode(self.window,
                                          self._shell.KeyboardMode.EXCLUSIVE)

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        window.add_css_class("overview")
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.set_valign(Gtk.Align.CENTER)
        outer.set_halign(Gtk.Align.CENTER)

        self._search = Gtk.SearchEntry(placeholder_text="Type to filter")
        self._search.set_size_request(420, -1)
        self._search.set_halign(Gtk.Align.CENTER)
        self._search.connect("search-changed", lambda _e: self._fill())
        outer.append(self._search)

        self._grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE,
                                 min_children_per_line=2,
                                 max_children_per_line=5,
                                 row_spacing=14, column_spacing=14,
                                 homogeneous=True)
        # Centred: a FlowBox fills its parent and would otherwise pin the cards
        # to the top-left corner of a full-screen overlay.
        self._grid.set_halign(Gtk.Align.CENTER)
        self._grid.set_valign(Gtk.Align.CENTER)
        outer.append(self._grid)
        return outer

    def refresh(self) -> None:
        self._search.set_text("")
        self._fill()
        # The search box takes focus so typing filters immediately rather than
        # after a click nobody expects to have to make.
        GLib.idle_add(self._search.grab_focus)

    def _fill(self) -> None:
        while (child := self._grid.get_first_child()) is not None:
            self._grid.remove(child)

        needle = self._search.get_text().strip().lower()
        clients = [c for c in hyprctl_json("clients") if c.get("mapped", True)]
        workspaces = {w["id"]: w for w in hyprctl_json("workspaces")}
        active = (hyprctl_json("activeworkspace") or {}).get("id")

        by_workspace: dict[int, list[dict]] = {}
        for client in clients:
            ws = client.get("workspace", {}).get("id")
            if ws is None:
                continue
            if needle and needle not in (client.get("title", "") + " " +
                                         client.get("class", "")).lower():
                continue
            by_workspace.setdefault(ws, []).append(client)

        # Every workspace that exists or holds something, in numeric order.
        # Special workspaces have negative ids and sort to the front, which is
        # where "minimized" belongs anyway.
        ids = sorted(set(by_workspace) | set(workspaces))
        for ws_id in ids:
            windows = by_workspace.get(ws_id, [])
            if needle and not windows:
                continue                # filtering: hide the empty ones
            self._grid.append(self._workspace_card(ws_id, windows,
                                                   workspaces.get(ws_id),
                                                   ws_id == active))

        if self._grid.get_first_child() is None:
            self._grid.append(Gtk.Label(label="Nothing matches"))

    def _workspace_card(self, ws_id: int, windows: list[dict],
                        info: dict | None, is_active: bool) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("overview-card")
        if is_active:
            card.add_css_class("overview-card-active")
        card.set_size_request(220, 150)

        name = (info or {}).get("name") or str(ws_id)
        title = Gtk.Label(label=f"{ws_id}  {name}" if name != str(ws_id) else str(ws_id))
        title.add_css_class("overview-title")
        title.set_xalign(0)
        card.append(title)

        if not windows:
            empty = Gtk.Label(label="empty")
            empty.add_css_class("popup-subtle")
            empty.set_valign(Gtk.Align.CENTER)
            empty.set_vexpand(True)
            card.append(empty)
        else:
            for window in windows[:5]:
                card.append(self._window_row(window))
            if len(windows) > 5:
                more = Gtk.Label(label=f"+{len(windows) - 5} more", xalign=0)
                more.add_css_class("popup-subtle")
                card.append(more)

        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_a, i=ws_id: self._go_workspace(i))
        card.add_controller(click)
        return card

    def _window_row(self, window: dict) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row.add_css_class("overview-window")
        row.append(Gtk.Image.new_from_icon_name(icon_for(window)))
        label = Gtk.Label(label=window.get("title") or window.get("class") or "?",
                          xalign=0)
        label.set_ellipsize(3)          # PANGO_ELLIPSIZE_END
        label.set_max_width_chars(22)
        row.append(label)

        # The address is pulled out BEFORE the lambda. A default argument that
        # calls a function is evaluated once at definition, which happens to be
        # right here — but it reads as a bug to everyone who meets it, and the
        # loop variable it is guarding against is the real reason it is bound
        # at all.
        address = window.get("address")
        click = Gtk.GestureClick()
        click.connect("pressed", lambda *_a, a=address: self._go_window(a))
        row.add_controller(click)
        return row

    # -- actions ------------------------------------------------------------

    def _go_workspace(self, ws_id: int) -> None:
        self.hide()
        dispatch(f'hl.dsp.focus({{ workspace = {ws_id} }})')

    def _go_window(self, address: str | None) -> None:
        if not address:
            return
        self.hide()
        dispatch(f'hl.dsp.focus({{ window = "address:{address}" }})')

    def _on_key(self, _c, keyval, _code, _state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.hide()
            return True
        return False
