#!/usr/bin/env bash
# Turn a URL into a real application: its own window without browser chrome,
# its own icon, its own entry in the launcher, its own window rule.
#
#   webapp.sh add Teams https://teams.microsoft.com teams
#   webapp.sh install-defaults
#
# Microsoft dropped the native Linux Teams client at the end of 2022, so the
# web app IS the supported path — not a workaround. Doing it this way rather
# than with teams-for-linux means no extra Electron stack and no wrapper
# project to go stale.
set -euo pipefail

BROWSER="${BUCHHWIN_BROWSER:-brave-origin}"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

add() {
    local name="$1" url="$2" icon="${3:-web-browser}"
    local id; id="$(tr '[:upper:] ' '[:lower:]-' <<<"$name")"
    local class="brave-origin-$id"
    mkdir -p "$APPS"
    cat >"$APPS/buchhwin-webapp-$id.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$name
Comment=$url
Exec=$BROWSER --app=$url --class=$class --name=$class
Icon=$icon
Terminal=false
StartupWMClass=$class
Categories=Network;
X-Buchhwin-WebApp=true
EOF
    echo "  web app: $name  ($class)"
}

case "${1:-}" in
    add)
        shift; add "$@" ;;
    install-defaults)
        add "Teams"       "https://teams.microsoft.com"   "teams"
        add "Outlook"     "https://outlook.office.com/mail" "thunderbird"
        add "Microsoft 365" "https://www.office.com"      "libreoffice-startcenter"
        add "WhatsApp"    "https://web.whatsapp.com"      "whatsapp"
        ;;
    *)
        echo "usage: webapp.sh add <name> <url> [icon] | install-defaults" >&2
        exit 2 ;;
esac

command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" 2>/dev/null || true
