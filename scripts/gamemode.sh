#!/usr/bin/env bash
#
# Game mode: turn off everything that costs frames, and put it back.
#
# Blur, shadows, animations and the gaps are what make the desktop look like
# this, and every one of them is work the GPU does instead of drawing the game.
# One key turns them off; the same key turns them back on.
#
# The state lives in settings.lua like everything else, so the settings window
# shows the truth while game mode is on rather than the values you will get back.
set -euo pipefail
REPO="${BUCHHWIN_REPO:-${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland}"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/buchhwin"
SAVED="$STATE/gamemode.json"
SETTINGS="$REPO/scripts/settings.py"

mkdir -p "$STATE"

get() { python3 "$SETTINGS" get "$1" 2>/dev/null || true; }

if [[ -f "$SAVED" ]]; then
    # --- off: restore exactly what was there ---------------------------------
    python3 - "$SETTINGS" "$SAVED" <<'PY'
import json, subprocess, sys
settings, saved = sys.argv[1], sys.argv[2]
with open(saved) as fh:
    values = json.load(fh)
subprocess.run([sys.executable, settings, "set",
                *[f"{k}={json.dumps(v) if isinstance(v, bool) else v}".replace("true", "true")
                  for k, v in values.items()]], check=False)
PY
    rm -f "$SAVED"
    notify-send -a Hyprland "Game mode off" "Blur, shadows and animations are back" 2>/dev/null || true
else
    # --- on: remember, then strip -------------------------------------------
    python3 - "$SETTINGS" "$SAVED" <<'PY'
import json, subprocess, sys
settings, saved = sys.argv[1], sys.argv[2]
keys = ["look.blur", "look.shadow", "look.animations", "look.gaps_in", "look.gaps_out"]
values = {}
for key in keys:
    out = subprocess.run([sys.executable, settings, "get", key],
                         capture_output=True, text=True, check=False).stdout.strip()
    if out and not out.startswith("not found"):
        values[key] = out
with open(saved, "w") as fh:
    json.dump(values, fh)
PY
    python3 "$SETTINGS" set look.blur=false look.shadow=false \
        look.animations=false look.gaps_in=0 look.gaps_out=0 >/dev/null
    notify-send -a Hyprland "Game mode on" "Blur, shadows, animations and gaps are off" 2>/dev/null || true
fi

hyprctl reload >/dev/null 2>&1 || true
