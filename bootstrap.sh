#!/usr/bin/env bash
#
# fedora-buchhwin-hyprland — one-line bootstrap
#
#   curl -fsSL https://buchhwin.github.io/fedora-buchhwin-hyprland/install | bash
#
# Deliberately small enough to read in one screen before piping it to a shell.
# It does three things and nothing else: check the system, fetch the repo, hand
# over to install.sh. Every argument is passed straight through:
#
#   ... | bash -s -- --dry-run
#
set -euo pipefail

REPO_URL="${BUCHHWIN_REPO_URL:-https://github.com/buchhwin/fedora-buchhwin-hyprland.git}"
REPO_REF="${BUCHHWIN_REPO_REF:-main}"
DEST="${BUCHHWIN_DEST:-${XDG_DATA_HOME:-$HOME/.local/share}/fedora-buchhwin-hyprland}"

red()  { printf '\033[38;5;203m%s\033[0m\n' "$*" >&2; }
info() { printf '\033[38;5;111m==>\033[0m %s\n' "$*"; }

[[ $EUID -ne 0 ]] || { red "Run this as your normal user, not as root."; exit 1; }

if [[ ! -r /etc/os-release ]] || ! grep -q '^ID=fedora' /etc/os-release; then
    red "This installer is for Fedora only."
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    info "Installing git..."
    sudo dnf install -y git
fi

if [[ -d "$DEST/.git" ]]; then
    info "Updating $DEST"
    git -C "$DEST" fetch --quiet origin "$REPO_REF"
    git -C "$DEST" checkout --quiet "$REPO_REF"
    git -C "$DEST" pull --quiet --ff-only
else
    info "Cloning into $DEST"
    mkdir -p "$(dirname "$DEST")"
    git clone --quiet --branch "$REPO_REF" "$REPO_URL" "$DEST"
fi

chmod +x "$DEST/install.sh"
info "Starting the installer"
exec "$DEST/install.sh" "$@"
