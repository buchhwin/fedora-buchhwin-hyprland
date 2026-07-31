#!/usr/bin/env python3
"""Make the minimize button do something.

Hyprland has no minimize. A tiling layout has nowhere to put a minimized
window, which is a perfectly good reason not to implement one — but the moment
windows carry a titlebar with a minimize button, "nothing happens" stops being
a design decision and becomes a broken button.

So this gives it somewhere to go: a special workspace named `minimized`. The
window leaves the layout, the dock's taskbar still lists it, and clicking it
there brings it back. That works for every window — GTK, Qt, XWayland, games —
because the taskbar speaks the foreign-toplevel protocol, not a toolkit's.

How it hears about it
---------------------
Hyprland announces `minimized>>ADDRESS,STATE` on its second socket — note the
"d", which cost an hour: `"minimized>>...".startswith("minimize>>")` is false,
so the first version of this listened forever and heard nothing. Verified by
dumping every event on the socket while triggering a minimize. STATE is 1 for
minimize and 0 for restore; both are handled, because a taskbar asks for either.
The address arrives without its `0x` prefix.

Why not the scratchpad
----------------------
`special:scratch` is already taken — rules.lua spawns a terminal into it, so
minimizing something there would drop it next to a shell. A separate workspace
also means "show me what I minimized" is one keystroke and does not disturb the
scratchpad.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

WORKSPACE = "special:minimized"


def socket_path() -> Path | None:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    signature = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if signature:
        candidate = runtime / "hypr" / signature / ".socket2.sock"
        return candidate if candidate.exists() else None
    # No signature in the environment — happens when this is started by systemd
    # before the session has exported it. Take the newest instance.
    base = runtime / "hypr"
    if not base.is_dir():
        return None
    instances = sorted(base.glob("*/.socket2.sock"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    return instances[0] if instances else None


def dispatch(lua: str) -> None:
    """One dispatcher, in Lua.

    `hyprctl dispatch movetoworkspacesilent ...` is a Lua syntax error under a
    Lua config provider and fails silently with exit status 0 — the same trap
    that left window snapping broken for months. Errors are printed.
    """
    out = subprocess.run(["hyprctl", "dispatch", lua], capture_output=True,
                         text=True, check=False).stdout
    if "error" in out.lower():
        print(f"minimize: {lua}\n  {out.strip()}", file=sys.stderr, flush=True)


# Addresses this process put away. Restoring is driven off this rather than off
# a lookup, so the common case — a focus change on a window that is NOT
# minimized, which happens constantly — costs a set membership test.
_MINIMIZED: set[str] = set()


def minimize(address: str) -> None:
    # silent = true: move it away without following it, which is the whole
    # difference between minimizing and switching workspace.
    dispatch(f'hl.dsp.window.move({{ workspace = "{WORKSPACE}", '
             f'silent = true, window = "address:{address}" }})')
    _MINIMIZED.add(address)


def restore(address: str) -> None:
    if address not in _MINIMIZED:
        return
    _MINIMIZED.discard(address)
    dispatch(f'hl.dsp.window.move({{ workspace = "e+0", '
             f'window = "address:{address}" }})')
    dispatch(f'hl.dsp.focus({{ window = "address:{address}" }})')


def main() -> int:
    path = socket_path()
    if path is None:
        print("minimize: no Hyprland socket found", file=sys.stderr)
        return 1

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(str(path))
        buffer = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                return 0                      # compositor gone; systemd restarts us
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                handle(line.decode(errors="replace").strip())


def handle(line: str) -> None:
    # Restore is driven ONLY by `minimized>>addr,0`. An earlier version also
    # restored on any focus change of a minimized window, reasoning that a
    # taskbar click might send plain `activate`. It defeated itself: showing a
    # special workspace focuses the window on it, so the window was pulled back
    # out in the same breath it was put away. Traced event by event.
    if not line.startswith("minimized>>"):
        return
    payload = line.split(">>", 1)[1]
    parts = payload.split(",")
    if len(parts) < 2:
        return
    address, state = parts[0].strip(), parts[1].strip()
    if not address:
        return
    if not address.startswith("0x"):
        address = "0x" + address
    if state == "1":
        minimize(address)
    elif state == "0":
        restore(address)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0) from None
