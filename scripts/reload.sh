#!/usr/bin/env bash
# Reload everything that has a config: compositor, bar, notification centre,
# idle manager.
set -euo pipefail
REPO="${BUCHHWIN_REPO:-${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland}"
[[ -d "$REPO" ]] || REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

hyprctl reload >/dev/null 2>&1 || true
systemctl --user reload-or-restart buchhwin-bar.service 2>/dev/null || true
swaync-client --reload-config 2>/dev/null || true
swaync-client --reload-css 2>/dev/null || true

# hypridle is the odd one out: its config cannot be reloaded, it has to be
# GENERATED from settings.lua first. This is what makes `bhctl set
# idle.lock_after=900` — and a hand edit of settings.lua followed by a reload —
# actually change anything. The dock deliberately stays out: regenerating it
# restarts its waybar instance, and a visible flicker on every reload is worse
# than the setting waiting for the settings window's Apply.
"$REPO/scripts/idle-config.sh" >/dev/null 2>&1 || true

command -v notify-send >/dev/null && notify-send -a Hyprland "Configuration reloaded"
