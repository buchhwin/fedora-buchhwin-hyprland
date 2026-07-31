"""Calendar popup: a month at a glance, plus what is actually on that day.

Windows shows the month and the day's appointments when you click the clock,
and lets you open the full calendar from there. This does the same. The month
grid is Gtk.Calendar; the appointments come from scripts/calendar.py, which
already reads evolution-data-server for the bar — so the popup, the bar and
GNOME Calendar can never disagree about your day.
"""

from __future__ import annotations

import importlib.util
import threading
from datetime import datetime, timedelta
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

import weather
from gi.repository import GLib, Gtk
from popup import PanelWindow, heading, launch, note

# scripts/calendar.py is loaded by PATH, deliberately not by putting scripts/ on
# sys.path: it is called calendar.py, and a plain `import calendar` would then
# shadow the standard library module of that name for this process and anything
# it imports. Loading it under a distinct name keeps both reachable.
_CAL_SOURCE = Path(__file__).resolve().parent.parent / "scripts" / "calendar.py"


def _load_calendar_module():
    spec = importlib.util.spec_from_file_location("buchhwin_calendar", _CAL_SOURCE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_CAL_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CalendarPopup(PanelWindow):
    name = "calendar"
    width = 340

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._calendar = Gtk.Calendar()
        self._calendar.add_css_class("popup-calendar")
        self._calendar.connect("day-selected", lambda _c: self.refresh())
        box.append(self._calendar)

        # Weather sits above the agenda: both answer "what is today like", and
        # it stays out of the way entirely when no location is configured.
        self._weather_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                                    spacing=10)
        self._weather_row.add_css_class("popup-row")
        self._weather_icon = Gtk.Image.new_from_icon_name("weather-clear-symbolic")
        self._weather_row.append(self._weather_icon)
        self._weather_labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                       spacing=0)
        self._weather_labels.set_hexpand(True)
        self._weather_main = Gtk.Label(label="", xalign=0)
        self._weather_sub = Gtk.Label(label="", xalign=0)
        self._weather_sub.add_css_class("popup-subtle")
        self._weather_labels.append(self._weather_main)
        self._weather_labels.append(self._weather_sub)
        self._weather_row.append(self._weather_labels)
        self._weather_row.set_visible(False)
        box.append(self._weather_row)

        box.append(Gtk.Separator())

        self._agenda_title = heading("Today")
        box.append(self._agenda_title)

        self._agenda = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._agenda.add_css_class("popup-agenda")
        box.append(self._agenda)

        box.append(Gtk.Separator())

        open_full = Gtk.Button(label="Open calendar")
        open_full.add_css_class("popup-action")
        open_full.connect("clicked",
                          lambda _b: launch(["gnome-calendar"], self))
        box.append(open_full)

        return box

    # -- appointments ------------------------------------------------------

    def _selected_date(self) -> datetime:
        g = self._calendar.get_date()          # GLib.DateTime
        return datetime(g.get_year(), g.get_month(), g.get_day_of_month())

    def _refresh_weather(self) -> None:
        """Fetch off-thread; a popup must open in milliseconds, not after a
        network round trip. Cached for half an hour by weather.py."""
        place = weather.location()
        if not place:
            self._weather_row.set_visible(False)
            return

        def work() -> None:
            data = weather.fetch(place)
            GLib.idle_add(self._show_weather, data)

        threading.Thread(target=work, daemon=True).start()

    def _show_weather(self, data) -> bool:
        if not data:
            self._weather_row.set_visible(False)
            return False
        self._weather_icon.set_from_icon_name(weather.icon_for(data["condition"]))
        self._weather_main.set_text(f'{data["temp"]}  {data["condition"]}')
        self._weather_sub.set_text(
            f'feels {data["feels"]} · {data["humidity"]} · {data["wind"]}'
            f' · {data["location"]}')
        self._weather_row.set_visible(True)
        return False

    def refresh(self) -> None:
        """Redraw the labels immediately; fetch the appointments off-thread.

        Reading evolution-data-server is a network operation with a timeout,
        and it used to run inside build() — so clicking the clock meant staring
        at nothing for as long as it took. Measured at 11.9 seconds with an
        unreachable account. The grid and the heading are cheap and appear at
        once; the day's events arrive when they arrive.
        """
        self._refresh_weather()

        day = self._selected_date()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if day.date() == today.date():
            self._agenda_title.set_label("Today")
        elif day.date() == (today + timedelta(days=1)).date():
            self._agenda_title.set_label("Tomorrow")
        else:
            self._agenda_title.set_label(day.strftime("%A, %d %B"))

        self._set_rows([note("Loading…")])

        # Each refresh gets a token. A slow answer for a day the user has
        # already clicked past must not overwrite the day now on screen.
        self._token = getattr(self, "_token", 0) + 1
        token = self._token

        def work() -> None:
            try:
                rows = self._events_for(day)
            except Exception as exc:
                rows = [("error", str(exc))]
            GLib.idle_add(self._deliver, token, day, rows)

        threading.Thread(target=work, daemon=True).start()

    def _deliver(self, token: int, day: datetime, rows: list) -> bool:
        if token != getattr(self, "_token", 0):
            return False                                  # a later click won
        widgets = []
        for kind, payload in rows:
            if kind == "event":
                widgets.append(self._event_row(payload,
                                               datetime.fromtimestamp(payload["start"])))
            else:
                widgets.append(note(payload))
        self._set_rows(widgets or [note("Nothing scheduled")])
        return False

    def _set_rows(self, widgets: list[Gtk.Widget]) -> None:
        while (child := self._agenda.get_first_child()) is not None:
            self._agenda.remove(child)
        for w in widgets:
            self._agenda.append(w)

    def _events_for(self, day: datetime) -> list[tuple[str, object]]:
        """Runs on a worker thread — no GTK calls in here."""
        try:
            cal = _load_calendar_module()
        except (ImportError, OSError, SyntaxError) as exc:
            return [("error", f"calendar module unavailable ({exc})")]

        # Ask for exactly the selected day. Passing `since` is why fetch_events
        # grew that parameter — the bar only ever looks forward, a calendar has
        # to be able to look back.
        events, error = cal.fetch_events(days=1, since=day.astimezone())
        if error:
            return [("error", error)]

        end = day + timedelta(days=1)
        out: list[tuple[str, object]] = []
        for ev in events:
            start = datetime.fromtimestamp(ev["start"])
            if day <= start < end:
                out.append(("event", ev))
        return out

    def _event_row(self, ev: dict, start: datetime) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.add_css_class("agenda-row")

        when = "all day" if ev["all_day"] else start.strftime("%H:%M")
        time_label = Gtk.Label(label=when, xalign=0)
        time_label.add_css_class("agenda-time")
        time_label.set_size_request(56, -1)
        row.append(time_label)

        title = Gtk.Label(label=ev["summary"], xalign=0)
        title.add_css_class("agenda-title")
        title.set_ellipsize(3)             # Pango.EllipsizeMode.END
        title.set_hexpand(True)
        row.append(title)
        return row

