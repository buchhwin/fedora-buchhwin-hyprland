#!/usr/bin/env bash
#
# The update count, for the bar.
#
#   updates.sh waybar   JSON for a waybar custom module
#   updates.sh count    just the number
#
# Deliberately cheap and deliberately cached. `dnf check-upgrade --refresh`
# takes tens of seconds on a cold cache, and waybar polls this on an interval —
# so the refresh happens at most once an hour, in the background, and the module
# reads whatever the last one found. A bar that stalls for thirty seconds is
# worse than a count that is fifty minutes old.
#
# ⚠️ dnf exits 100 when updates ARE available. Treating that as failure is the
# classic way to build an updates indicator that permanently shows nothing.
set -uo pipefail

CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/buchhwin"
STAMP="$CACHE/updates.count"
MAX_AGE=3600

mkdir -p "$CACHE"

refresh() {
    local n=0 out rc
    out="$(dnf5 check-upgrade --refresh 2>/dev/null)" ; rc=$?
    if (( rc != 0 && rc != 100 )); then
        out="$(dnf check-update --refresh 2>/dev/null)" ; rc=$?
    fi
    if (( rc == 100 )); then
        n="$(printf '%s\n' "$out" | awk 'NF>=3 && $0 !~ /^ / {c++} END {print c+0}')"
    fi

    # Flatpaks: flathub by name. Asking every remote drags in Fedora's OCI one,
    # which wants a polkit authorisation to build its summary — a bar module
    # must never cause a password prompt.
    local f=0
    if command -v flatpak >/dev/null 2>&1; then
        f="$(flatpak remote-ls flathub --updates --columns=application 2>/dev/null \
             | grep -c . || true)"
    fi
    printf '%s\n' "$(( n + f ))" >"$STAMP"
}

stale() {
    [[ -f "$STAMP" ]] || return 0
    local age=$(( $(date +%s) - $(stat -c %Y "$STAMP") ))
    (( age > MAX_AGE ))
}

if stale; then
    # Detached: waybar waits for this command, so the refresh must not be in
    # the path that produces the answer.
    ( refresh ) >/dev/null 2>&1 &
fi

count="$(cat "$STAMP" 2>/dev/null || echo 0)"
[[ "$count" =~ ^[0-9]+$ ]] || count=0

case "${1:-waybar}" in
    count) printf '%s\n' "$count" ;;
    waybar)
        if (( count == 0 )); then
            printf '{}\n'
        else
            printf '{"text":"󰚰 %s","tooltip":"%s update(s) available — click to open the settings","class":"has-updates"}\n' \
                "$count" "$count"
        fi
        ;;
    *) echo "usage: updates.sh waybar|count" >&2; exit 2 ;;
esac
