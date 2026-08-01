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
    # The version this desktop is written and verified against. packages/
    # copr-desktop.txt pins the packages to match; this is the check that the
    # pin actually held, because a mismatch is silent otherwise — Hyprland
    # starts either way and simply ignores config it does not understand.
    local hypr_expected="0.55"

    if ! (( DRY_RUN )) && command -v hyprctl >/dev/null 2>&1; then
        local hv; hv="$(Hyprland --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
        if [[ -n "$hv" ]]; then
            # Numeric, not string: "0.9" sorts AFTER "0.55" as text, which
            # would report an ancient build as too new.
            local maj min emaj emin
            maj="${hv%%.*}"; min="$(cut -d. -f2 <<<"$hv")"
            emaj="${hypr_expected%%.*}"; emin="${hypr_expected##*.}"
            if (( maj == emaj && min == emin )); then
                ok "$(msg ok_hyprland "$hv")"
            elif (( maj < emaj || (maj == emaj && min < emin) )); then
                # Before 0.55 the config language was hyprlang, not Lua.
                # Everything in dotfiles/hypr would load as nothing at all.
                fail "$(msg fail_hyprland_old "$hv" "$hypr_expected")"
            else
                # Newer is not better here. 0.56 needs hyprutils 0.14, and
                # hyprlock has no build against it — measured on 2026-08-02:
                # the whole transaction stops resolving. If this fires, the
                # pin in copr-desktop.txt was bypassed or the repository moved.
                fail "$(msg fail_hyprland_new "$hv" "$hypr_expected")"
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
