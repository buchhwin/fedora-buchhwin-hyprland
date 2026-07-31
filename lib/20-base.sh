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
        #
        # Plain `chsh` makes the account authenticate to itself, which fails
        # outright when the account has no password (cloud images, and every
        # test VM). Go through sudo, which the installer already relies on
        # everywhere else, and keep bare chsh as the fallback for the case
        # where sudo is the thing that is not available.
        if sudo -n chsh -s /usr/bin/zsh "$USER" 2>/dev/null \
           || sudo chsh -s /usr/bin/zsh "$USER" 2>/dev/null \
           || chsh -s /usr/bin/zsh; then
            ok "$(msg ok_shell)"
        else
            warn "$(msg warn_chsh)"
        fi
    fi

    # --- XDG user directories -----------------------------------------------
    run_quiet xdg-user-dirs-update || true
}
