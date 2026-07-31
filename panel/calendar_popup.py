"""Calendar popup: a month at a glance, plus what is actually on that day.

Windows shows the month and the day's appointments when you click the clock,
and lets you open the full calendar from there. This does the same. The month
grid is Gtk.Calendar; the appointments come from scripts/calendar.py, which
already reads evolution-data-server for the bar — so the popup, the bar and
GNOME Calendar can never disagree about your day.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from popup import Popup, heading, launch  # noqa: E402

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


class CalendarPopup(Popup):
    name = "calendar"
    width = 340

    def build(self, window: Gtk.Window) -> Gtk.Widget:
        self._window = window
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        self._calendar = Gtk.Calendar()
        self._calendar.add_css_class("popup-calendar")
        self._calendar.connect("day-selected", lambda _c: self._refresh())
        box.append(self._calendar)

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
                          lambda _b: launch(["gnome-calendar"], window))
        box.append(open_full)

        self._refresh()
        return box

    # -- appointments ------------------------------------------------------

    def _selected_date(self) -> datetime:
        g = self._calendar.get_date()          # GLib.DateTime
        return datetime(g.get_year(), g.get_month(), g.get_day_of_month())

    def _refresh(self) -> None:
        day = self._selected_date()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if day.date() == today.date():
            self._agenda_title.set_label("Today")
        elif day.date() == (today + timedelta(days=1)).date():
            self._agenda_title.set_label("Tomorrow")
        else:
            self._agenda_title.set_label(day.strftime("%A, %d %B"))

        while (child := self._agenda.get_first_child()) is not None:
            self._agenda.remove(child)

        for row in self._rows_for(day):
            self._agenda.append(row)

    def _rows_for(self, day: datetime) -> list[Gtk.Widget]:
        try:
            cal = _load_calendar_module()
        except (ImportError, OSError, SyntaxError) as exc:
            return [self._note(f"calendar module unavailable ({exc})")]

        # Ask for exactly the selected day. Passing `since` is why fetch_events
        # grew that parameter — the bar only ever looks forward, a calendar has
        # to be able to look back.
        events, error = cal.fetch_events(days=1, since=day.astimezone())
        if error:
            return [self._note(error)]

        end = day + timedelta(days=1)
        rows = []
        for ev in events:
            start = datetime.fromtimestamp(ev["start"])
            if not (day <= start < end):
                continue
            rows.append(self._event_row(ev, start))

        return rows or [self._note("Nothing scheduled")]

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

    def _note(self, text: str) -> Gtk.Widget:
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("popup-note")
        label.set_wrap(True)
        return label
