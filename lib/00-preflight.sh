#!/usr/bin/env bash
# Phase 00 — refuse to start on a system where the run cannot succeed.
# The old script had no checks at all and would happily half-install on the
# wrong distribution.

phase_preflight() {
    section "$(msg sec_preflight)"

    # --- distribution --------------------------------------------------------
    local id="" ver=""
    if [[ -r /etc/os-release ]]; then
        # shellcheck source=/dev/null
        id="$(. /etc/os-release && echo "${ID:-}")"
        ver="$(. /etc/os-release && echo "${VERSION_ID:-}")"
    fi
    [[ "$id" == "fedora" ]] || die "$(msg err_not_fedora "${id:-unknown}")"
    ok "$(msg ok_fedora "$ver")"

    if [[ "$ver" != "$TARGET_FEDORA" ]]; then
        warn "$(msg warn_fedora_version "$ver" "$TARGET_FEDORA")"
        confirm "$(msg ask_continue_anyway)" || die "$(msg err_aborted)"
    fi

    # --- architecture --------------------------------------------------------
    local arch; arch="$(uname -m)"
    [[ "$arch" == "x86_64" || "$arch" == "aarch64" ]] \
        || die "$(msg err_arch "$arch")"

    # --- not root ------------------------------------------------------------
    [[ $EUID -ne 0 ]] || die "$(msg err_running_as_root)"

    # --- network -------------------------------------------------------------
    if ! curl -fsS --max-time 10 -o /dev/null https://mirrors.fedoraproject.org/ ; then
        die "$(msg err_no_network)"
    fi
    ok "$(msg ok_network)"

    # --- free space ----------------------------------------------------------
    local free_mb; free_mb="$(df -Pm / | awk 'NR==2 {print $4}')"
    if (( free_mb < 12000 )); then
        warn "$(msg warn_low_space "$free_mb")"
        confirm "$(msg ask_continue_anyway)" || die "$(msg err_aborted)"
    else
        ok "$(msg ok_space "$(( free_mb / 1024 ))")"
    fi

    # --- GPU -----------------------------------------------------------------
    if [[ "$GPU" == "auto" ]]; then
        GPU="$(detect_gpu)"
        info "$(msg info_gpu_detected "$GPU")"
    fi

    # --- virtual machine -----------------------------------------------------
    if is_vm; then
        IS_VM=1
        info "$(msg info_vm_detected "$(systemd-detect-virt)")"
    else
        IS_VM=0
    fi

    mkdir -p "$STATE_DIR"
    ok "$(msg ok_log "$LOG_FILE")"
}
