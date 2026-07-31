#!/usr/bin/env bash
# Screen recording toggle. Same key starts and stops it; the bar shows a
# blinking red dot while it runs, so it cannot be forgotten.
set -euo pipefail

DIR="$(xdg-user-dir VIDEOS 2>/dev/null || echo "$HOME/Videos")/Recordings"
mkdir -p "$DIR"

if pgrep -x wf-recorder >/dev/null; then
    pkill -INT -x wf-recorder
    command -v notify-send >/dev/null && notify-send -a Recording "Stopped" "$DIR"
    exit 0
fi

FILE="$DIR/$(date +%Y-%m-%d_%H-%M-%S).mp4"
if [[ "${1:-screen}" == "region" ]]; then
    geometry="$(slurp -d -b 11111b99 -c f38ba8ff -w 2)" || exit 0
    wf-recorder -g "$geometry" -f "$FILE" &
else
    wf-recorder -f "$FILE" &
fi
command -v notify-send >/dev/null && notify-send -a Recording "Started" "SUPER+SHIFT+V to stop"
