#!/usr/bin/env python3
"""Which applications you actually use, so the launcher can lead with them.

    app-usage.py record <desktop-id>    count one launch
    app-usage.py top [n]                the most-used ids, best first
    app-usage.py listen                 count launches by watching Hyprland

Ranking is launches plus a decay, not launches alone: something opened forty
times last year should not outrank what you opened four times this week. The
score halves every 30 days, which is the difference between "most used ever"
and "what you are working on".

Nothing here leaves the machine and nothing is recorded but a count and a
timestamp per desktop id.
"""

from __future__ import annotations

import json
import math
import os
import socket
import sys
import time
from pathlib import Path

STATE = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "buchhwin"
DB = STATE / "app-usage.json"
HALF_LIFE = 30 * 24 * 3600          # seconds


def load() -> dict:
    try:
        return json.loads(DB.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def save(data: dict) -> None:
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        DB.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


def record(app: str) -> None:
    if not app:
        return
    data = load()
    entry = data.setdefault(app, {"count": 0, "last": 0})
    entry["count"] = entry.get("count", 0) + 1
    entry["last"] = int(time.time())
    save(data)


def score(entry: dict, now: float) -> float:
    age = max(0.0, now - entry.get("last", 0))
    return entry.get("count", 0) * math.pow(0.5, age / HALF_LIFE)


def top(limit: int = 10) -> list[str]:
    now = time.time()
    data = load()
    ranked = sorted(data.items(), key=lambda kv: score(kv[1], now), reverse=True)
    return [app for app, _ in ranked[:limit]]


def listen() -> int:
    """Count launches by watching Hyprland's window-open events.

    Watching the compositor rather than wrapping every launcher: rofi, the
    dock, a keybind and a file manager all open windows, and only one of them
    would ever have been wrapped. The class is not a desktop id, but it is what
    identifies the application everywhere else here too.
    """
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if signature:
        path = runtime / "hypr" / signature / ".socket2.sock"
    else:
        candidates = sorted((runtime / "hypr").glob("*/.socket2.sock"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        path = candidates[0] if candidates else None
    if path is None or not path.exists():
        print("app-usage: no Hyprland socket", file=sys.stderr)
        return 1

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(path))
        buffer = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                return 0
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                text = line.decode(errors="replace")
                # openwindow>>address,workspace,class,title
                if text.startswith("openwindow>>"):
                    parts = text.split(">>", 1)[1].split(",")
                    if len(parts) >= 3 and parts[2].strip():
                        record(parts[2].strip())


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    if argv[1] == "record" and len(argv) > 2:
        record(argv[2])
        return 0
    if argv[1] == "top":
        limit = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 10
        for app in top(limit):
            print(app)
        return 0
    if argv[1] == "listen":
        return listen()
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
