#!/usr/bin/env bash
# Phase 30 — the desktop itself: compositor, bar, menus, login manager.

phase_hyprland() {
    section "$(msg sec_desktop)"

    mapfile -t desktop < <(read_list "$REPO_DIR/packages/dnf-desktop.txt")
    dnf_install "${desktop[@]}"

    mapfile -t coprpkgs < <(read_list "$REPO_DIR/packages/copr-desktop.txt")
    dnf_install "${coprpkgs[@]}"

    # --- verify the compositor is actually the Lua-config generation ---------
    # Hyprland 0.55 replaced hyprlang with Lua. Everything in dotfiles/hypr is
    # written for that; silently running an older build would load nothing.
    if ! (( DRY_RUN )) && command -v hyprctl >/dev/null 2>&1; then
        local hv; hv="$(Hyprland --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
        if [[ -n "$hv" ]]; then
            local maj min; maj="${hv%%.*}"; min="$(cut -d. -f2 <<<"$hv")"
            if (( maj == 0 && min < 55 )); then
                fail "$(msg fail_hyprland_old "$hv")"
            else
                ok "$(msg ok_hyprland "$hv")"
                # 0.56 exists in the COPR but cannot be installed alongside a
                # working desktop: it needs aquamarine 0.14, while hyprlock and
                # hyprpicker in the same repository are still built against
                # 0.12. Taking 0.56 therefore REMOVES the lock screen and the
                # colour picker — measured, not assumed.
                #
                # 0.55 is what matters: it is the release that made the config
                # Lua, which is what everything here is written for. When the
                # repository rebuilds hyprlock against the newer aquamarine,
                # a plain `bhctl update` will move up on its own. Nothing is
                # pinned; it simply is not forced.
                (( maj == 0 && min == 55 )) && info "$(msg info_hyprland_055)"
            fi
        fi
    fi

    # --- login manager -------------------------------------------------------
    step "$(msg step_sddm)"
    run sudo systemctl set-default graphical.target
    run sudo systemctl enable sddm.service

    # The greeter runs on Wayland through the sddm-wayland-generic subpackage,
    # which ships its own Weston-based configuration. Deliberately not
    # overridden here: writing our own CompositorCommand would either fight
    # that config or drag in the whole KDE stack for kwin_wayland.
    # The Catppuccin greeter theme is selected in phase 50, once it exists.

    # --- session entry -------------------------------------------------------
    # Started through uwsm so the session lives in a proper systemd scope:
    # user services get a real session bus, and logout tears everything down.
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s install hyprland-uwsm.desktop\n' "$C_DIM" "$C_RESET"
    else
        sudo mkdir -p /usr/share/wayland-sessions
        sudo tee /usr/share/wayland-sessions/hyprland-buchhwin.desktop >/dev/null <<'EOF'
[Desktop Entry]
Name=Hyprland (Buchhwin)
Comment=Catppuccin Hyprland desktop
Exec=uwsm start -S -F /usr/bin/Hyprland
Type=Application
DesktopNames=Hyprland
EOF
    fi
    ok "$(msg ok_session)"
}
