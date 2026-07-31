#!/usr/bin/env python3
"""Upcoming appointments, for the Waybar module.

    calendar.py waybar     JSON for waybar
    calendar.py list       plain text, next 7 days
    calendar.py today      just today

Where the data comes from
-------------------------
GNOME Online Accounts signs you in; **evolution-data-server** does the syncing;
this reads what EDS already has. That means one account, one sync engine, and
the bar, GNOME Calendar and Evolution can never disagree about your day.

The alternative — vdirsyncer plus khal — was rejected on purpose: its Google
support needs OAuth credentials you create yourself in the Google Cloud
console, which is the opposite of "just log in".

Note for anyone packaging this: the GObject typelibs (`ECal-2.0`,
`EDataServer-1.2`) ship in the main `evolution-data-server` package on Fedora,
not in `-devel`. Installing the desktop is enough; no build dependencies.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta

WINDOW_DAYS = 7
SOON_MINUTES = 15


def load_gi():
    """Import the EDS bindings, or return None with a readable reason."""
    try:
        import gi
        gi.require_version("EDataServer", "1.2")
        gi.require_version("ECal", "2.0")
        from gi.repository import ECal, EDataServer, GLib
        return ECal, EDataServer, GLib
    except (ImportError, ValueError) as exc:
        return ("error", str(exc))


def fetch_events(days: int = WINDOW_DAYS) -> tuple[list[dict], str | None]:
    """Return (events, error). Events are dicts with start/end/summary/all_day."""
    loaded = load_gi()
    if isinstance(loaded, tuple) and loaded and loaded[0] == "error":
        return [], f"evolution-data-server is not available ({loaded[1]})"
    ECal, EDataServer, GLib = loaded

    try:
        registry = EDataServer.SourceRegistry.new_sync(None)
    except GLib.Error as exc:
        return [], f"no calendar service ({exc.message})"

    sources = registry.list_sources(EDataServer.SOURCE_EXTENSION_CALENDAR)
    if not sources:
        return [], "no calendars configured"

    now = datetime.now(UTC)
    end = now + timedelta(days=days)
    start_ts, end_ts = int(now.timestamp()), int(end.timestamp())

    events: list[dict] = []
    for source in sources:
        ext = source.get_extension(EDataServer.SOURCE_EXTENSION_CALENDAR)
        if hasattr(ext, "get_selected") and not ext.get_selected():
            continue                       # unticked in the calendar app
        try:
            client = ECal.Client.connect_sync(
                source, ECal.ClientSourceType.EVENTS, 10, None)
            ok, comps = client.get_object_list_as_comps_sync(
                f"(occur-in-time-range? (make-time \"{_ical(now)}\") "
                f"(make-time \"{_ical(end)}\"))", None)
        except GLib.Error:
            # One broken calendar must not take the whole bar module down.
            continue
        if not ok:
            continue

        for comp in comps or []:
            try:
                summary = comp.get_summary()
                text = summary.get_value() if summary else ""
                dtstart = comp.get_dtstart()
                if dtstart is None or dtstart.get_value() is None:
                    continue
                ical = dtstart.get_value()
                all_day = ical.is_date()
                ts = ical.as_timet_with_zone(ical.get_timezone()) \
                    if not all_day else ical.as_timet()
                if not (start_ts <= ts <= end_ts):
                    continue
                events.append({
                    "start": ts,
                    "summary": text or "(no title)",
                    "all_day": bool(all_day),
                    "calendar": source.get_display_name() or "",
                })
            except Exception:
                continue

    events.sort(key=lambda e: (e["start"], e["summary"]))
    return events, None


def _ical(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _fmt_time(ts: int, all_day: bool) -> str:
    if all_day:
        return "all day"
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def _day_label(ts: int) -> str:
    d = datetime.fromtimestamp(ts).date()
    today = datetime.now().date()
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    return datetime.fromtimestamp(ts).strftime("%a %d %b")


def cmd_waybar() -> int:
    events, error = fetch_events()

    if error:
        # Deliberately NOT an empty module. An empty field reads as "nothing on
        # today", which is the more dangerous of the two mistakes.
        print(json.dumps({
            "text": "󰃭 —",
            "tooltip": f"Calendar unavailable\n{error}",
            "class": "unavailable",
        }))
        return 0

    if not events:
        print(json.dumps({
            "text": datetime.now().strftime("󰃭 %a %d %b"),
            "tooltip": "Nothing in the next 7 days",
            "class": "empty",
        }))
        return 0

    nxt = events[0]
    minutes = int((nxt["start"] - datetime.now().timestamp()) / 60)
    if nxt["all_day"]:
        text = f"󰃭 {nxt['summary'][:28]}"
        cls = "allday"
    elif minutes < 0:
        text = f"󰃰 {nxt['summary'][:28]}"
        cls = "now"
    elif minutes <= SOON_MINUTES:
        text = f"󰀠 {minutes} min · {nxt['summary'][:22]}"
        cls = "soon"
    else:
        text = f"󰃭 {_fmt_time(nxt['start'], False)} {nxt['summary'][:24]}"
        cls = ""

    lines, current_day = [], None
    for ev in events[:20]:
        day = _day_label(ev["start"])
        if day != current_day:
            lines.append(f"\n<b>{day}</b>" if current_day else f"<b>{day}</b>")
            current_day = day
        when = _fmt_time(ev["start"], ev["all_day"])
        lines.append(f"  {when}  {_escape(ev['summary'])}")

    print(json.dumps({"text": text, "tooltip": "\n".join(lines), "class": cls}))
    return 0


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cmd_list(days: int) -> int:
    events, error = fetch_events(days)
    if error:
        print(error, file=sys.stderr)
        return 1
    if not events:
        print(f"nothing in the next {days} day(s)")
        return 0
    current_day = None
    for ev in events:
        day = _day_label(ev["start"])
        if day != current_day:
            print(f"\n{day}")
            current_day = day
        print(f"  {_fmt_time(ev['start'], ev['all_day']):>8}  {ev['summary']}")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "waybar"
    if cmd == "waybar":
        raise SystemExit(cmd_waybar())
    if cmd == "today":
        raise SystemExit(cmd_list(1))
    if cmd == "list":
        raise SystemExit(cmd_list(WINDOW_DAYS))
    print(__doc__)
    raise SystemExit(2)
