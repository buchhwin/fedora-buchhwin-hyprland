#!/usr/bin/env bash
# Phase 60 — put the configuration in place.
#
# Files are symlinked out of the cloned repo, so `bhctl update` (a git pull)
# updates all of them at once and there is never a half-copied state.
#
# Linking happens per FILE, not per directory, on purpose: generated colour
# files (written by theme/apply-theme.py) live in the same directories as the
# hand-written ones. If ~/.config/waybar were a symlink into the repo, every
# theme switch would write generated files into a public git repository.
#
#   symlinked  -> hand-written, tracked in git
#   generated  -> written by apply-theme.py, ignored by git, machine-local
#   seeded     -> copied once, then owned by the user / the settings GUI

_append_once() {
    # Append a line to a file we do not own, exactly once. The marker line goes
    # first so the file says who added it and why.
    local file="$1" line="$2" marker="$3"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s ensure %s in %s\n' "$C_DIM" "$C_RESET" "$line" "$file"
        return 0
    fi
    mkdir -p "$(dirname "$file")"
    [[ -f "$file" ]] || : >"$file"
    grep -qxF "$line" "$file" && return 0
    printf '\n%s\n%s\n' "$marker" "$line" >>"$file"
}

phase_dotfiles() {
    section "$(msg sec_dotfiles)"

    # --- Hyprland ------------------------------------------------------------
    link_config dotfiles/hypr/hyprland.lua   "$CONFIG_HOME/hypr/hyprland.lua"
    link_config dotfiles/hypr/binds.lua      "$CONFIG_HOME/hypr/binds.lua"
    link_config dotfiles/hypr/rules.lua      "$CONFIG_HOME/hypr/rules.lua"
    link_config dotfiles/hypr/hypridle.conf  "$CONFIG_HOME/hypr/hypridle.conf"

    # --- bar, menus, notifications ------------------------------------------
    link_config dotfiles/waybar/config.jsonc "$CONFIG_HOME/waybar/config.jsonc"
    link_config dotfiles/waybar/style.css    "$CONFIG_HOME/waybar/style.css"
    link_config dotfiles/swaync/config.json  "$CONFIG_HOME/swaync/config.json"
    link_config dotfiles/swaync/style.css    "$CONFIG_HOME/swaync/style.css"
    link_config dotfiles/rofi/config.rasi    "$CONFIG_HOME/rofi/config.rasi"
    link_config dotfiles/rofi/menu.rasi      "$CONFIG_HOME/rofi/menu.rasi"
    link_config dotfiles/rofi/grid.rasi      "$CONFIG_HOME/rofi/grid.rasi"
    link_config dotfiles/wlogout/layout      "$CONFIG_HOME/wlogout/layout"

    # --- terminal, shell, tools ---------------------------------------------
    link_config dotfiles/kitty/kitty.conf    "$CONFIG_HOME/kitty/kitty.conf"
    link_config dotfiles/btop/btop.conf      "$CONFIG_HOME/btop/btop.conf"
    link_config dotfiles/zsh/.zshrc          "$HOME/.zshrc"

    # --- per-machine settings -----------------------------------------------
    # settings.lua holds the values the GUI owns. Deliberately NOT symlinked:
    # it is machine state, and shipping it would push personal choices into a
    # public repository.
    if [[ ! -f "$CONFIG_HOME/hypr/settings.lua" ]]; then
        step "$(msg step_settings_seed)"
        run mkdir -p "$CONFIG_HOME/hypr"
        run cp "$REPO_DIR/dotfiles/hypr/settings.example.lua" \
               "$CONFIG_HOME/hypr/settings.lua"

        # The keyboard answer from phase 05 lands here, and only here: the file
        # did not exist when the question was asked. Applied ONLY to a freshly
        # seeded file — an existing settings.lua belongs to the user and to the
        # settings GUI, and a re-run must not reach into it.
        #
        # settings.py rather than sed, because settings.lua is real Lua and is
        # read back through the lua interpreter. bhctl set would also work but
        # additionally reloads Hyprland, which is not running during install.
        if [[ -n "${SETUP_KB_LAYOUT:-}" ]]; then
            step "$(msg step_settings_keyboard "$SETUP_KB_LAYOUT" "${SETUP_KB_VARIANT:-–}")"
            run python3 "$REPO_DIR/scripts/settings.py" set \
                "input.kb_layout=$SETUP_KB_LAYOUT" \
                "input.kb_variant=${SETUP_KB_VARIANT:-}" \
                || warn "$(msg warn_settings_keyboard)"
        fi
    else
        info "$(msg info_settings_kept)"
    fi

    # --- the bhctl command ---------------------------------------------------
    step "$(msg step_bhctl)"
    run mkdir -p "$BIN_HOME"
    run ln -sfn "$REPO_DIR/bin/bhctl" "$BIN_HOME/bhctl"

    # The settings window, by the name its desktop entry uses. Without this the
    # entry says Exec=buchhwin-control-center and nothing on PATH answers to
    # that, so clicking Settings in the launcher failed with a file-not-found
    # error — while the application itself worked perfectly when started by its
    # full path. One missing symlink made the whole settings app look absent.
    run ln -sfn "$REPO_DIR/settings-gui/buchhwin-control-center" \
                "$BIN_HOME/buchhwin-control-center"

    # --- login shell ---------------------------------------------------------
    # Lives here, not in the base phase, because the base phase is skipped by
    # every configuration-only run — and then the shell quietly stayed bash.
    #
    # Plain `chsh` makes the account authenticate to itself, which fails
    # outright when the account has no password (cloud images, and every test
    # VM). Go through sudo, which the installer relies on everywhere else, and
    # keep bare chsh as the fallback for when sudo is what is missing.
    step "$(msg step_shell)"
    local current_shell
    current_shell="$(getent passwd "$USER" | cut -d: -f7)"
    if [[ "$current_shell" == *zsh ]]; then
        info "$(msg info_shell_already)"
    elif [[ ! -x /usr/bin/zsh ]]; then
        warn "$(msg warn_chsh)"
    elif (( DRY_RUN )); then
        printf '     %s[dry-run]%s chsh -s /usr/bin/zsh\n' "$C_DIM" "$C_RESET"
    elif sudo -n chsh -s /usr/bin/zsh "$USER" 2>/dev/null \
         || sudo chsh -s /usr/bin/zsh "$USER" 2>/dev/null \
         || chsh -s /usr/bin/zsh; then
        ok "$(msg ok_shell)"
    else
        warn "$(msg warn_chsh)"
    fi

    # The bar popups. Waybar calls them by their path inside the checkout, so
    # there is nothing to link — but a tarball download or a stray umask can
    # arrive without the executable bit, and then clicking the clock silently
    # does nothing at all.
    run chmod +x "$REPO_DIR/panel/buchhwin-panel"

    # ~/.local/bin is on Fedora's default PATH, but only if it exists at login
    # time — on a fresh Server install it does not.
    ensure_block "$HOME/.zprofile" "buchhwin path" \
'case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac'

    # --- generated colours, wired into files we do not own --------------------
    # tmux and git keep their own config in the home directory, and those
    # belong to the user. So instead of writing them, one line is APPENDED once
    # that pulls in the generated colours — idempotent, and removable by
    # deleting that one line.
    step "$(msg step_colour_includes)"
    _append_once "$HOME/.tmux.conf" \
        "source-file ~/.config/buchhwin/tmux-colors.conf" \
        "# buchhwin: colours follow the palette"
    _append_once "$CONFIG_HOME/git/config" \
        "	path = ~/.config/buchhwin/delta-colors.gitconfig" \
        "[include]"

    # --- desktop entries -----------------------------------------------------
    run mkdir -p "$DATA_HOME/applications"
    link_config settings-gui/buchhwin-control-center.desktop \
        "$DATA_HOME/applications/buchhwin-control-center.desktop"
    run_quiet update-desktop-database "$DATA_HOME/applications" || true

    # --- session environment -------------------------------------------------
    # In ~/.config/uwsm/env so it applies to the whole graphical session,
    # including applications started from the launcher rather than a shell.
    step "$(msg step_session_env)"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s write %s/uwsm/env\n' "$C_DIM" "$C_RESET" "$CONFIG_HOME"
    else
        mkdir -p "$CONFIG_HOME/uwsm"
        cat >"$CONFIG_HOME/uwsm/env" <<'EOF'
# Wayland-native toolkits
export QT_QPA_PLATFORM=wayland
export QT_QPA_PLATFORMTHEME=qt6ct
export QT_WAYLAND_DISABLE_WINDOWDECORATION=1
export GDK_BACKEND=wayland,x11
export SDL_VIDEODRIVER=wayland
export CLUTTER_BACKEND=wayland
export MOZ_ENABLE_WAYLAND=1
export ELECTRON_OZONE_PLATFORM_HINT=auto
export _JAVA_AWT_WM_NONREPARENTING=1

# Cursor size, read by both XCursor and hyprcursor consumers
export XCURSOR_SIZE=24
export HYPRCURSOR_SIZE=24
EOF
    fi
    ok "$(msg ok_dotfiles)"
}
