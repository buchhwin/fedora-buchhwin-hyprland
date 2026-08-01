#!/usr/bin/env bash
# Phase 05 — ask for the handful of things that cannot be guessed.
#
# Before this phase existed, the whole installer asked exactly ONE question
# ("continue anyway?") and everything else came from command-line flags. That
# is fine for the person who wrote the flags and wrong for everyone else: the
# keyboard layout sat hard-coded as "de" in settings.example.lua, the timezone
# was never set at all, and a fresh Fedora Server kept the hostname "localhost".
#
# Placed AFTER preflight on purpose. Answering six questions and then being
# told the disk is too small is a worse experience than the other way round.
#
# Skipped entirely when --unattended: the test lab builds that way, and an
# unattended run must not touch the keyboard of the machine it lands on.

# --- validators -------------------------------------------------------------
# All three ask the tool that owns the answer, rather than carrying a list that
# would rot. localectl knows 99 layouts on Fedora 44 and timedatectl 598 zones;
# neither belongs in this file.
_setup_valid_layout()  { localectl list-x11-keymap-layouts 2>/dev/null | grep -qx -- "$1"; }
_setup_valid_variant() {
    [[ -z "$1" || "$1" == "-" ]] && return 0
    localectl list-x11-keymap-variants "$SETUP_KB_LAYOUT" 2>/dev/null | grep -qx -- "$1"
}
_setup_valid_tz()      { timedatectl list-timezones 2>/dev/null | grep -qx -- "$1"; }
# RFC 1123: letters, digits and hyphens, not starting or ending with one.
_setup_valid_host()    { [[ "$1" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; }

_setup_current_layout() {
    local l
    l="$(localectl status 2>/dev/null | sed -n 's/^ *X11 Layout: *//p' | head -1)"
    [[ -z "$l" ]] && l="${LANG%%_*}"
    _setup_valid_layout "$l" || l="us"
    printf '%s' "$l"
}

phase_setup() {
    section "$(msg sec_setup)"

    if (( UNATTENDED )); then
        info "$(msg info_setup_skipped)"
        return 0
    fi

    # --- keyboard ------------------------------------------------------------
    # The one question the user actually asked for. Three layers depend on it
    # and they are set by different things:
    #
    #   the Hyprland session      settings.lua -> input.kb_layout   (phase 60)
    #   the SDDM login screen     libxkbcommon reads the X11 keymap
    #   the text console (tty)    the vconsole keymap
    #
    # Wayland does not make the X11 one irrelevant: libxkbcommon reads
    # /etc/X11/xorg.conf.d/00-keyboard.conf, so the Wayland greeter reads it
    # too — and the login screen is where the password gets typed FIRST.
    #
    # Measured on 2026-08-02: `localectl set-x11-keymap de "" ""` sets the
    # console keymap as well (VC Keymap followed to fr-azerty in the test), so
    # one call covers both. A second `set-keymap` would be redundant.
    local cur; cur="$(_setup_current_layout)"
    SETUP_KB_LAYOUT="$(ask_choice "$(msg ask_kb_layout)" "$cur" \
        "$cur" us de gb fr es it ch at "$(msg ask_other)")"
    if [[ "$SETUP_KB_LAYOUT" == "$(msg ask_other)" ]]; then
        SETUP_KB_LAYOUT="$(ask_value "$(msg ask_kb_layout_free)" "$cur" _setup_valid_layout)"
    fi

    SETUP_KB_VARIANT=""
    local -a variants=()
    mapfile -t variants < <(localectl list-x11-keymap-variants "$SETUP_KB_LAYOUT" 2>/dev/null)
    if (( ${#variants[@]} )); then
        SETUP_KB_VARIANT="$(ask_choice "$(msg ask_kb_variant)" "-" \
            "-" "${variants[@]:0:8}" "$(msg ask_other)")"
        if [[ "$SETUP_KB_VARIANT" == "$(msg ask_other)" ]]; then
            SETUP_KB_VARIANT="$(ask_value "$(msg ask_kb_variant_free)" "-" _setup_valid_variant)"
        fi
        [[ "$SETUP_KB_VARIANT" == "-" ]] && SETUP_KB_VARIANT=""
    fi

    step "$(msg step_keymap "$SETUP_KB_LAYOUT" "${SETUP_KB_VARIANT:-–}")"
    run sudo localectl set-x11-keymap "$SETUP_KB_LAYOUT" "" "$SETUP_KB_VARIANT" \
        || warn "$(msg warn_keymap)"

    # --- timezone ------------------------------------------------------------
    local tz_now tz
    tz_now="$(timedatectl show -p Timezone --value 2>/dev/null)"
    [[ -z "$tz_now" ]] && tz_now="UTC"
    tz="$(ask_choice "$(msg ask_timezone)" "$tz_now" \
        "$tz_now" Europe/Berlin Europe/Vienna Europe/Zurich UTC "$(msg ask_other)")"
    if [[ "$tz" == "$(msg ask_other)" ]]; then
        tz="$(ask_value "$(msg ask_timezone_free)" "$tz_now" _setup_valid_tz)"
    fi
    if [[ "$tz" != "$tz_now" ]]; then
        step "$(msg step_timezone "$tz")"
        run sudo timedatectl set-timezone "$tz" || warn "$(msg warn_timezone)"
    fi

    # --- hostname ------------------------------------------------------------
    # Only worth asking when it is still a placeholder. Somebody who already
    # named their machine does not want to be asked about it again on every
    # re-run, and this installer is meant to be safe to run twice.
    local host_now; host_now="$(hostnamectl hostname 2>/dev/null || hostname)"
    case "$host_now" in
        localhost|localhost.localdomain|fedora|"")
            local host
            host="$(ask_value "$(msg ask_hostname)" "buchhwin" _setup_valid_host)"
            step "$(msg step_hostname "$host")"
            run sudo hostnamectl set-hostname "$host" || warn "$(msg warn_hostname)"
            ;;
        *)
            info "$(msg info_hostname_kept "$host_now")"
            ;;
    esac

    # --- palette -------------------------------------------------------------
    # Skipped when --flavour / --accent were given: a flag is already an answer,
    # and asking again would be asking the user to repeat themselves.
    if ! (( FLAVOUR_SET )); then
        local -a palettes=()
        mapfile -t palettes < <(
            find "$REPO_DIR/theme/palettes" -maxdepth 1 -name '*.json' -printf '%f\n' \
                2>/dev/null | sed 's/\.json$//' | sort
        )
        (( ${#palettes[@]} )) && THEME_FLAVOUR="$(ask_choice "$(msg ask_flavour)" \
            "$THEME_FLAVOUR" "${palettes[@]}")"
    fi

    if ! (( ACCENT_SET )); then
        # The accent list MUST come from the chosen palette. They differ —
        # gruvbox has no "sky" and no "lavender" — and theme/apply-theme.py
        # aborts on an accent the palette does not define.
        local -a accents=()
        mapfile -t accents < <(
            python3 -c "
import json,sys
try:
    print('\n'.join(json.load(open(sys.argv[1])).get('accents', [])))
except Exception:
    pass" "$REPO_DIR/theme/palettes/$THEME_FLAVOUR.json" 2>/dev/null
        )
        if (( ${#accents[@]} )); then
            local acc_default="$THEME_ACCENT"
            printf '%s\n' "${accents[@]}" | grep -qx -- "$acc_default" || acc_default="${accents[0]}"
            THEME_ACCENT="$(ask_choice "$(msg ask_accent)" "$acc_default" "${accents[@]}")"
        fi
    fi

    ok "$(msg ok_setup "$SETUP_KB_LAYOUT" "$tz" "$THEME_FLAVOUR" "$THEME_ACCENT")"
}
