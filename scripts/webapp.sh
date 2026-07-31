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

# Fetch a site's icon into the user icon directory. A launcher entry with a
# generic globe next to five other generic globes is unusable, and this is a
# one-off cost at install time.
fetch_icon() {
    local id="$1" url="$2"
    local dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
    local out="$dir/buchhwin-$id.png"
    [[ -s "$out" ]] && { printf 'buchhwin-%s' "$id"; return; }
    mkdir -p "$dir"
    local host; host="$(sed -E 's#^https?://([^/]+).*#\1#' <<<"$url")"
    # Google's favicon service normalises size and format, which saves parsing
    # every site's HTML for whichever icon tag it happens to use.
    if curl -fsSL --max-time 15 -o "$out.tmp" \
        "https://www.google.com/s2/favicons?sz=256&domain=$host" 2>/dev/null \
        && [[ -s "$out.tmp" ]]; then
        mv "$out.tmp" "$out"
        printf 'buchhwin-%s' "$id"
        return
    fi
    rm -f "$out.tmp"
    printf 'web-browser'
}

add() {
    local name="$1" url="$2" icon="${3:-web-browser}"
    local id; id="$(tr '[:upper:] ' '[:lower:]-' <<<"$name")"
    local class="brave-origin-$id"
    mkdir -p "$APPS"
    icon="$(fetch_icon "$id" "$url")"
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
        # ChatGPT and Claude have no official Linux desktop app — the desktop
        # builds are Windows and macOS only, and neither is on Flathub
        # (checked: "App not found" for com.openai.ChatGPT and
        # com.anthropic.Claude). Community Electron wrappers exist and are
        # deliberately not used: they lag behind changes and go unmaintained.
        # The web app in its own window is the honest answer, and it is exactly
        # what Microsoft themselves point at for Teams.
        add "ChatGPT"     "https://chatgpt.com"           "chatgpt"
        add "Claude"      "https://claude.ai"             "claude"
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
