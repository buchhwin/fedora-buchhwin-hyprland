#!/usr/bin/env bash
# Phase 20 — base packages and the shell.

phase_base() {
    section "$(msg sec_base)"

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

    # --- XDG user directories -----------------------------------------------
    run_quiet xdg-user-dirs-update || true
}
