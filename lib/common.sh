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
    # Cleared, because this is called a SECOND time once the setup phase has
    # asked which language to use. Without it, switching de -> en would leave
    # the German table in place and keep answering in German.
    MSG_LOCAL=()
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
    # Screen AND log. This used to be a bare "$@", so the output went to the
    # screen only and the log held nothing but the command line — while the
    # summary underneath still promised a "full log". When two Flatpaks failed,
    # the reason had scrolled off the screen and existed nowhere else.
    #
    # PIPESTATUS rather than pipefail: this file is also sourced by scripts
    # that do not set it, and the status of the command must not become the
    # status of tee.
    "$@" 2>&1 | tee -a "$LOG_FILE"
    local rc="${PIPESTATUS[0]}"
    return "$rc"
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

# run_capture <file> <cmd...>
#
# Like run_quiet, but the output also lands in <file> so the CALLER can quote
# the actual error. "The system update did not finish cleanly" is not a fault
# report, it is a shrug; the reason belongs in the message, not only in a log
# the user then has to go and find.
run_capture() {
    local out="$1"; shift
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s %s\n' "$C_DIM" "$C_RESET" "$*"
        _log "dry-run: $*"
        : >"$out"
        return 0
    fi
    _log "run: $*"
    # Visible like run(), because the things worth capturing are also the slow
    # ones: a silent five-minute dnf update or a 1.3 GB Flatpak download looks
    # like a hung installer. tee -a applies to every file, so <out> is
    # truncated first rather than growing across calls.
    : >"$out"
    "$@" 2>&1 | tee -a "$LOG_FILE" "$out"
    local rc="${PIPESTATUS[0]}"
    return "$rc"
}

# The last meaningful line(s) of a captured output, trimmed to one line so it
# fits in a warning and in the summary list.
reason_from() {
    local f="$1" n="${2:-2}"
    [[ -s "$f" ]] || return 0
    grep -vE '^[[:space:]]*$' "$f" | tail -n "$n" | tr '\n' ' ' | cut -c1-240
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

# Free megabytes on the filesystem holding <path>.
#
# Walks up to the first component that exists, because the interesting paths do
# not exist yet when the question is asked: /var/lib/flatpak is created by
# flatpak, and asking df about a missing path returns nothing at all. Checking
# "/" alone is not enough either — Fedora Server's default LVM layout puts
# /home on its own volume and caps /, which is exactly the machine where this
# check matters.
free_mb() {
    local p="${1:-/}"
    while [[ ! -e "$p" && "$p" != "/" ]]; do p="$(dirname "$p")"; done
    df -Pm "$p" 2>/dev/null | awk 'NR==2 {print $4}'
}

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

# ---------------------------------------------------------------------------
# Questions
#
# Everything here reads from the TERMINAL, not from stdin, and writes its
# prompts there too. Two reasons, both real:
#
#   1. bootstrap.sh is still advertised as `curl … | bash`, and the test-lab
#      script really invokes it that way. There stdin is the SCRIPT — a plain
#      `read` swallows the rest of it or sees EOF immediately.
#   2. ask_value/ask_choice return their answer on stdout so callers can use
#      $( ). A prompt printed to stdout would end up inside the answer.
#
# With no terminal at all the default is taken and the run continues. A
# question nobody can see must never block an install.
# ---------------------------------------------------------------------------
_have_tty() { [[ -r /dev/tty && -w /dev/tty ]]; }

_say_tty() { if _have_tty; then printf '%b' "$1" >/dev/tty; else printf '%b' "$1" >&2; fi; }

# _ask_raw <prompt> <varname> -> 1 when there is nothing to read from
#
# Every local in here is __ask_-prefixed on purpose. Returning a value through
# a caller-supplied variable NAME collides the moment the caller picks the same
# name for its own local — and every caller here naturally called it "reply".
# printf -v then wrote into THIS function's local, which vanished on return, so
# every question silently answered itself with its default and confirm() always
# said no. The prompt appeared, the typed text echoed, and the answer was
# thrown away.
_ask_raw() {
    local __ask_prompt="$1" __ask_var="$2" __ask_reply=""
    [[ "$__ask_var" == __ask_* ]] && return 1   # never let the collision back in
    _say_tty "$__ask_prompt"
    if _have_tty; then
        IFS= read -r __ask_reply </dev/tty || return 1
    elif [[ -t 0 ]]; then
        IFS= read -r __ask_reply || return 1
    else
        _say_tty '\n'
        return 1
    fi
    printf -v "$__ask_var" '%s' "$__ask_reply"
}

confirm() {
    (( UNATTENDED )) && return 0
    (( DRY_RUN )) && return 0
    local reply=""
    _ask_raw "  $1 [y/N] " reply || return 1
    [[ "$reply" =~ ^[Yy]$ ]]
}

# ask_value <question> <default> [validator]
#
# Free text with a default. The validator is a function name; it is asked again
# until the answer passes, so nothing unchecked can reach a config file.
ask_value() {
    local question="$1" default="$2" validator="${3:-}" reply=""
    if (( UNATTENDED )) || (( DRY_RUN )); then printf '%s' "$default"; return 0; fi
    while true; do
        if ! _ask_raw "  $question [$default]: " reply; then
            printf '%s' "$default"; return 0
        fi
        [[ -z "$reply" ]] && reply="$default"
        if [[ -z "$validator" ]] || "$validator" "$reply"; then
            printf '%s' "$reply"; return 0
        fi
        _say_tty "  $C_YELLOW$(msg ask_invalid "$reply")$C_RESET\n"
    done
}

# ask_choice <question> <default> <option...>
#
# A numbered list. Enter takes the default; the default is also offered as a
# plain typed value so an answer that is not in the short list still works.
ask_choice() {
    local question="$1" default="$2"; shift 2
    if (( UNATTENDED )) || (( DRY_RUN )); then printf '%s' "$default"; return 0; fi

    # Every caller passes the CURRENT value first and then a short list of
    # sensible ones — and the current value is very often already in that list.
    # A German machine was therefore offered
    #     1) de (default)   2) us   3) de (default)   4) gb …
    # with the same entry twice, both labelled as the default. Seen in a
    # transcript of a first install, not reasoned about. Callers stay simple;
    # the duplicate is dropped here, keeping the first occurrence so the
    # current value stays at the top where it belongs.
    local -a options=()
    local candidate seen i reply=""
    for candidate in "$@"; do
        seen=0
        for i in "${options[@]}"; do
            [[ "$candidate" == "$i" ]] && { seen=1; break; }
        done
        (( seen )) || options+=("$candidate")
    done

    _say_tty "\n  $C_BOLD$question$C_RESET\n"
    for i in "${!options[@]}"; do
        if [[ "${options[$i]}" == "$default" ]]; then
            _say_tty "    $C_GREEN$((i + 1)))$C_RESET ${options[$i]} $C_DIM($(msg ask_default))$C_RESET\n"
        else
            _say_tty "    $((i + 1))) ${options[$i]}\n"
        fi
    done
    while true; do
        if ! _ask_raw "  $(msg ask_pick) [$default]: " reply; then
            printf '%s' "$default"; return 0
        fi
        [[ -z "$reply" ]] && { printf '%s' "$default"; return 0; }
        if [[ "$reply" =~ ^[0-9]+$ ]] && (( reply >= 1 && reply <= ${#options[@]} )); then
            printf '%s' "${options[$((reply - 1))]}"; return 0
        fi
        for i in "${options[@]}"; do
            [[ "$reply" == "$i" ]] && { printf '%s' "$reply"; return 0; }
        done
        _say_tty "  $C_YELLOW$(msg ask_invalid "$reply")$C_RESET\n"
    done
}
