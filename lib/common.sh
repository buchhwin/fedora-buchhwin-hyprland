#!/usr/bin/env bash
# Shared helpers for install.sh, bhctl and the lib/NN-*.sh phases.
# Sourced, never executed directly.

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# shellcheck disable=SC2034
# The paths below are consumed by the lib/NN-*.sh phases, by bin/bhctl and by
# the helper scripts — all of which source this file. shellcheck analyses one
# file at a time and cannot see that, so it reports them as unused.
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/buchhwin"
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
BIN_HOME="$HOME/.local/bin"
LOG_FILE="${LOG_FILE:-$STATE_DIR/install-$(date +%Y%m%d-%H%M%S).log}"

# ---------------------------------------------------------------------------
# Options (install.sh overrides these from the command line)
# ---------------------------------------------------------------------------
DRY_RUN="${DRY_RUN:-0}"
UNATTENDED="${UNATTENDED:-0}"
MINIMAL="${MINIMAL:-0}"
NO_FLATPAK="${NO_FLATPAK:-0}"
NO_TWEAKS="${NO_TWEAKS:-0}"
NO_FIREWALL="${NO_FIREWALL:-0}"
PROFILE="${PROFILE:-work}"
GPU="${GPU:-auto}"
LANG_CHOICE="${LANG_CHOICE:-}"

# ---------------------------------------------------------------------------
# Colours — only when stdout is a terminal, so logs stay readable
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
    C_BLUE=$'\033[38;5;111m'; C_GREEN=$'\033[38;5;114m'
    C_YELLOW=$'\033[38;5;179m'; C_RED=$'\033[38;5;203m'
    C_MAUVE=$'\033[38;5;183m'
else
    C_RESET=''; C_BOLD=''; C_DIM=''
    C_BLUE=''; C_GREEN=''; C_YELLOW=''; C_RED=''; C_MAUVE=''
fi

# ---------------------------------------------------------------------------
# Translations
#
# msg <key> [printf args...]
#
# Looks up the key in the selected language, falling back to English when the
# key is missing. A missing key can therefore never produce an empty message —
# it degrades to English, and only a key missing from BOTH files prints the raw
# key so the omission is obvious rather than silent.
# ---------------------------------------------------------------------------
declare -A MSG_EN=() MSG_LOCAL=()

i18n_load() {
    local lang="${1:-en}"
    # shellcheck source=/dev/null
    source "$REPO_DIR/i18n/en.sh"
    local k
    for k in "${!MSG[@]}"; do MSG_EN["$k"]="${MSG[$k]}"; done
    unset MSG; declare -gA MSG=()

    if [[ "$lang" != "en" && -f "$REPO_DIR/i18n/$lang.sh" ]]; then
        # shellcheck source=/dev/null
        source "$REPO_DIR/i18n/$lang.sh"
        for k in "${!MSG[@]}"; do MSG_LOCAL["$k"]="${MSG[$k]}"; done
    fi
    unset MSG
}

msg() {
    local key="$1"; shift
    local fmt="${MSG_LOCAL[$key]:-${MSG_EN[$key]:-}}"
    if [[ -z "$fmt" ]]; then
        printf '%s' "$key"          # untranslated key: visible, not empty
        return
    fi
    # shellcheck disable=SC2059  # the format string is ours, from i18n/*.sh
    printf "$fmt" "$@"
}

# Resolve the interface language: explicit flag > saved choice > $LANG > en.
resolve_lang() {
    local l="$LANG_CHOICE"
    [[ -z "$l" && -f "$STATE_DIR/lang" ]] && l="$(<"$STATE_DIR/lang")"
    [[ -z "$l" ]] && l="${LANG%%_*}"
    case "$l" in
        de) echo de ;;
        *)  echo en ;;
    esac
}

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
_log() { printf '%s %s\n' "$(date '+%F %T')" "$1" >>"$LOG_FILE"; }

section() { printf '\n%s%s==>%s %s%s%s\n' "$C_BOLD" "$C_MAUVE" "$C_RESET" "$C_BOLD" "$1" "$C_RESET"; _log "== $1"; }
step()    { printf '  %s->%s %s\n' "$C_BLUE" "$C_RESET" "$1"; _log "-- $1"; }
ok()      { printf '  %s v%s %s\n' "$C_GREEN" "$C_RESET" "$1"; _log "ok $1"; }
warn()    { printf '  %s!%s  %s\n' "$C_YELLOW" "$C_RESET" "$1" >&2; _log "WARN $1"; WARNINGS+=("$1"); }
fail()    { printf '  %sx%s  %s\n' "$C_RED" "$C_RESET" "$1" >&2; _log "FAIL $1"; FAILURES+=("$1"); }
info()    { printf '     %s%s%s\n' "$C_DIM" "$1" "$C_RESET"; }
die()     { printf '\n%sx%s %s\n' "$C_RED" "$C_RESET" "$1" >&2; _log "DIE $1"; exit "${2:-1}"; }

# ---------------------------------------------------------------------------
# Summary bookkeeping
# ---------------------------------------------------------------------------
declare -a INSTALLED=() SKIPPED=() WARNINGS=() FAILURES=()

# ---------------------------------------------------------------------------
# Command execution
#
# run <cmd...>       run it, or print it when --dry-run is active
# run_quiet <cmd...> same, but output goes to the log only
# ---------------------------------------------------------------------------
run() {
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s %s\n' "$C_DIM" "$C_RESET" "$*"
        _log "dry-run: $*"
        return 0
    fi
    _log "run: $*"
    "$@"
}

run_quiet() {
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s %s\n' "$C_DIM" "$C_RESET" "$*"
        _log "dry-run: $*"
        return 0
    fi
    _log "run: $*"
    "$@" >>"$LOG_FILE" 2>&1
}

# ---------------------------------------------------------------------------
# sudo
#
# Asked for once, up front, then kept alive by a background refresher. The old
# script asked for the password at random points, including at the very end.
#
# NOT `sudo -v`. That validates against EVERY matching sudoers rule, so on a
# machine where the user is both in wheel (password required) and covered by a
# NOPASSWD rule, it insists on a password that no individual command actually
# needs — and then fails outright without a TTY:
#
#     User buchhwin may run the following commands:
#         (ALL) ALL                <- wheel, wants a password
#         (ALL) NOPASSWD: ALL      <- what every command actually uses
#
# So: ask `sudo -n true` first. If passwordless sudo works, nothing needs to be
# prompted for and no keep-alive is necessary. Only otherwise fall back to an
# interactive prompt — and refuse that outright when unattended, instead of
# hanging on a prompt nobody will see.
# ---------------------------------------------------------------------------
SUDO_KEEPALIVE_PID=""
# shellcheck disable=SC2034  # read by the phases, which source this file
SUDO_PASSWORDLESS=0

sudo_init() {
    (( DRY_RUN )) && return 0
    if [[ $EUID -eq 0 ]]; then
        die "$(msg err_running_as_root)"
    fi

    if sudo -n true 2>/dev/null; then
        SUDO_PASSWORDLESS=1
        ok "$(msg ok_sudo_passwordless)"
        return 0
    fi

    if (( UNATTENDED )); then
        die "$(msg err_sudo_unattended)"
    fi

    sudo -v || die "$(msg err_no_sudo)"
    # Refresh the timestamp while long package installs run, so the password is
    # asked for once at the start rather than again halfway through.
    ( while true; do sudo -n true 2>/dev/null; sleep 50
        kill -0 "$$" 2>/dev/null || exit; done ) &
    SUDO_KEEPALIVE_PID=$!
}

sudo_done() {
    [[ -n "$SUDO_KEEPALIVE_PID" ]] && kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
    SUDO_KEEPALIVE_PID=""
}

# ---------------------------------------------------------------------------
# Package list files
#
# read_list <file>  ->  package names, one per line, comments and inline
#                       "# ..." trailers stripped
# ---------------------------------------------------------------------------
read_list() {
    local f="$1"
    [[ -f "$f" ]] || { warn "$(msg warn_missing_list "$f")"; return 0; }
    sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' "$f"
}

# dnf_install <package...> — skips what is already installed, so a second run
# is a no-op instead of a long reinstall.
dnf_install() {
    local -a want=("$@") todo=()
    (( ${#want[@]} )) || return 0
    local p
    for p in "${want[@]}"; do
        if (( DRY_RUN )); then
            todo+=("$p")
        elif rpm -q "$p" >/dev/null 2>&1; then
            SKIPPED+=("$p")
        else
            todo+=("$p")
        fi
    done
    if (( ${#todo[@]} == 0 )); then
        info "$(msg info_all_present)"
        return 0
    fi
    step "$(msg step_installing "${#todo[@]}")"
    info "${todo[*]}"
    if run sudo dnf install -y "${todo[@]}"; then
        INSTALLED+=("${todo[@]}")
    else
        fail "$(msg fail_dnf_group)"
        # Retry one by one so a single bad name cannot take the whole list down.
        for p in "${todo[@]}"; do
            if run_quiet sudo dnf install -y "$p"; then
                INSTALLED+=("$p")
            else
                fail "$(msg fail_pkg "$p")"
            fi
        done
    fi
}

# ---------------------------------------------------------------------------
# Idempotent linking
#
# link_config <source-in-repo> <target>
#
# Configs are symlinked out of the cloned repo, not copied. `git pull` then
# updates every config at once, and there is no half-copied state to reason
# about. An existing real file is moved aside once, with a timestamp.
# ---------------------------------------------------------------------------
link_config() {
    local src="$REPO_DIR/$1" dst="$2"
    [[ -e "$src" ]] || { warn "$(msg warn_missing_src "$1")"; return 0; }

    if [[ -L "$dst" && "$(readlink -f "$dst")" == "$(readlink -f "$src")" ]]; then
        return 0                                   # already correct
    fi
    run mkdir -p "$(dirname "$dst")"
    if [[ -e "$dst" || -L "$dst" ]]; then
        local backup
        backup="$dst.bak-$(date +%Y%m%d-%H%M%S)"
        step "$(msg step_backup "$dst" "$backup")"
        run mv "$dst" "$backup"
    fi
    run ln -s "$src" "$dst"
}

# Append a block to a file exactly once, marked so it can be found and updated.
# The old script used a bare `cat >>`, which duplicated on every run.
ensure_block() {
    local file="$1" marker="$2" content="$3"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s ensure block %s in %s\n' "$C_DIM" "$C_RESET" "$marker" "$file"
        return 0
    fi
    mkdir -p "$(dirname "$file")"
    touch "$file"
    if grep -qF "# >>> $marker >>>" "$file"; then
        # Replace the existing block instead of appending a second one.
        local tmp; tmp="$(mktemp)"
        awk -v m="$marker" '
            $0 == "# >>> " m " >>>" { skip = 1 }
            !skip { print }
            $0 == "# <<< " m " <<<" { skip = 0 }
        ' "$file" >"$tmp"
        mv "$tmp" "$file"
    fi
    { printf '\n# >>> %s >>>\n' "$marker"
      printf '%s\n' "$content"
      printf '# <<< %s <<<\n' "$marker"
    } >>"$file"
}

# ---------------------------------------------------------------------------
# Environment facts
# ---------------------------------------------------------------------------
fedora_version() { rpm -E %fedora 2>/dev/null || echo 0; }

is_vm() {
    local v; v="$(systemd-detect-virt 2>/dev/null || echo none)"
    [[ "$v" != "none" ]]
}

# Is there accelerated rendering, or will everything land on the CPU?
#
# Measured on the test VM in both states, because the obvious test is wrong:
# /dev/dri/renderD128 exists even when virtio-gpu runs WITHOUT VirGL, so the
# presence of a render node proves nothing. What does differ is the negotiated
# virtio feature bit 0 (VIRTIO_GPU_F_VIRGL) on the device bound to virtio_gpu:
# 1 with VirGL, 0 without.
#
# No virtio GPU at all means real hardware or passthrough — accelerated.
gpu_is_accelerated() {
    local dev drv
    for dev in /sys/bus/virtio/devices/*/; do
        [[ -e "$dev/driver" ]] || continue
        drv="$(basename "$(readlink -f "$dev/driver")")"
        [[ "$drv" == "virtio_gpu" ]] || continue
        [[ -r "$dev/features" ]] || return 1
        [[ "$(cut -c1 <"$dev/features")" == "1" ]]
        return $?
    done
    return 0
}

detect_gpu() {
    if lspci 2>/dev/null | grep -qiE 'vga|3d|display' ; then
        local line; line="$(lspci 2>/dev/null | grep -iE 'vga|3d|display' | head -1)"
        case "$line" in
            *NVIDIA*|*nVidia*) echo nvidia ;;
            *AMD*|*ATI*|*Radeon*) echo amd ;;
            *Intel*) echo intel ;;
            *Red\ Hat*|*Virtio*|*QXL*|*Cirrus*|*VMware*) echo none ;;
            *) echo none ;;
        esac
    else
        echo none
    fi
}

confirm() {
    (( UNATTENDED )) && return 0
    (( DRY_RUN )) && return 0
    local reply
    read -r -p "  $1 [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]]
}
