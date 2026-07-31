#!/usr/bin/env python3
"""Weather for the calendar popup.

Off unless you set a location, and that is deliberate rather than lazy. Every
no-API-key weather source works by looking up whoever asked, so switching this
on by default would send this machine's address to a third party the first time
the calendar was opened, without anyone choosing that. Naming a town instead is
both more private and more accurate — the IP of a VPN endpoint is not where you
are standing.

Source is wttr.in, which needs no key and no account.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

CACHE_TTL = 30 * 60          # seconds; the weather does not change faster
TIMEOUT = 8                  # a popup must never wait on the network


def _cache_path() -> Path:
    import os
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "buchhwin" / "weather.json"


def _settings(key: str, fallback: str = "") -> str:
    """One value out of settings.lua, without importing the settings module."""
    import os
    repo = Path(os.environ.get(
        "BUCHHWIN_REPO",
        Path.home() / ".local/share/fedora-buchhwin-hyprland"))
    script = repo / "scripts" / "settings.py"
    if not script.exists():
        return fallback
    try:
        import sys
        out = subprocess.run([sys.executable, str(script), "get", key],
                             capture_output=True, text=True, check=False,
                             timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return fallback
    if not out or out.startswith("not found") or out in ("None", "nil"):
        return fallback
    return out


def fetch(location: str) -> dict | None:
    """Current conditions, or None. Never raises, never blocks for long."""
    if not location:
        return None

    cache = _cache_path()
    try:
        cached = json.loads(cache.read_text())
        if (cached.get("location") == location
                and time.time() - cached.get("at", 0) < CACHE_TTL):
            return cached
    except (OSError, json.JSONDecodeError, ValueError):
        pass

    # %C condition, %t temperature, %f feels-like, %h humidity, %w wind.
    # One line, so there is nothing to parse wrongly.
    url = f"https://wttr.in/{location}?format=%C|%t|%f|%h|%w&m"
    try:
        out = subprocess.run(["curl", "-fsS", "--max-time", str(TIMEOUT), url],
                             capture_output=True, text=True, check=False,
                             timeout=TIMEOUT + 2).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    parts = [p.strip() for p in out.split("|")]
    if len(parts) < 5 or not parts[0]:
        return None

    data = {"location": location, "at": time.time(),
            "condition": parts[0], "temp": parts[1], "feels": parts[2],
            "humidity": parts[3], "wind": parts[4]}
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data))
    except OSError:
        pass
    return data


def location() -> str:
    return _settings("weather.location", "")


def icon_for(condition: str) -> str:
    """A themed icon name for a wttr.in condition phrase."""
    text = condition.lower()
    if "thunder" in text or "storm" in text:
        return "weather-storm-symbolic"
    if "snow" in text or "sleet" in text or "ice" in text:
        return "weather-snow-symbolic"
    if "rain" in text or "drizzle" in text or "shower" in text:
        return "weather-showers-symbolic"
    if "fog" in text or "mist" in text or "haze" in text:
        return "weather-fog-symbolic"
    if "overcast" in text:
        return "weather-overcast-symbolic"
    if "cloud" in text:
        return "weather-few-clouds-symbolic"
    return "weather-clear-symbolic"
