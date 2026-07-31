#!/usr/bin/env bash
# Phase 70 — user services.
#
# The background pieces of the desktop run as systemd user units rather than
# `exec-once` lines. That way they restart on crash, their logs land in the
# journal, and `bhctl doctor` can simply ask systemd whether the desktop is
# healthy instead of grepping process lists.

_write_unit() {
    local name="$1" content="$2"
    local dir="$CONFIG_HOME/systemd/user"
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s write %s/%s\n' "$C_DIM" "$C_RESET" "$dir" "$name"
        return 0
    fi
    mkdir -p "$dir"
    printf '%s\n' "$content" >"$dir/$name"
}

phase_services() {
    section "$(msg sec_services)"

    # graphical-session.target is bound to the Hyprland session by uwsm, so
    # everything below starts on login and stops on logout.

    _write_unit "buchhwin-clipboard.service" \
'[Unit]
Description=Clipboard history (cliphist)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/wl-paste --type text --watch /usr/bin/cliphist store
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    _write_unit "buchhwin-clipboard-image.service" \
'[Unit]
Description=Clipboard history for images (cliphist)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/wl-paste --type image --watch /usr/bin/cliphist store
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    _write_unit "buchhwin-wallpaper.service" \
'[Unit]
Description=Wallpaper daemon (swww)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/swww-daemon
# Call the script, not bhctl: `bhctl wallpaper <arg>` treats its argument as a
# FILE, so "restore" was passed to `wallpaper.sh set` and died with a usage
# error that `|| true` swallowed — leaving a black desktop until the slideshow
# timer fired up to half an hour later.
ExecStartPost=/bin/sh -c "sleep 1; %h/.local/share/fedora-buchhwin-hyprland/scripts/wallpaper.sh restore || true"
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    _write_unit "buchhwin-bar.service" \
'[Unit]
Description=Status bar (waybar)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/waybar
ExecReload=/bin/kill -SIGUSR2 $MAINPID
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    _write_unit "buchhwin-notifications.service" \
'[Unit]
Description=Notification centre (swaync)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/swaync
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    _write_unit "buchhwin-idle.service" \
'[Unit]
Description=Idle manager (hypridle)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/hypridle
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    _write_unit "buchhwin-polkit.service" \
'[Unit]
Description=Polkit authentication agent (hyprpolkitagent)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/libexec/hyprpolkitagent
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    _write_unit "buchhwin-nightlight.service" \
'[Unit]
Description=Night light (gammastep)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/gammastep -m wayland
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical-session.target'

    # --- keyring -------------------------------------------------------------
    # Without a running secret service every cloud and network drive asks for
    # its password again on every login, which defeats "sign in once".
    _write_unit "buchhwin-keyring.service" \
'[Unit]
Description=Secret service (gnome-keyring)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/gnome-keyring-daemon --foreground --components=secrets,pkcs11
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    # --- wallpaper + drives --------------------------------------------------
    # Both generate their own units from settings.lua, so the timer interval and
    # the drive list can never drift from what is configured.
    step "$(msg step_generated_units)"
    run "$REPO_DIR/scripts/wallpaper.sh" sync-timer || warn "$(msg warn_unit wallpaper-timer)"
    run python3 "$REPO_DIR/scripts/drives.py" sync || warn "$(msg warn_unit drives)"

    step "$(msg step_enable_units)"
    local u
    for u in buchhwin-keyring buchhwin-clipboard buchhwin-clipboard-image \
             buchhwin-wallpaper buchhwin-bar buchhwin-notifications \
             buchhwin-idle buchhwin-polkit buchhwin-nightlight; do
        run_quiet systemctl --user enable "$u.service" || warn "$(msg warn_unit "$u")"
    done
    run_quiet systemctl --user daemon-reload || true

    # Bluetooth is a system service and off by default on Fedora Server.
    if rpm -q bluez >/dev/null 2>&1 || (( DRY_RUN )); then
        run_quiet sudo systemctl enable bluetooth.service || true
    fi

    # --- keyring unlocks with the login --------------------------------------
    # This lives HERE and not in the base phase: /etc/pam.d/sddm does not exist
    # until SDDM is installed in phase 30, so in phase 20 the step silently
    # found nothing and only took effect on a second run — which nobody would
    # ever notice.
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


    ok "$(msg ok_services)"
}
