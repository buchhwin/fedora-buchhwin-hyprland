#!/usr/bin/env bash
#
# fedora-buchhwin-hyprland — installer
#
# Turns a bare Fedora Server into a Catppuccin-themed Hyprland desktop.
# Safe to run twice: every phase is idempotent.
#
#   ./install.sh --dry-run          show everything it would do, change nothing
#   ./install.sh                    interactive install
#   ./install.sh --unattended       no questions (used by the test VMs)
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export REPO_DIR

TARGET_FEDORA=44
THEME_FLAVOUR="mocha"
THEME_ACCENT="mauve"
IS_VM=0

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
ONLY_PHASES=()
SKIP_PHASES=()
WITH_GROUPS=()
FLAVOUR_SET=0
ACCENT_SET=0

usage() {
    cat <<'EOF'
Usage: ./install.sh [options]

  --dry-run              Print every action without changing anything.
  --unattended           Never ask a question; assume yes.
  --minimal              Desktop only: no applications, no sysadmin toolkit.
  --with GROUP           Add an optional package group (repeatable).
                         Available: k8s iac db analysis virt backup
                         Nothing is installed from these unless you ask.
  --no-flatpak           Skip Flathub and all Flatpaks.
  --no-tweaks            Leave system settings alone (journal size, mDNS,
                         power profiles, oomd).
  --no-firewall          Do not install or enable ufw.
  --profile work|showcase
                         Visual profile. "work" is quick and restrained,
                         "showcase" is slower with more blur for screenshots.
  --gpu amd|nvidia|intel|none|auto
                         Graphics driver branch. Default: auto-detect.
  --software-render      Render on the CPU: switch blur, shadows, animations
                         and transparency off and pin Mesa to llvmpipe. Use
                         this when the session starts to a black screen in a
                         virtual machine whose 3D the installer cannot verify
                         — VirtualBox in particular. Detected automatically
                         for a VM without VirGL.
  --flavour NAME         Palette: mocha, latte, nord, gruvbox, dracula,
                         tokyo-night, rose-pine, ... (theme/palettes/).
  --accent NAME          Accent colour; which ones exist depends on the
                         palette (see its "accents" list).
  --lang en|de           Interface language of the installer. Default: en.
  --only PHASE           Run only this phase (repeatable).
  --skip PHASE           Skip this phase (repeatable).
  -h, --help             This text.

Phases: preflight setup repos tweaks base hyprland apps theme dotfiles
        services vm firewall summary

The "setup" phase is the short set of questions at the start (language,
keyboard, timezone, hostname, palette). --unattended and --skip setup both
turn it off; every answer also has its own flag.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)     DRY_RUN=1 ;;
        --unattended)  UNATTENDED=1 ;;
        --minimal)     MINIMAL=1 ;;
        --with)        WITH_GROUPS+=("${2:?}"); shift ;;
        --no-flatpak)  NO_FLATPAK=1 ;;
        --no-tweaks)   NO_TWEAKS=1 ;;
        --no-firewall) NO_FIREWALL=1 ;;
        --profile)     PROFILE="${2:?}"; shift ;;
        --gpu)         GPU="${2:?}"; shift ;;
        --software-render) SOFTWARE_RENDER=1 ;;
        --flavour)     THEME_FLAVOUR="${2:?}"; FLAVOUR_SET=1; shift ;;
        --accent)      THEME_ACCENT="${2:?}"; ACCENT_SET=1; shift ;;
        --lang)        LANG_CHOICE="${2:?}"; shift ;;
        --only)        ONLY_PHASES+=("${2:?}"); shift ;;
        --skip)        SKIP_PHASES+=("${2:?}"); shift ;;
        -h|--help)     usage; exit 0 ;;
        *)             printf 'Unknown option: %s\n\n' "$1" >&2; usage; exit 2 ;;
    esac
    shift
done

export DRY_RUN UNATTENDED MINIMAL NO_FLATPAK NO_TWEAKS NO_FIREWALL PROFILE GPU LANG_CHOICE
export SOFTWARE_RENDER="${SOFTWARE_RENDER:-0}"
export WITH_GROUPS_STR="${WITH_GROUPS[*]:-}"
export THEME_FLAVOUR THEME_ACCENT TARGET_FEDORA IS_VM
# Whether the palette came from the command line. The setup phase asks only
# about things the user has not already answered with a flag.
export FLAVOUR_SET ACCENT_SET
# Filled in by the setup phase, consumed by the dotfiles phase — settings.lua
# does not exist yet at the time the question is asked.
SETUP_KB_LAYOUT=""; SETUP_KB_VARIANT=""
export SETUP_KB_LAYOUT SETUP_KB_VARIANT

# ---------------------------------------------------------------------------
# Load helpers and phases
# ---------------------------------------------------------------------------
# shellcheck source=lib/common.sh
source "$REPO_DIR/lib/common.sh"

mkdir -p "$STATE_DIR"
: >"$LOG_FILE"

i18n_load "$(resolve_lang)"

for f in "$REPO_DIR"/lib/[0-9][0-9]-*.sh; do
    # shellcheck source=/dev/null
    source "$f"
done

# ---------------------------------------------------------------------------
# Error handling — the single most important difference from the old script.
# A failing command stops the run and says exactly where it stopped, instead of
# carrying on and reporting success.
# ---------------------------------------------------------------------------
on_error() {
    local code=$? line=$1
    sudo_done
    printf '\n%sx%s %s\n' "$C_RED" "$C_RESET" "$(msg err_trap "$line" "$code")" >&2
    printf '  %s\n\n' "$(msg sum_log "$LOG_FILE")" >&2
    exit "$code"
}
trap 'on_error $LINENO' ERR
trap 'sudo_done' EXIT

# ---------------------------------------------------------------------------
# Phase selection
# ---------------------------------------------------------------------------
should_run() {
    local name="$1" p
    if (( ${#ONLY_PHASES[@]} )); then
        for p in "${ONLY_PHASES[@]}"; do [[ "$p" == "$name" ]] && return 0; done
        return 1
    fi
    for p in "${SKIP_PHASES[@]}"; do [[ "$p" == "$name" ]] && return 1; done
    return 0
}

# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
printf '\n%s%s%s\n' "$C_BOLD$C_MAUVE" "$(msg banner)" "$C_RESET"
printf '%s%s%s\n' "$C_DIM" "$(msg banner_sub "$THEME_FLAVOUR" "$THEME_ACCENT" "$PROFILE")" "$C_RESET"
(( DRY_RUN )) && printf '%s%s%s\n' "$C_YELLOW" "$(msg banner_dry)" "$C_RESET"

# The language comes before everything else, so that the rest of the run —
# including preflight, which is allowed to abort — speaks the language the user
# picked instead of one guessed from $LANG. The tables are reloaded with the
# answer. Skipped when --lang already said so, and when nobody is watching.
if [[ -z "$LANG_CHOICE" ]] && ! (( UNATTENDED )) && ! (( DRY_RUN )) \
   && should_run setup; then
    LANG_CHOICE="$(ask_choice "$(msg ask_language)" "$(resolve_lang)" en de)"
    export LANG_CHOICE
    i18n_load "$LANG_CHOICE"
fi

should_run preflight && phase_preflight
sudo_init
should_run setup     && phase_setup
should_run repos     && phase_repos
should_run tweaks    && phase_tweaks
should_run base      && phase_base
should_run hyprland  && phase_hyprland
should_run apps      && phase_apps
should_run theme     && phase_theme
should_run dotfiles  && phase_dotfiles
should_run services  && phase_services
should_run vm        && phase_vm_tweaks
# The firewall goes last: enabling a default-deny policy mid-run would cut the
# SSH connection the installer is often running over.
should_run firewall  && phase_firewall

# Remember the language so bhctl and the GUI agree with the installer.
if ! (( DRY_RUN )); then
    printf '%s\n' "$(resolve_lang)" >"$STATE_DIR/lang"
fi

trap - ERR
should_run summary && phase_summary

# The line above must not be the last thing the script does. `a && b` leaves
# the status of `a` when it short-circuits, so any run that filters the summary
# phase out — every `--only` that does not name it — exited 1 and reported a
# perfectly good install as a failure.
exit 0
