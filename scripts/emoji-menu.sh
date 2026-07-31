#!/usr/bin/env bash
# Emoji picker. Uses the system emoji data, so there is no list to maintain.
set -euo pipefail

DATA="/usr/share/unicode/emoji/emoji-test.txt"
CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/buchhwin/emoji.txt"
mkdir -p "$(dirname "$CACHE")"

if [[ ! -s "$CACHE" || ( -f "$DATA" && "$DATA" -nt "$CACHE" ) ]]; then
    if [[ -f "$DATA" ]]; then
        grep -E '; fully-qualified' "$DATA" \
            | sed -E 's/^.*# ([^ ]+) E[0-9.]+ (.*)$/\1 \2/' >"$CACHE"
    else
        printf '%s\n' "😀 grinning face" "👍 thumbs up" "🎉 party popper" \
                      "🔥 fire" "❤️ red heart" >"$CACHE"
    fi
fi

choice="$(rofi -dmenu -i -p "󰞅 Emoji" -theme "$HOME/.config/rofi/menu.rasi" <"$CACHE")"
[[ -z "$choice" ]] && exit 0
printf '%s' "${choice%% *}" | wl-copy
command -v notify-send >/dev/null && notify-send -a Emoji "Copied" "${choice%% *}"
