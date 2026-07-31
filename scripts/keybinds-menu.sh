#!/usr/bin/env bash
# Searchable keyboard-shortcut cheatsheet, built from settings.lua so it can
# never disagree with the bindings that are actually loaded. Selecting an entry
# runs it, which makes it a second launcher for anything you half-remember.
set -euo pipefail
REPO="${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland"

list="$(python3 "$REPO/scripts/settings.py" dump | python3 -c '
import json, sys
data = json.load(sys.stdin)
width = max((len(b.get("key", "")) for b in data.get("binds", [])), default=20)
for b in data.get("binds", []):
    key = b.get("key", "")
    desc = b.get("desc") or b.get("arg", "")
    print(f"{key:<{width}}  {desc}")
')"

choice="$(printf '%s\n' "$list" | sort | rofi -dmenu -i -p "󰌌 Shortcuts" \
    -theme "$HOME/.config/rofi/menu.rasi" -no-custom)"
[[ -z "$choice" ]] && exit 0

# Fire the binding the user picked, so the cheatsheet is also usable as a menu.
key="${choice%% *}"
hyprctl dispatch sendshortcut "$key" 2>/dev/null || true
