#!/usr/bin/env bash
# Phase 15 — system settings that are worth changing on a fresh Fedora.
#
# Every entry here has a reason that can be stated in one sentence. Anything
# that only appears in forum posts as folklore is deliberately absent — see the
# "not done" list at the bottom of this file, which is as much a part of the
# design as the things that are done.
#
# Skipped entirely with --no-tweaks, so it stays obvious what this installer
# changes about the system itself rather than about your desktop.

phase_tweaks() {
    (( NO_TWEAKS )) && { section "$(msg sec_tweaks)"; info "$(msg info_tweaks_skipped)"; return 0; }

    section "$(msg sec_tweaks)"

    dnf_install avahi nss-mdns tuned tuned-ppd fwupd btrfs-progs compsize

    # thermald is Intel-only. Installing it on AMD does nothing useful and adds
    # a service that logs about hardware it cannot find.
    if grep -qi 'GenuineIntel' /proc/cpuinfo 2>/dev/null; then
        dnf_install thermald
        run_quiet sudo systemctl enable --now thermald || true
    fi

    # --- journal size --------------------------------------------------------
    # Without a limit the journal grows to 10% of the partition. That is how a
    # machine ends up with several GB of logs nobody has ever read — measured
    # on this project's own Proxmox host: 3.9 GB.
    step "$(msg step_journal_limit)"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s write /etc/systemd/journald.conf.d/00-buchhwin.conf\n' "$C_DIM" "$C_RESET"
    else
        sudo mkdir -p /etc/systemd/journald.conf.d
        sudo tee /etc/systemd/journald.conf.d/00-buchhwin.conf >/dev/null <<'EOF'
# Keep the journal useful without letting it eat the disk.
[Journal]
SystemMaxUse=500M
SystemMaxFileSize=50M
MaxRetentionSec=1month
EOF
        run_quiet sudo systemctl restart systemd-journald || true
    fi

    # --- mDNS ----------------------------------------------------------------
    # Without this, "nas.local" does not resolve and network drives only work by
    # IP address — which is exactly the kind of half-working that wastes an
    # afternoon.
    step "$(msg step_mdns)"
    run_quiet sudo systemctl enable --now avahi-daemon.service || warn "$(msg warn_avahi)"
    if ! (( DRY_RUN )) && [[ -f /etc/nsswitch.conf ]]; then
        if ! grep -q 'mdns4_minimal' /etc/nsswitch.conf; then
            sudo cp -n /etc/nsswitch.conf /etc/nsswitch.conf.bak-buchhwin
            sudo sed -i -E 's/^(hosts:\s+)(.*)$/\1mdns4_minimal [NOTFOUND=return] \2/' \
                /etc/nsswitch.conf
        fi
    fi

    # --- out-of-memory handling ---------------------------------------------
    # systemd-oomd is part of systemd, not a package. It ends one memory hog on
    # purpose instead of letting the whole machine freeze — the difference
    # between "Firefox is gone" and "I have to hold the power button".
    step "$(msg step_oomd)"
    run_quiet sudo systemctl enable --now systemd-oomd.service || warn "$(msg warn_oomd)"

    # --- power profiles ------------------------------------------------------
    # tuned-ppd is Fedora's current answer; power-profiles-daemon is the old one
    # and the two fight over the same D-Bus name, so only one may be installed.
    step "$(msg step_power_profiles)"
    if rpm -q power-profiles-daemon >/dev/null 2>&1; then
        info "$(msg info_ppd_present)"
    else
        run_quiet sudo systemctl enable --now tuned.service || true
        run_quiet sudo systemctl enable --now tuned-ppd.service || true
    fi

    # --- SSD trim ------------------------------------------------------------
    # Fedora enables this by default; it is only VERIFIED here, not forced.
    # Its absence on the Proxmox host cost 26 GB of pool space, so it is worth
    # a line of output either way.
    if systemctl is-enabled fstrim.timer >/dev/null 2>&1; then
        ok "$(msg ok_fstrim)"
    else
        step "$(msg step_fstrim)"
        run_quiet sudo systemctl enable --now fstrim.timer || warn "$(msg warn_fstrim)"
    fi

    # --- btrfs ---------------------------------------------------------------
    # Only reported, never changed: converting a live filesystem is not
    # something an installer should do behind your back. The kickstart in
    # kickstart/buchhwin.ks creates btrfs with zstd:1 from the start.
    if ! (( DRY_RUN )); then
        local fstype; fstype="$(findmnt -no FSTYPE / 2>/dev/null || echo unknown)"
        if [[ "$fstype" == "btrfs" ]]; then
            local opts; opts="$(findmnt -no OPTIONS / 2>/dev/null || true)"
            if [[ "$opts" == *compress* ]]; then
                ok "$(msg ok_btrfs_compressed)"
            else
                warn "$(msg warn_btrfs_uncompressed)"
            fi
        else
            info "$(msg info_not_btrfs "$fstype")"
        fi
    fi

    ok "$(msg ok_tweaks)"
}

# ---------------------------------------------------------------------------
# Deliberately NOT done, and why. These are the tweaks every forum recommends
# and that are wrong or pointless on a current Fedora:
#
#   vm.swappiness=10       Fedora swaps to zram — compressed RAM. Lowering
#                          swappiness prevents exactly the swapping that is
#                          fast and wanted. Actively harmful here.
#   disable systemd-oomd   Popular after it kills something. Without it the
#                          whole machine freezes instead.
#   noatime                relatime has been the default for years and does
#                          the same job.
#   disable SELinux        No. It costs nothing measurable, and this project
#                          has a concrete example of it working as intended.
#   preload / prelink      Dead projects.
#   cpu governor forcing   tuned already does this, per profile.
#   earlyoom               Duplicates systemd-oomd with worse integration.
# ---------------------------------------------------------------------------
