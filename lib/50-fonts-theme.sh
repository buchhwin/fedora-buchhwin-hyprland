#!/usr/bin/env bash
# Phase 50 — fonts, cursors, icons, greeter theme, and the first theme render.
#
# App colours are NOT cloned from a dozen theme repositories. theme/apply-theme.py
# renders every config from one palette file, so a flavour switch later touches
# exactly the same files in exactly the same way.
#
# Only three things genuinely have to come from outside, because they are
# binaries or QML rather than colour values:
#   * the patched Nerd Font
#   * the cursor theme
#   * the SDDM greeter theme
# Plus Kvantum (Qt widget shapes) and papirus-folders (icon recolouring script).

NERD_FONT_VERSION="3.4.0"
NERD_FONT_URL="https://github.com/ryanoasis/nerd-fonts/releases/download/v${NERD_FONT_VERSION}/JetBrainsMono.tar.xz"

_fetch_zip() {
    # _fetch_zip <url> <destination-dir> <human-name>
    local url="$1" dest="$2" name="$3"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s download %s\n' "$C_DIM" "$C_RESET" "$url"
        return 0
    fi
    local tmp; tmp="$(mktemp -d)"
    if curl -fsSL --max-time 180 -o "$tmp/a.zip" "$url"; then
        mkdir -p "$dest"
        unzip -qo "$tmp/a.zip" -d "$dest"
        rm -rf "$tmp"
        return 0
    fi
    rm -rf "$tmp"
    warn "$(msg warn_download "$name")"
    return 1
}

_install_nerd_font() {
    local dest="$DATA_HOME/fonts/JetBrainsMonoNerdFont"
    if [[ -d "$dest" ]] && compgen -G "$dest/*.ttf" >/dev/null; then
        info "$(msg info_font_present)"
        return 0
    fi
    step "$(msg step_nerd_font "$NERD_FONT_VERSION")"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s download %s\n' "$C_DIM" "$C_RESET" "$NERD_FONT_URL"
        return 0
    fi
    local tmp; tmp="$(mktemp -d)"
    if curl -fsSL --max-time 300 -o "$tmp/font.tar.xz" "$NERD_FONT_URL"; then
        mkdir -p "$dest"
        tar -xJf "$tmp/font.tar.xz" -C "$dest"
        rm -f "$dest"/*Windows*.ttf 2>/dev/null || true
        fc-cache -f "$dest" >>"$LOG_FILE" 2>&1
        ok "$(msg ok_font)"
    else
        fail "$(msg fail_font)"
    fi
    rm -rf "$tmp"
}

_clone_or_update() {
    local url="$1" dest="$2"
    if [[ -d "$dest/.git" ]]; then
        run_quiet git -C "$dest" pull --ff-only || true
    else
        run mkdir -p "$(dirname "$dest")"
        run_quiet git clone --depth 1 "$url" "$dest" || return 1
    fi
}

_palette_field() {
    # One field out of theme/palettes/<name>.json. Empty when the palette is
    # missing, so callers fall back rather than break the install.
    python3 - "$REPO_DIR" "$1" "$2" 2>/dev/null <<'PY' || true
import json, sys
from pathlib import Path
path = Path(sys.argv[1]) / "theme" / "palettes" / f"{sys.argv[2]}.json"
try:
    print(json.loads(path.read_text()).get(sys.argv[3], ""))
except Exception:
    print("")
PY
}

phase_theme() {
    section "$(msg sec_theme)"

    local src="$DATA_HOME/buchhwin-sources"

    # Light or dark, and which family — read from the palette rather than from
    # a hardcoded "latte means light". There are nine palettes now and more can
    # be dropped into theme/palettes/ without editing this file.
    local dark="dark" family="Catppuccin"
    if [[ "$(_palette_field "$THEME_FLAVOUR" dark)" == "False" ]]; then dark="light"; fi
    family="$(_palette_field "$THEME_FLAVOUR" family)"

    # Cursors, recoloured folders, Kvantum and the SDDM theme are downloaded
    # from the Catppuccin project. They exist for Catppuccin and for nothing
    # else, so for any other family they are skipped with a note rather than
    # failing four times over. Everything the theme ENGINE renders — 17 files,
    # every application — works for every palette; these four are extras.
    local catppuccin=0
    [[ "$family" == "Catppuccin" ]] && catppuccin=1

    _install_nerd_font

    if (( ! catppuccin )); then
        info "$(msg note_family_extras "$family")"
    fi

    # --- cursors -------------------------------------------------------------
    local cursor_name="catppuccin-${THEME_FLAVOUR}-${dark}-cursors"
    if (( catppuccin )); then
    if [[ -d "$DATA_HOME/icons/$cursor_name" ]]; then
        info "$(msg info_cursor_present)"
    else
        step "$(msg step_cursors "$cursor_name")"
        _fetch_zip \
            "https://github.com/catppuccin/cursors/releases/latest/download/${cursor_name}.zip" \
            "$DATA_HOME/icons" "cursors" && ok "$(msg ok_cursors)"
    fi
    fi

    # --- GTK -----------------------------------------------------------------
    # catppuccin/gtk was archived by its authors ("a nightmare to consistently
    # theme and maintain"). Instead: adw-gtk3-theme from Fedora provides the
    # widget shapes for GTK3, and apply-theme.py writes the Catppuccin colour
    # overrides for both GTK3 and GTK4/libadwaita. One source of truth, no
    # unmaintained dependency.
    dnf_install adw-gtk3-theme

    # --- icons ---------------------------------------------------------------
    step "$(msg step_icons)"
    if (( ! catppuccin )); then
        :   # nothing to recolour: the folder sets are a Catppuccin artefact
    elif _clone_or_update "https://github.com/catppuccin/papirus-folders.git" "$src/papirus-folders"; then
        if ! (( DRY_RUN )); then
            # Copy the recoloured folder sets into the user icon directory so
            # no root-owned files land in /usr/share.
            mkdir -p "$DATA_HOME/icons"
            cp -rn /usr/share/icons/Papirus* "$DATA_HOME/icons/" 2>/dev/null || true
            if [[ -x "$src/papirus-folders/papirus-folders" ]]; then
                "$src/papirus-folders/papirus-folders" \
                    -C "cat-${THEME_FLAVOUR}-${THEME_ACCENT}" \
                    --theme "Papirus-$([[ "$dark" == "light" ]] && echo Light || echo Dark)" \
                    >>"$LOG_FILE" 2>&1 || warn "$(msg warn_icons)"
            fi
        fi
    else
        warn "$(msg warn_icons)"
    fi

    # --- Qt / Kvantum --------------------------------------------------------
    step "$(msg step_kvantum)"
    if (( catppuccin )) && _clone_or_update "https://github.com/catppuccin/kvantum.git" "$src/catppuccin-kvantum"; then
        if ! (( DRY_RUN )); then
            local kv="$src/catppuccin-kvantum/themes/catppuccin-${THEME_FLAVOUR}-${THEME_ACCENT}"
            if [[ -d "$kv" ]]; then
                mkdir -p "$CONFIG_HOME/Kvantum"
                cp -r "$kv" "$CONFIG_HOME/Kvantum/" 2>/dev/null || true
                printf '[General]\ntheme=catppuccin-%s-%s\n' \
                    "$THEME_FLAVOUR" "$THEME_ACCENT" >"$CONFIG_HOME/Kvantum/kvantum.kvconfig"
            else
                warn "$(msg warn_kvantum "$THEME_FLAVOUR-$THEME_ACCENT")"
            fi
        fi
    fi

    # --- SDDM greeter --------------------------------------------------------
    local sddm_theme="catppuccin-${THEME_FLAVOUR}-${THEME_ACCENT}-sddm"
    if (( catppuccin )); then
    step "$(msg step_sddm_theme "$sddm_theme")"
    if _fetch_zip \
        "https://github.com/catppuccin/sddm/releases/latest/download/${sddm_theme}.zip" \
        "$STATE_DIR/sddm" "SDDM theme"
    then
        if ! (( DRY_RUN )); then
            sudo mkdir -p /usr/share/sddm/themes
            sudo cp -r "$STATE_DIR/sddm/"* /usr/share/sddm/themes/ 2>/dev/null || true
            sudo mkdir -p /etc/sddm.conf.d
            printf '[Theme]\nCurrent=%s\n' "${sddm_theme%-sddm}" \
                | sudo tee /etc/sddm.conf.d/20-buchhwin-theme.conf >/dev/null
            ok "$(msg ok_sddm_theme)"
        fi
    fi
    fi

    # --- render every app config from the palette ---------------------------
    step "$(msg step_render_theme "$THEME_FLAVOUR" "$THEME_ACCENT")"
    run python3 "$REPO_DIR/theme/apply-theme.py" \
        --flavour "$THEME_FLAVOUR" --accent "$THEME_ACCENT" --no-reload \
        || fail "$(msg fail_theme)"
}
