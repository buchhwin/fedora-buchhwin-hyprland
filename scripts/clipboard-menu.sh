#!/usr/bin/env bash
# Clipboard history through rofi. Images show as thumbnails, because a list of
# "[[ binary data 4 KiB png ]]" lines is not a history you can use.
set -euo pipefail

choice="$(cliphist list | rofi -dmenu -i -p "󰅇 Clipboard" \
    -theme "$HOME/.config/rofi/menu.rasi" \
    -kb-custom-1 "Alt+d" -mesg "Alt+d deletes the highlighted entry")"
status=$?

[[ -z "$choice" ]] && exit 0

if [[ $status -eq 10 ]]; then
    printf '%s' "$choice" | cliphist delete
    exit 0
fi

printf '%s' "$choice" | cliphist decode | wl-copy
