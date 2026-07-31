#!/usr/bin/env bash
# Phase 40 — applications: sysadmin toolkit, everyday apps, Flatpaks, web apps.

phase_apps() {
    if (( MINIMAL )); then
        section "$(msg sec_apps)"
        info "$(msg info_minimal_skip_apps)"
        return 0
    fi

    section "$(msg sec_sysadmin)"
    mapfile -t sysadmin < <(read_list "$REPO_DIR/packages/dnf-sysadmin.txt")
    dnf_install "${sysadmin[@]}"
    mapfile -t sysadmin_copr < <(read_list "$REPO_DIR/packages/copr-sysadmin.txt")
    dnf_install "${sysadmin_copr[@]}"

    # Wireshark without this is root-only, which nobody wants in daily use.
    if getent group wireshark >/dev/null 2>&1; then
        if ! id -nG "$USER" | tr ' ' '\n' | grep -qx wireshark; then
            step "$(msg step_wireshark_group)"
            run sudo usermod -aG wireshark "$USER"
            info "$(msg info_relogin_needed)"
        fi
    fi

    # Rootless containers need a subuid/subgid range; Fedora Server does not
    # always create one for a cloud-init user.
    if ! grep -q "^$USER:" /etc/subuid 2>/dev/null; then
        step "$(msg step_subuid)"
        run sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$USER"
        run_quiet podman system migrate || true
    fi

    section "$(msg sec_apps)"
    mapfile -t apps < <(read_list "$REPO_DIR/packages/dnf-apps.txt")
    dnf_install "${apps[@]}"

    # --- Flatpaks ------------------------------------------------------------
    if (( NO_FLATPAK )); then
        info "$(msg info_flatpak_disabled)"
    else
        local id
        while read -r id; do
            [[ -z "$id" ]] && continue
            if ! (( DRY_RUN )) && flatpak info "$id" >/dev/null 2>&1; then
                SKIPPED+=("$id"); continue
            fi
            step "$(msg step_flatpak "$id")"
            # System-wide, matching the system-wide remote from phase 10.
            if run sudo flatpak install -y --noninteractive flathub "$id"; then
                INSTALLED+=("$id")
            else
                fail "$(msg fail_flatpak "$id")"
            fi
        done < <(read_list "$REPO_DIR/packages/flatpak.txt")
    fi

    # --- web apps ------------------------------------------------------------
    # Teams has had no native Linux client since 2022; the web app is the
    # supported path. scripts/webapp.sh turns a URL into a real .desktop entry
    # with its own window, icon and window rule.
    section "$(msg sec_webapps)"
    # The binary is /usr/bin/brave-origin — brave-origin is a distinct package
    # from brave-browser and installs a differently named executable.
    if command -v brave-origin >/dev/null 2>&1 || (( DRY_RUN )); then
        run "$REPO_DIR/scripts/webapp.sh" install-defaults
    else
        warn "$(msg warn_no_browser)"
    fi
}
