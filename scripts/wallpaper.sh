#!/usr/bin/env bash
# Wallpaper handling through swww.
#
# swww rather than hyprpaper because it can cross-fade. That matters twice: it
# looks better, and it makes switching flavour feel like one change rather than
# a flicker.
set -euo pipefail
REPO="${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/buchhwin"
mkdir -p "$STATE"

_apply() {
    local file="$1"
    local transition
    transition="$(python3 "$REPO/scripts/settings.py" get wallpaper.transition 2>/dev/null || echo grow)"
    swww img "$file" \
        --transition-type "$transition" \
        --transition-duration 1.2 \
        --transition-fps 60 >/dev/null
    printf '%s\n' "$file" >"$STATE/wallpaper"
}

case "${1:-restore}" in
    set)
        [[ -f "${2:-}" ]] || { echo "usage: wallpaper.sh set <file>" >&2; exit 2; }
        _apply "$2"
        python3 "$REPO/scripts/settings.py" set "wallpaper.path=$2" >/dev/null
        ;;
    restore)
        # Called by the swww user service at login.
        file="$(python3 "$REPO/scripts/settings.py" get wallpaper.path 2>/dev/null || true)"
        [[ -z "$file" || ! -f "$file" ]] && file="$(cat "$STATE/wallpaper" 2>/dev/null || true)"
        if [[ -z "$file" || ! -f "$file" ]]; then
            flavour="$(python3 "$REPO/scripts/settings.py" get theme.flavour 2>/dev/null || echo mocha)"
            file="$(find "$REPO/wallpapers" -iname "*${flavour}*" -type f 2>/dev/null | head -1)"
        fi
        [[ -f "$file" ]] && _apply "$file"
        ;;
    *)
        echo "usage: wallpaper.sh [set <file>|restore]" >&2
        exit 2
        ;;
esac
