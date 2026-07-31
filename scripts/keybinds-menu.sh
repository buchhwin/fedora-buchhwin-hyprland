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
#
# Lua syntax: with a Lua config provider `hyprctl dispatch sendshortcut KEY`
# arrives as hl.dispatch(sendshortcut KEY) and dies on a syntax error. The
# dispatcher is also spelled send_shortcut there, not sendshortcut.
key="${choice%% *}"
mods="${key%+*}"; bare="${key##*+}"
[[ "$mods" == "$key" ]] && mods=""
hyprctl dispatch "hl.dsp.send_shortcut({ key = \"$bare\", mods = \"$mods\" })" >/dev/null 2>&1 || true
