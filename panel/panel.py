#!/usr/bin/env python3
"""The panel process. Started by the buchhwin-panel wrapper, never directly.

    panel.py --daemon      stay resident, listen for toggles (the normal case)
    panel.py calendar      build and show one popup, then exit (the fallback)

Why a FIFO and not a socket
---------------------------
Whatever the bar runs on a click has to be cheap, because the click is what the
user is waiting for. A named pipe can be written from the shell —
`echo toggle calendar > fifo` — which costs about a millisecond and needs no
client library. A Unix socket would need socat or another Python start, and a
second Python start is exactly the 1.1 seconds this whole design exists to
avoid.

The daemon opens the FIFO for reading AND writing itself. Read-only would give
EOF every time the last writer closed, turning the read loop into a spin.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib  # noqa: E402

from popup import FIFO, load_css  # noqa: E402

NAMES = ("calendar", "audio", "network", "bluetooth", "quick", "overview",
         "media",
         "osd-volume", "osd-brightness", "osd-mic")
USAGE = ("usage: panel.py --daemon | calendar|audio|network|quick"
         "|osd-volume|osd-brightness|osd-mic")


def _window_class(name: str):
    if name == "calendar":
        from calendar_popup import CalendarPopup
        return CalendarPopup
    if name == "quick":
        from quick_popup import QuickPopup

        return QuickPopup
    if name == "bluetooth":
        from bluetooth_popup import BluetoothPopup

        return BluetoothPopup
    if name == "overview":
        from overview_popup import OverviewPopup

        return OverviewPopup
    if name == "media":
        from media_popup import MediaPopup

        return MediaPopup
    if name.startswith("osd"):
        from osd_popup import OsdPopup

        return OsdPopup
    if name == "audio":
        from audio_popup import AudioPopup
        return AudioPopup
    from network_popup import NetworkPopup
    return NetworkPopup


class Panel(Adw.Application):
    def __init__(self, daemon: bool, only: str | None = None) -> None:
        super().__init__(application_id="de.buchhwin.panel",
                         flags=Gio.ApplicationFlags.NON_UNIQUE)
        self._daemon = daemon
        self._only = only
        self._windows: dict[str, object] = {}
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app) -> None:
        load_css()
        # Hold the application alive with no window on screen. Without this a
        # daemon whose popups are all hidden would consider itself finished.
        if self._daemon:
            self.hold()
            self._build_all()
            self._listen()
        else:
            self._get(self._only).show()

    def _build_all(self) -> None:
        # Built up front, not on first click: building is the slow part, and
        # doing it at login means the first click is as fast as the tenth.
        for name in NAMES:
            try:
                self._get(name)
            except Exception as exc:                      # noqa: BLE001
                print(f"panel: could not build {name}: {exc}", file=sys.stderr)

    def _get(self, name: str):
        # The three osd-* names share one window: it is the same bar showing a
        # different value, and three of them could otherwise be on screen at
        # once, stacked on top of each other.
        key = "osd" if name.startswith("osd") else name
        if key not in self._windows:
            self._windows[key] = _window_class(name)(self)
        return self._windows[key]

    # -- the toggle channel ------------------------------------------------

    def _listen(self) -> None:
        try:
            if FIFO.exists():
                FIFO.unlink()
            os.mkfifo(FIFO, 0o600)
        except OSError as exc:
            print(f"panel: cannot create {FIFO}: {exc}", file=sys.stderr)
            return

        # A plain reader thread rather than GLib.io_add_watch. An IOChannel
        # cannot do read_line() unbuffered, and buffering a FIFO that is meant
        # to be read line-by-line as lines arrive is the wrong shape — the
        # first version did exactly that and silently read nothing at all.
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self) -> None:
        # O_RDWR, not O_RDONLY: a read-only pipe returns EOF every time the
        # last writer closes, which would turn this into a spin loop.
        fd = os.open(FIFO, os.O_RDWR)
        with os.fdopen(fd, "r", buffering=1) as pipe:
            for line in pipe:
                parts = line.split()
                if len(parts) != 2 or parts[0] not in ("toggle", "show", "hide"):
                    continue
                action, name = parts
                if name in NAMES:
                    GLib.idle_add(self._apply, action, name)

    def _apply(self, action: str, name: str) -> bool:
        window = self._get(name)

        # The OSD is feedback, not a menu: it never closes anything, and
        # nothing closes it. Turning the volume down while the calendar is open
        # should not shut the calendar.
        if name.startswith("osd"):
            window.show_for(name.split("-", 1)[1] if "-" in name else "volume")
            return False

        # Opening one popup closes the others. Two panels open at once is not
        # a thing any desktop does, and the catchers would fight over clicks.
        if action in ("toggle", "show"):
            for other, w in self._windows.items():
                if other != name and other != "osd":
                    w.hide()
        getattr(window, action)()
        return False


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    arg = argv[1]
    if arg == "--daemon":
        return Panel(daemon=True).run([])
    if arg in NAMES:
        return Panel(daemon=False, only=arg).run([])
    print(f"unknown popup: {arg}\n{USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
