#!/usr/bin/env bash
# Phase 10 — third-party repositories and codecs.
#
# Every step here is idempotent: enabling a repo that is already enabled, or
# swapping ffmpeg that is already swapped, must not fail the run.

_repo_enabled() {
    (( DRY_RUN )) && return 1
    dnf repolist --enabled 2>/dev/null | awk '{print $1}' | grep -qx "$1"
}

phase_repos() {
    section "$(msg sec_repos)"

    # --- RPM Fusion ----------------------------------------------------------
    # Needed for full ffmpeg, hardware video acceleration and the NVIDIA akmod.
    local fedver; fedver="$(fedora_version)"
    if rpm -q rpmfusion-free-release >/dev/null 2>&1 \
    && rpm -q rpmfusion-nonfree-release >/dev/null 2>&1; then
        info "$(msg info_rpmfusion_present)"
    else
        step "$(msg step_rpmfusion)"
        run sudo dnf install -y \
            "https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-${fedver}.noarch.rpm" \
            "https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-${fedver}.noarch.rpm" \
            || fail "$(msg fail_rpmfusion)"
    fi

    # --- COPRs ---------------------------------------------------------------
    # Hyprland is orphaned in Fedora (last build 0.45.2 on F42, absent from
    # F43/F44), so a COPR is not a convenience here — it is the only source.
    # Which one, and why, is written down in packages/copr.txt.
    local entry
    while read -r entry; do
        [[ -z "$entry" ]] && continue
        # owner/project[:priority]
        local copr="${entry%%:*}" prio=""
        [[ "$entry" == *:* ]] && prio="${entry##*:}"
        local repoid="copr:copr.fedorainfracloud.org:${copr%%/*}:${copr##*/}"

        if _repo_enabled "$repoid"; then
            info "$(msg info_copr_present "$copr")"
        else
            step "$(msg step_copr "$copr")"
            run sudo dnf copr enable -y "$copr" || { fail "$(msg fail_copr "$copr")"; continue; }
        fi

        # Priority decides which repository wins when two offer the same
        # package. Without it, two Hyprland COPRs silently fight over hyprutils
        # and the resolution depends on version numbers alone — which is how
        # you end up with a compositor from one repo and its libraries from
        # another. Lower number wins.
        if [[ -n "$prio" ]]; then
            run sudo dnf config-manager setopt "$repoid.priority=$prio" \
                || warn "$(msg warn_copr_priority "$copr")"
        fi
    done < <(read_list "$REPO_DIR/packages/copr.txt")

    (( MINIMAL )) && { info "$(msg info_minimal_skip_repos)"; return 0; }

    # --- Brave ---------------------------------------------------------------
    if [[ -f /etc/yum.repos.d/brave-browser.repo ]]; then
        info "$(msg info_repo_present Brave)"
    else
        step "$(msg step_repo Brave)"
        run sudo rpm --import https://brave-browser-rpm-release.s3.brave.com/brave-core.asc
        run sudo dnf config-manager addrepo \
            --from-repofile=https://brave-browser-rpm-release.s3.brave.com/brave-browser.repo \
            || fail "$(msg fail_repo Brave)"
    fi

    # --- Visual Studio Code --------------------------------------------------
    if [[ -f /etc/yum.repos.d/vscode.repo ]]; then
        info "$(msg info_repo_present "VS Code")"
    else
        step "$(msg step_repo "VS Code")"
        run sudo rpm --import https://packages.microsoft.com/keys/microsoft.asc
        if (( DRY_RUN )); then
            printf '     %s[dry-run]%s write /etc/yum.repos.d/vscode.repo\n' "$C_DIM" "$C_RESET"
        else
            sudo tee /etc/yum.repos.d/vscode.repo >/dev/null <<'EOF'
[code]
name=Visual Studio Code
baseurl=https://packages.microsoft.com/yumrepos/vscode
enabled=1
autorefresh=1
gpgcheck=1
gpgkey=https://packages.microsoft.com/keys/microsoft.asc
EOF
        fi
    fi

    # --- codecs --------------------------------------------------------------
    step "$(msg step_codecs)"
    run sudo dnf config-manager setopt fedora-cisco-openh264.enabled=1 || true
    if rpm -q ffmpeg >/dev/null 2>&1; then
        info "$(msg info_ffmpeg_present)"
    else
        run sudo dnf swap ffmpeg-free ffmpeg --allowerasing -y || fail "$(msg fail_ffmpeg)"
    fi
    # `dnf update @multimedia` was wrong and warned on every single run: dnf5
    # only updates a group that is already INSTALLED, and this one never is on
    # a Fedora Server base, so it failed with "No match for argument:
    # multimedia" — the group exists, it just had nothing to update. The step
    # therefore never installed a codec in its life while claiming to.
    #
    # `group install` is what was meant. It pulls the RPM Fusion pieces the
    # earlier steps enabled the repositories for — a52, mpeg2, aptX, HEVC —
    # about 20 MB.
    run_quiet sudo dnf group install multimedia \
        --setopt="install_weak_deps=False" \
        --exclude=PackageKit-gstreamer-plugin -y || warn "$(msg warn_multimedia)"

    # --- GPU drivers ---------------------------------------------------------
    case "$GPU" in
        amd)
            step "$(msg step_gpu AMD)"
            dnf_install mesa-vulkan-drivers mesa-va-drivers libva-utils
            ;;
        intel)
            step "$(msg step_gpu Intel)"
            dnf_install mesa-vulkan-drivers intel-media-driver libva-utils
            ;;
        nvidia)
            step "$(msg step_gpu NVIDIA)"
            dnf_install akmod-nvidia xorg-x11-drv-nvidia-cuda \
                        xorg-x11-drv-nvidia-power nvidia-vaapi-driver
            # The old script stopped here. Without building the module the
            # machine boots to a black screen, and with Secure Boot enabled it
            # does so even after the build unless the key is enrolled.
            step "$(msg step_nvidia_build)"
            run sudo akmods --force || warn "$(msg warn_akmods)"
            run sudo dracut --force || warn "$(msg warn_dracut)"
            if [[ -d /sys/firmware/efi ]] && command -v mokutil >/dev/null 2>&1 \
               && mokutil --sb-state 2>/dev/null | grep -qi enabled; then
                warn "$(msg warn_secureboot)"
            fi
            ;;
        none|*)
            info "$(msg info_gpu_none)"
            ;;
    esac
}
