#!/usr/bin/env bash
# Reload everything that has a config: compositor, bar, notification centre.
set -euo pipefail
hyprctl reload >/dev/null 2>&1 || true
systemctl --user reload-or-restart buchhwin-bar.service 2>/dev/null || true
swaync-client --reload-config 2>/dev/null || true
swaync-client --reload-css 2>/dev/null || true
command -v notify-send >/dev/null && notify-send -a Hyprland "Configuration reloaded"
