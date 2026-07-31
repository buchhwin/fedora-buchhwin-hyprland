#!/usr/bin/env bash
#
# Wallpaper: one picture, or a folder as a slideshow.
#
#   wallpaper.sh set <file>     use one picture and switch to static mode
#   wallpaper.sh folder <dir>   use a folder and switch to slideshow mode
#   wallpaper.sh next           advance the slideshow now
#   wallpaper.sh restore        put the current wallpaper back (login)
#   wallpaper.sh sync-timer     rewrite the systemd timer from settings.lua
#
# swww rather than hyprpaper, because it can cross-fade. That matters twice: a
# slideshow that hard-cuts every 30 minutes is distracting, and switching
# flavour should look like one change rather than a flicker.
set -euo pipefail

REPO="${BUCHHWIN_REPO:-${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland}"
[[ -d "$REPO" ]] || REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/buchhwin"
UNITS="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
INDEX="$STATE/wallpaper-index"
mkdir -p "$STATE"

get()  { python3 "$REPO/scripts/settings.py" get "$1" 2>/dev/null || true; }
set_() { python3 "$REPO/scripts/settings.py" set "$@" >/dev/null; }

# ---------------------------------------------------------------------------
# Picture list
#
# Sorted, so "alphabetical" is stable and a saved index still points at the same
# picture after a reboot. Symlinks are followed, because a wallpaper folder is
# very often a link to somewhere else.
# ---------------------------------------------------------------------------
list_pictures() {
    local dir="$1"
    [[ -d "$dir" ]] || return 0
    find -L "$dir" -type f \
        \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \
           -o -iname '*.bmp' \) -print 2>/dev/null | sort
}

# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------
_swww_ready() {
    swww query >/dev/null 2>&1 && return 0
    # The daemon is a user service; at login this script can win the race
    # against it, so wait briefly rather than failing outright.
    for _ in $(seq 1 10); do
        sleep 0.5
        swww query >/dev/null 2>&1 && return 0
    done
    return 1
}

apply_to() {
    # apply_to <file> [monitor]
    local file="$1" monitor="${2:-}" transition
    transition="$(get wallpaper.transition)"
    [[ -z "$transition" || "$transition" == "None" ]] && transition="grow"

    local -a args=(img "$file"
        --transition-type "$transition"
        --transition-duration 1.2
        --transition-fps 60)
    [[ -n "$monitor" ]] && args+=(--outputs "$monitor")
    swww "${args[@]}" >/dev/null

    # Only once per change, not once per monitor: with three screens this would
    # otherwise re-render every config three times and reload the bar three
    # times for one picture.
    [[ -z "$monitor" ]] && recolour_from "$file"
}

recolour_from() {
    # Derive the palette from the picture and re-render everything — but only
    # when the user asked for it. Off by default; a fixed family stays fixed.
    [[ "$(get theme.from_wallpaper)" == "True" ]] || return 0
    command -v matugen >/dev/null 2>&1 || return 0

    # A slideshow fires this on a timer, and a click in the wallpaper picker can
    # fire it three times in a second. One at a time, and never a queue: if a
    # recolour is already running, the picture that started it is already the
    # one on screen by the time it finishes.
    local lock="${XDG_RUNTIME_DIR:-/tmp}/buchhwin-recolour.lock"
    exec 9>"$lock"
    flock -n 9 || return 0

    python3 "$REPO/scripts/palette-from-wallpaper.py" "$1" >/dev/null 2>&1 || return 0
    set_ theme.flavour=wallpaper
    python3 "$REPO/theme/apply-theme.py" --flavour wallpaper >/dev/null 2>&1
    hyprctl reload >/dev/null 2>&1 || true
}

monitors() {
    hyprctl -j monitors 2>/dev/null | python3 -c '
import json, sys
try:
    print("\n".join(m["name"] for m in json.load(sys.stdin)))
except Exception:
    pass'
}

# ---------------------------------------------------------------------------
# Choosing the next picture
# ---------------------------------------------------------------------------
next_picture() {
    # next_picture <list-file> <slot>  -> prints one path
    local listfile="$1" slot="${2:-0}" count
    count="$(wc -l <"$listfile")"
    (( count > 0 )) || return 1

    if [[ "$(get wallpaper.order)" == "random" ]]; then
        # Do not repeat the picture that is already up: with a handful of
        # images, pure random repeats often enough to look broken.
        local current pick tries=0
        current="$(cat "$STATE/wallpaper" 2>/dev/null || true)"
        while (( tries < 8 )); do
            pick="$(shuf -n1 "$listfile")"
            [[ "$pick" != "$current" || $count -le 1 ]] && break
            tries=$(( tries + 1 ))
        done
        printf '%s\n' "$pick"
    else
        local idx
        idx="$(cat "$INDEX" 2>/dev/null || echo -1)"
        [[ "$idx" =~ ^-?[0-9]+$ ]] || idx=-1
        idx=$(( (idx + 1 + slot) % count ))
        printf '%s\n' "$idx" >"$INDEX"
        sed -n "$(( idx + 1 ))p" "$listfile"
    fi
}

cmd_next() {
    local folder listfile
    folder="$(get wallpaper.folder)"
    [[ -z "$folder" || "$folder" == "None" ]] && folder="$REPO/wallpapers"
    folder="${folder/#\~/$HOME}"

    listfile="$(mktemp)"
    # shellcheck disable=SC2064  # expand now: the path must survive the trap
    trap "rm -f '$listfile'" RETURN
    list_pictures "$folder" >"$listfile"
    [[ -s "$listfile" ]] || { echo "no pictures in $folder" >&2; return 1; }

    _swww_ready || { echo "swww is not running" >&2; return 1; }

    if [[ "$(get wallpaper.per_monitor)" == "True" ]]; then
        local slot=0 m pic last=""
        while read -r m; do
            [[ -z "$m" ]] && continue
            pic="$(next_picture "$listfile" "$slot")"
            apply_to "$pic" "$m"
            last="$pic"
            slot=$(( slot + 1 ))
        done < <(monitors)
        [[ -n "$last" ]] && printf '%s\n' "$last" >"$STATE/wallpaper"
    else
        local pic
        pic="$(next_picture "$listfile" 0)"
        apply_to "$pic"
        printf '%s\n' "$pic" >"$STATE/wallpaper"
    fi
}

# ---------------------------------------------------------------------------
# The timer
#
# Generated from settings.lua rather than hand-maintained. Otherwise the
# interval shown in the settings and the interval systemd actually uses drift
# apart, and only one of the two is telling the truth.
# ---------------------------------------------------------------------------
cmd_sync_timer() {
    local interval mode
    interval="$(get wallpaper.interval)"; [[ "$interval" =~ ^[0-9]+$ ]] || interval=0
    mode="$(get wallpaper.mode)"

    mkdir -p "$UNITS"
    cat >"$UNITS/buchhwin-wallpaper-next.service" <<'EOF'
[Unit]
Description=Advance the wallpaper slideshow
After=buchhwin-wallpaper.service
PartOf=graphical-session.target

[Service]
Type=oneshot
ExecStart=%h/.local/share/fedora-buchhwin-hyprland/scripts/wallpaper.sh next
EOF

    if [[ "$mode" != "slideshow" ]] || (( interval == 0 )); then
        systemctl --user disable --now buchhwin-wallpaper.timer 2>/dev/null || true
        rm -f "$UNITS/buchhwin-wallpaper.timer"
        systemctl --user daemon-reload 2>/dev/null || true
        echo "  slideshow timer off (mode=$mode, interval=$interval)"
        return 0
    fi

    cat >"$UNITS/buchhwin-wallpaper.timer" <<EOF
[Unit]
Description=Wallpaper slideshow every ${interval}s

[Timer]
OnActiveSec=${interval}
OnUnitActiveSec=${interval}
Unit=buchhwin-wallpaper-next.service
# The wallpaper is cosmetic: a change missed while suspended must not fire a
# burst of catch-up runs on resume.
Persistent=false
AccuracySec=30s

[Install]
WantedBy=graphical-session.target
EOF

    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user enable --now buchhwin-wallpaper.timer 2>/dev/null || true
    echo "  slideshow timer: every ${interval}s"
}

cmd_restore() {
    _swww_ready || exit 0
    if [[ "$(get wallpaper.mode)" == "slideshow" ]]; then
        cmd_next
        return
    fi

    local file flavour
    file="$(get wallpaper.path)"; file="${file/#\~/$HOME}"
    [[ -z "$file" || "$file" == "None" || ! -f "$file" ]] \
        && file="$(cat "$STATE/wallpaper" 2>/dev/null || true)"

    if [[ -z "$file" || ! -f "$file" ]]; then
        # Nothing chosen yet: take the one matching the current flavour.
        flavour="$(get theme.flavour)"; [[ -z "$flavour" ]] && flavour=mocha
        file="$(list_pictures "$REPO/wallpapers" | grep -m1 -- "$flavour" || true)"
        [[ -z "$file" ]] && file="$(list_pictures "$REPO/wallpapers" | head -1)"
    fi
    [[ -f "$file" ]] && { apply_to "$file"; printf '%s\n' "$file" >"$STATE/wallpaper"; }
}

# ---------------------------------------------------------------------------
case "${1:-restore}" in
    set)
        [[ -f "${2:-}" ]] || { echo "usage: wallpaper.sh set <file>" >&2; exit 2; }
        _swww_ready && apply_to "$2"
        printf '%s\n' "$2" >"$STATE/wallpaper"
        set_ "wallpaper.path=$2" "wallpaper.mode=static"
        cmd_sync_timer
        ;;
    folder)
        [[ -d "${2:-}" ]] || { echo "usage: wallpaper.sh folder <dir>" >&2; exit 2; }
        set_ "wallpaper.folder=$2" "wallpaper.mode=slideshow"
        rm -f "$INDEX"
        cmd_next
        cmd_sync_timer
        ;;
    next)       cmd_next ;;
    sync-timer) cmd_sync_timer ;;
    restore)    cmd_restore ;;
    *)
        echo "usage: wallpaper.sh [set <file>|folder <dir>|next|restore|sync-timer]" >&2
        exit 2
        ;;
esac
