#!/usr/bin/env bash
# Colour picker: hex on the clipboard, and a notification you can actually read
# the value from.
set -euo pipefail
colour="$(hyprpicker -a -f hex)" || exit 0
[[ -z "$colour" ]] && exit 0
command -v notify-send >/dev/null && notify-send -a "Colour picker" "$colour" "Copied to clipboard"
