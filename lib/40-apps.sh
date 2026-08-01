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

    # Optional groups: nothing from these is installed unless asked for with
    # --with, which is the whole point. A desktop that ships kubectl, Terraform
    # and two database clients to somebody who runs none of them is exactly the
    # kind of weight this setup is trying not to carry.
    local group
    for group in ${WITH_GROUPS_STR:-}; do
        local list="$REPO_DIR/packages/optional-$group.txt"
        if [[ ! -f "$list" ]]; then
            warn "$(msg warn_unknown_group "$group")"
            continue
        fi
        step "$(msg step_optional_group "$group")"
        mapfile -t extra < <(read_list "$list")
        dnf_install "${extra[@]}"
    done

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
    # Flathub is added HERE and not in the repository phase, because `flatpak`
    # itself is installed in the base phase, which runs after it. The first
    # test run added the remote before the tool existed: the remote-add failed
    # silently and all five Flatpaks then failed too — five red lines from one
    # ordering mistake.
    if (( NO_FLATPAK )); then
        info "$(msg info_flatpak_disabled)"
    else
        step "$(msg step_flathub)"
        run sudo flatpak remote-add --if-not-exists \
            flathub https://dl.flathub.org/repo/flathub.flatpakrepo \
            || fail "$(msg fail_flathub)"

        # One cause should produce one message. Without this, a full disk shows
        # up as one red line per application and hides the single thing that is
        # actually wrong. Measured: the four Flatpaks below need 4.7 GB with
        # their runtimes, so 5 GB free is the point where it is worth starting.
        local fp_free; fp_free="$(free_mb /var/lib/flatpak)"
        if [[ -n "$fp_free" ]] && (( fp_free < 5000 )) && ! (( DRY_RUN )); then
            warn "$(msg warn_flatpak_no_space "$fp_free")"
        else
            local id fp_out; fp_out="$(mktemp)"
            while read -r id; do
                [[ -z "$id" ]] && continue
                if ! (( DRY_RUN )) && flatpak info "$id" >/dev/null 2>&1; then
                    SKIPPED+=("$id"); continue
                fi
                step "$(msg step_flatpak "$id")"
                # System-wide, matching the system-wide remote from phase 10.
                #
                # </dev/null matters: this loop's stdin is the package list
                # arriving through process substitution, and any child that
                # reads stdin eats the entries not yet processed.
                if run_capture "$fp_out" sudo flatpak install -y \
                        --noninteractive flathub "$id" </dev/null; then
                    INSTALLED+=("$id")
                else
                    fail "$(msg fail_flatpak "$id" "$(reason_from "$fp_out")")"
                fi
            done < <(read_list "$REPO_DIR/packages/flatpak.txt")
            rm -f "$fp_out"
        fi
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
