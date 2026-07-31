#!/usr/bin/env bash
# Gaps on/off — the quick way to "I need the whole screen right now".
#
# hyprctl keyword does not work with a Lua config, so this flips the value in
# settings.lua and reloads. Slower than a keyword call, but it is also the only
# thing that survives the next reload, which is what you actually want.
set -euo pipefail
REPO="${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland"

current="$(python3 "$REPO/scripts/settings.py" get look.gaps_out)"
if [[ "$current" == "0" ]]; then
    python3 "$REPO/scripts/settings.py" set look.gaps_out=12 look.gaps_in=5 >/dev/null
else
    python3 "$REPO/scripts/settings.py" set look.gaps_out=0 look.gaps_in=0 >/dev/null
fi
hyprctl reload >/dev/null
