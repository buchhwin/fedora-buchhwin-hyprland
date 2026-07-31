#!/usr/bin/env bash
# Screenshot: region / window / screen, straight into satty for annotation.
#
# grim + slurp rather than hyprshot: hyprshot is itself a wrapper around these
# two, and doing it here removes one COPR dependency and lets the annotation
# step and the clipboard behaviour be exactly what we want.
set -euo pipefail

MODE="${1:-region}"
DIR="$(xdg-user-dir PICTURES 2>/dev/null || echo "$HOME/Pictures")/Screenshots"
mkdir -p "$DIR"
FILE="$DIR/$(date +%Y-%m-%d_%H-%M-%S).png"

notify() { command -v notify-send >/dev/null && notify-send -a Screenshot "$@"; }

case "$MODE" in
    region)
        # Dim everything outside the selection so the region is obvious.
        geometry="$(slurp -d -b 11111b99 -c cba6f7ff -w 2 2>/dev/null)" || exit 0
        grim -g "$geometry" "$FILE"
        ;;
    window)
        geometry="$(hyprctl -j activewindow \
            | jq -r '"\(.at[0]),\(.at[1]) \(.size[0])x\(.size[1])"')"
        grim -g "$geometry" "$FILE"
        ;;
    screen)
        grim "$FILE"
        ;;
    *)
        echo "usage: screenshot.sh [region|window|screen]" >&2
        exit 2
        ;;
esac

# Copy first, annotate second: even if you close satty without saving, the
# screenshot is already on the clipboard and on disk.
wl-copy --type image/png < "$FILE"

if command -v satty >/dev/null; then
    satty --filename "$FILE" --output-filename "$FILE" \
          --early-exit --copy-command wl-copy --initial-tool brush \
          --disable-notifications || true
fi

notify "Screenshot saved" "$FILE"
