#!/usr/bin/env bash
# Phase 20 — base packages and the shell.

phase_base() {
    section "$(msg sec_base)"

    # --- dnf: Enter means yes ------------------------------------------------
    # `Is this ok [y/N]:` with N as the default means every install needs an
    # explicit y. Flipped to [Y/n], because on this machine the answer is
    # essentially always yes and hitting Enter should not abort the install you
    # just asked for.
    step "$(msg step_dnf_defaults)"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s set defaultyes=True in /etc/dnf/dnf.conf\n' "$C_DIM" "$C_RESET"
    else
        sudo mkdir -p /etc/dnf
        sudo touch /etc/dnf/dnf.conf
        if grep -qE '^\s*defaultyes\s*=' /etc/dnf/dnf.conf; then
            sudo sed -i -E 's/^\s*defaultyes\s*=.*/defaultyes=True/' /etc/dnf/dnf.conf
        else
            # The key belongs under [main]; append it there rather than at the
            # end of the file, where dnf would ignore it.
            if grep -q '^\[main\]' /etc/dnf/dnf.conf; then
                sudo sed -i '/^\[main\]/a defaultyes=True' /etc/dnf/dnf.conf
            else
                printf '[main]\ndefaultyes=True\n' | sudo tee -a /etc/dnf/dnf.conf >/dev/null
            fi
        fi
        # Also make the count of retained kernels sane and keep dnf quiet about
        # its own weak dependencies — both are everyday annoyances otherwise.
        grep -qE '^\s*max_parallel_downloads' /etc/dnf/dnf.conf \
            || sudo sed -i '/^\[main\]/a max_parallel_downloads=10' /etc/dnf/dnf.conf
        ok "$(msg ok_dnf_defaults)"
    fi

    step "$(msg step_update)"
    run_quiet sudo dnf update -y || warn "$(msg warn_update)"

    mapfile -t core < <(read_list "$REPO_DIR/packages/dnf-core.txt")
    dnf_install "${core[@]}"
    mapfile -t core_copr < <(read_list "$REPO_DIR/packages/copr-core.txt")
    dnf_install "${core_copr[@]}"

    # --- zsh -----------------------------------------------------------------
    # Fedora packages both zsh plugins, so nothing is cloned from GitHub any
    # more; they are updated by dnf like everything else.
    step "$(msg step_shell)"
    if [[ "$SHELL" == *zsh ]]; then
        info "$(msg info_shell_already)"
    elif (( DRY_RUN )); then
        printf '     %s[dry-run]%s chsh -s /usr/bin/zsh\n' "$C_DIM" "$C_RESET"
    else
        # Done here, early, and not as the very last action of the whole run —
        # the password prompt should arrive while the user is still watching.
        if chsh -s /usr/bin/zsh; then
            ok "$(msg ok_shell)"
        else
            warn "$(msg warn_chsh)"
        fi
    fi

    # --- keyring unlocks with the login --------------------------------------
    # Without pam_gnome_keyring you get a second password prompt for the keyring
    # after every login, and every cloud drive stays disconnected until you
    # answer it. Added idempotently, with a backup, because getting PAM wrong
    # locks you out of your own machine.
    step "$(msg step_pam_keyring)"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s add pam_gnome_keyring to /etc/pam.d/sddm\n' "$C_DIM" "$C_RESET"
    elif [[ -f /etc/pam.d/sddm ]]; then
        if grep -q 'pam_gnome_keyring' /etc/pam.d/sddm; then
            info "$(msg info_pam_present)"
        else
            sudo cp -n /etc/pam.d/sddm "/etc/pam.d/sddm.bak-buchhwin"
            printf '%s\n%s\n' \
                '-auth       optional     pam_gnome_keyring.so' \
                '-session    optional     pam_gnome_keyring.so auto_start' \
                | sudo tee -a /etc/pam.d/sddm >/dev/null
            ok "$(msg ok_pam_keyring)"
        fi
    else
        warn "$(msg warn_pam_missing)"
    fi

    # --- XDG user directories -----------------------------------------------
    run_quiet xdg-user-dirs-update || true
}
