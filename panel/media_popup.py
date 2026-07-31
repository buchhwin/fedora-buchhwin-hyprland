#!/usr/bin/env python3
"""Media controls — what is playing, and the buttons for it.

playerctl speaks MPRIS, which every player worth having implements: Spotify,
browsers, mpv, VLC, GNOME Music. So this is one popup for all of them rather
than a plugin per application.

Album art is fetched only from a LOCAL file. `mpris:artUrl` is frequently an
http URL pointing at the streaming service's CDN, and a panel that quietly
fetches images from the internet every time it opens is not something to build
without saying so — a remote URL is skipped and the player's icon is shown
instead.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, GdkPixbuf, Gtk
from popup import PanelWindow, heading, note

ART_SIZE = 64


def playerctl(*args: str, player: str | None = None) -> str:
    cmd = ["playerctl"]
    if player:
        cmd += ["--player", player]
    cmd += list(args)
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              check=False, timeout=4).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def players() -> list[str]:
    out = playerctl("--list-all")
    return [line.strip() for line in out.splitlines() if line.strip()]


def info(player: str) -> dict:
    fmt = "{{status}}|{{artist}}|{{title}}|{{album}}|{{mpris:artUrl}}"
    parts = playerctl("metadata", "--format", fmt, player=player).split("|")
    while len(parts) < 5:
        parts.append("")
    return {"player": player, "status": parts[0], "artist": parts[1],
            "title": parts[2], "album": parts[3], "art": parts[4]}


def local_art(url: str) -> Path | None:
    """A readable local path for the art, or None.

    file:// only. See the module docstring: an http artUrl would mean this
    popup made a network request to a third party every time it opened.
    """
    if not url.startswith("file://"):
        return None
    path = Path(unquote(urlparse(url).path))
    return path if path.is_file() else None


class MediaPopup(PanelWindow):
    name = "media"
    width = 340

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        self._box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._populate()
        return self._box

    def refresh(self) -> None:
        self._populate()

    def _populate(self) -> None:
        box = self._box
        while (child := box.get_first_child()) is not None:
            box.remove(child)

        found = players()
        if not found:
            box.append(heading("Media"))
            box.append(note("Nothing is playing"))
            return

        for index, player in enumerate(found):
            if index:
                box.append(Gtk.Separator())
            box.append(self._player_block(info(player)))

    def _player_block(self, data: dict) -> Gtk.Widget:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        art = local_art(data["art"])
        if art is not None:
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    str(art), ART_SIZE, ART_SIZE, True)
                image = Gtk.Picture.new_for_paintable(
                    Gdk.Texture.new_for_pixbuf(pixbuf))
                image.set_size_request(ART_SIZE, ART_SIZE)
                image.add_css_class("media-art")
            except Exception:
                image = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
        else:
            image = Gtk.Image.new_from_icon_name("audio-x-generic-symbolic")
            image.set_pixel_size(40)
        row.append(image)

        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        labels.set_hexpand(True)
        labels.set_valign(Gtk.Align.CENTER)
        title = Gtk.Label(label=data["title"] or data["player"], xalign=0)
        title.set_ellipsize(3)
        title.set_max_width_chars(24)
        labels.append(title)
        if data["artist"] or data["album"]:
            sub = Gtk.Label(label=" — ".join(x for x in (data["artist"], data["album"]) if x),
                            xalign=0)
            sub.add_css_class("popup-subtle")
            sub.set_ellipsize(3)
            sub.set_max_width_chars(28)
            labels.append(sub)
        row.append(labels)
        outer.append(row)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        controls.set_halign(Gtk.Align.CENTER)
        for icon, action in (("media-skip-backward-symbolic", "previous"),
                             ("media-playback-pause-symbolic"
                              if data["status"] == "Playing"
                              else "media-playback-start-symbolic", "play-pause"),
                             ("media-skip-forward-symbolic", "next")):
            button = Gtk.Button(icon_name=icon)
            button.add_css_class("media-button")
            button.connect("clicked", self._on_control, data["player"], action)
            controls.append(button)
        outer.append(controls)
        return outer

    def _on_control(self, _button, player: str, action: str) -> None:
        playerctl(action, player=player)
        # Re-read rather than assume: the player decides whether it obeyed, and
        # a pause button that flips to play on a stream that ignored it lies.
        self._populate()
