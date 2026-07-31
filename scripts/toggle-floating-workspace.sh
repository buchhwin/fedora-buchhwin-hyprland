#!/usr/bin/env bash
#
# Turn the current workspace into a floating one, and back.
#
# A floating workspace behaves like Windows: nothing tiles, windows drag freely
# and snap magnetically to edges and to each other. Every other workspace keeps
# tiling. That is the point — you get both, and you decide per workspace which
# one you are in right now.
set -euo pipefail
REPO="${BUCHHWIN_REPO:-${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland}"
[[ -d "$REPO" ]] || REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ws="$(hyprctl -j activeworkspace | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"

python3 - "$REPO" "$ws" <<'PY'
import subprocess, sys
sys.path.insert(0, sys.argv[1] + "/scripts")
import settings as S

ws = int(sys.argv[2])
data = S.read()
layout = data.setdefault("layout", {})
current = list(layout.get("floating_workspaces") or [])

if ws in current:
    current.remove(ws)
    state = "tiling"
else:
    current.append(ws)
    state = "floating"
layout["floating_workspaces"] = sorted(current)
S.write(data)

# Existing windows are not covered by the workspace rule — that only applies to
# new ones. So flip what is already open, otherwise the switch appears to do
# nothing until you open something.
clients = subprocess.run(["hyprctl", "-j", "clients"], capture_output=True, text=True).stdout
import json
for c in json.loads(clients or "[]"):
    if c.get("workspace", {}).get("id") == ws:
        want_float = state == "floating"
        if bool(c.get("floating")) != want_float:
            # Lua syntax. `hyprctl dispatch setfloating address:0x...` is a Lua
            # syntax error under a Lua config provider and does nothing, while
            # still exiting 0 — which is why toggling a workspace to floating
            # appeared to work and left every open window tiled.
            action = "on" if want_float else "off"
            subprocess.run(
                ["hyprctl", "dispatch",
                 'hl.dsp.window.float({ action = "%s", window = "address:%s" })'
                 % (action, c["address"])],
                capture_output=True)

subprocess.run(["hyprctl", "reload"], capture_output=True)
subprocess.run(["notify-send", "-a", "Hyprland", f"Workspace {ws}: {state}"],
               capture_output=True)
print(f"workspace {ws}: {state}")
PY
