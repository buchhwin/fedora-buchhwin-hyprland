#!/usr/bin/env bash
# Wallpaper picker: a thumbnail grid, not a list of file names.
#
# This is the one job fuzzel cannot do and rofi can, and it is why rofi is the
# launcher for everything here.
set -euo pipefail
REPO="${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland"
DIRS=("$REPO/wallpapers" "$(xdg-user-dir PICTURES 2>/dev/null || echo "$HOME/Pictures")/Wallpapers")

entries=""
for d in "${DIRS[@]}"; do
    [[ -d "$d" ]] || continue
    while IFS= read -r -d '' f; do
        entries+="$(basename "${f%.*}")\x00icon\x1f${f}\n"
    done < <(find "$d" -maxdepth 2 -type f \
                  \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) -print0)
done

[[ -z "$entries" ]] && { notify-send -a Wallpaper "No wallpapers found" "${DIRS[*]}"; exit 0; }

choice="$(printf "$entries" | rofi -dmenu -i -p "󰸉 Wallpaper" \
    -theme "$HOME/.config/rofi/grid.rasi" -show-icons)"
[[ -z "$choice" ]] && exit 0

for d in "${DIRS[@]}"; do
    for ext in jpg jpeg png webp JPG PNG; do
        cand="$d/$choice.$ext"
        [[ -f "$cand" ]] && { exec "$REPO/scripts/wallpaper.sh" set "$cand"; }
    done
done
