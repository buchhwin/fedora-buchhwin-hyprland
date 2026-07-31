#!/usr/bin/env bash
#
# Clipboard history through rofi, with thumbnails for images.
#
# The comment here used to claim images showed as thumbnails. They did not:
# `cliphist list` went straight into rofi, so a copied screenshot appeared as
# "[[ binary data 4 KiB png 800x600 ]]" and the only way to find the right one
# was to try them in turn. Each image entry is now decoded once into a cache
# and handed to rofi as an icon.
set -euo pipefail

CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/buchhwin/clipboard"
mkdir -p "$CACHE"

# Drop thumbnails cliphist no longer knows about. Without this the cache grows
# for the life of the machine, one file per image ever copied.
prune() {
    local ids file id
    ids="$(cliphist list | cut -f1)"
    for file in "$CACHE"/*.png; do
        [[ -e "$file" ]] || continue
        id="$(basename "$file" .png)"
        grep -qx -- "$id" <<<"$ids" || rm -f "$file"
    done
}

# rofi's dmenu mode takes a per-row icon as:  text \0 icon \x1f path
entries() {
    local line id rest thumb
    while IFS= read -r line; do
        id="${line%%$'\t'*}"
        rest="${line#*$'\t'}"
        if [[ "$rest" == *"binary data"* ]]; then
            thumb="$CACHE/$id.png"
            if [[ ! -f "$thumb" ]]; then
                # Decoded once. A failure is not fatal — the row simply keeps
                # its text description instead of gaining a picture.
                cliphist decode <<<"$line" >"$thumb" 2>/dev/null || rm -f "$thumb"
            fi
            if [[ -s "$thumb" ]]; then
                printf '%s\0icon\x1f%s\n' "$line" "$thumb"
                continue
            fi
        fi
        printf '%s\n' "$line"
    done < <(cliphist list)
}

prune

# rofi exits 10 for the custom key and 1 when cancelled, so errexit has to be
# off around it or Alt+d would kill the script instead of deleting an entry.
set +e
choice="$(entries | rofi -dmenu -i -p "󰅇 Clipboard" \
    -show-icons \
    -theme "$HOME/.config/rofi/menu.rasi" \
    -kb-custom-1 "Alt+d" -mesg "Alt+d deletes the highlighted entry")"
status=$?
set -e

[[ -z "$choice" ]] && exit 0

if [[ $status -eq 10 ]]; then
    printf '%s' "$choice" | cliphist delete
    exit 0
fi

printf '%s' "$choice" | cliphist decode | wl-copy
