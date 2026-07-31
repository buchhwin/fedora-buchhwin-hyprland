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
ExecStartPost=/bin/sh -c "sleep 1; %h/.local/bin/bhctl wallpaper restore || true"
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

    ok "$(msg ok_services)"
}
