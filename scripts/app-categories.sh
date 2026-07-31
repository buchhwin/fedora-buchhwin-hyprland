#!/usr/bin/env bash
#
# Browse applications by category.
#
# Typing a name is faster when you know it. This is for the other case: you
# want a photo editor and cannot remember which one is installed. rofi's
# -drun-categories filters the launcher to one category; on its own that would
# HIDE everything else, which is why it is not set globally. Here it is a
# deliberate second step, chosen from a list.
#
# Categories are read from the installed .desktop files, so the menu only ever
# offers categories that actually contain something.
set -euo pipefail

APP_DIRS=(
    /usr/share/applications
    /usr/local/share/applications
    "$HOME/.local/share/applications"
    /var/lib/flatpak/exports/share/applications
)

# The freedesktop main categories, in the order people look for them. Anything
# not in this list (Qt, GTK, KDE, X-*) is a toolkit tag, not a category, and
# would only add noise.
declare -A LABEL=(
    [AudioVideo]="  Audio and video"
    [Development]="  Development"
    [Education]="  Education"
    [Game]="  Games"
    [Graphics]="  Graphics"
    [Network]="  Internet"
    [Office]="  Office"
    [Science]="  Science"
    [Settings]="  Settings"
    [System]="  System"
    [Utility]="  Accessories"
)

count_in() {
    local category="$1" n=0 file
    for dir in "${APP_DIRS[@]}"; do
        [[ -d "$dir" ]] || continue
        for file in "$dir"/*.desktop; do
            [[ -f "$file" ]] || continue
            grep -q "^NoDisplay=true" "$file" && continue
            grep -q "^Categories=.*\b$category\b" "$file" && n=$((n + 1))
        done
    done
    printf '%s' "$n"
}

menu=""
declare -A BY_LABEL=()
for category in AudioVideo Development Education Game Graphics Network Office \
                Science Settings System Utility; do
    n="$(count_in "$category")"
    (( n == 0 )) && continue                 # never offer an empty category
    entry="${LABEL[$category]}  ($n)"
    BY_LABEL["$entry"]="$category"
    menu+="$entry"$'\n'
done

[[ -z "$menu" ]] && exec rofi -show drun

chosen="$(printf '%s' "$menu" | rofi -dmenu -i -p "Categories" -no-custom)"
[[ -z "$chosen" ]] && exit 0

exec rofi -show drun -drun-categories "${BY_LABEL[$chosen]}"
