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
    #
    # This used to warn and carry on. It is a hard stop now, because carrying on
    # is what produced the failure this check exists to prevent: a run with
    # 8643 MB free installed 109 packages and then died on the last two
    # Flatpaks, leaving a half-built desktop and a summary full of red.
    #
    # The numbers are measured, not estimated. A finished install of this
    # desktop occupies 11.0 GB on / (btrfs, zstd:1), of which /var/lib/flatpak
    # is 5.0 GB. Add the RPMs and Flatpak downloads that are staged during the
    # run and released afterwards, and 12 GB free is the honest requirement.
    # Dropping the Flatpaks really does drop the need — hence the three tiers
    # rather than one number that is wrong for two of the three cases.
    local need_mb=12000 how="" flatpak_dir="/var/lib/flatpak"
    if (( MINIMAL )); then
        need_mb=6000;  how="--minimal"
    elif (( NO_FLATPAK )); then
        need_mb=8000;  how="--no-flatpak"
    fi

    local root_mb; root_mb="$(free_mb /)"
    if (( root_mb < need_mb )); then
        die "$(msg err_low_space "$root_mb" "$(( need_mb / 1000 ))" "${how:---no-flatpak}")"
    fi

    # /var/lib/flatpak is usually on / — but not on Fedora Server's default LVM
    # layout, and that is exactly the machine that runs out. Only worth saying
    # anything when it really is a separate filesystem.
    if ! (( MINIMAL )) && ! (( NO_FLATPAK )); then
        local fp_mb; fp_mb="$(free_mb "$flatpak_dir")"
        if [[ -n "$fp_mb" ]] && (( fp_mb < 6000 )) && (( fp_mb != root_mb )); then
            die "$(msg err_low_space_flatpak "$fp_mb")"
        fi
    fi
    ok "$(msg ok_space "$(( root_mb / 1024 ))")"

    # --- GPU -----------------------------------------------------------------
    if [[ "$GPU" == "auto" ]]; then
        GPU="$(detect_gpu)"
        info "$(msg info_gpu_detected "$GPU")"
    fi

    # --- virtual machine -----------------------------------------------------
    # shellcheck disable=SC2034  # read by lib/80-vm-tweaks.sh
    if is_vm; then
        IS_VM=1
        info "$(msg info_vm_detected "$(systemd-detect-virt)")"
    else
        IS_VM=0
    fi

    mkdir -p "$STATE_DIR"
    ok "$(msg ok_log "$LOG_FILE")"
}
