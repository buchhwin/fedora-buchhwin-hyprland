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

    # No unit for blueman-applet on purpose. Bluetooth moved out of the bar and
    # into the tray, and the obvious next step is a unit that starts the applet
    # — but Fedora's blueman package already ships /etc/xdg/autostart/blueman
    # .desktop, which the session honours. Adding one here would run a second
    # applet and put two Bluetooth icons in the tray. Checked in a running VM
    # before writing this: pid 1202, parent Hyprland, from XDG autostart.

    # nm-applet has to be actively stopped, not merely left out. Its tray icon
    # duplicates the bar's own network module, so you get two network icons.
    #
    # It came from BOTH places, which is what made this confusing: our own
    # settings.lua autostart list ran it, and Fedora ships
    # /etc/xdg/autostart/nm-applet.desktop as well. Removing it from our list
    # fixed half the problem and I reported the whole thing as done; the second
    # icon was still there.
    #
    # Measured, not assumed: the surviving process runs as
    # app-nm\x2dapplet@autostart.service — a unit systemd's xdg-autostart
    # generator builds from that .desktop file, with systemd --user as its
    # parent. So the fix is the one systemd offers for exactly this, rather
    # than a Hidden=true entry whose handling depends on the generator.
    run systemctl --user mask 'app-nm\x2dapplet@autostart.service' || true
    run systemctl --user stop 'app-nm\x2dapplet@autostart.service' || true

    # --- the bar's popups ----------------------------------------------------
    # Resident, because starting Python and GTK4 per click was measured at 1.1
    # seconds: 42 ms for Python, 518 ms for GTK4 and libadwaita, the rest in
    # layer-shell and CSS. None of that is our code, so none of it can be tuned
    # away — it can only be paid once, at login.
    _write_unit "buchhwin-panel.service" \
'[Unit]
Description=Status area popups (calendar, sound, network)
PartOf=graphical-session.target
After=graphical-session.target buchhwin-bar.service

[Service]
Type=simple
ExecStart=%h/.local/share/fedora-buchhwin-hyprland/panel/buchhwin-panel --daemon
Restart=always
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    # --- minimize ------------------------------------------------------------
    # Windows carry a minimize button now, so the button has to do something.
    # Hyprland has no minimize of its own; this listens on its event socket and
    # moves the window to a special workspace, which the dock's taskbar still
    # lists. Restart=always because the compositor's socket goes away with the
    # session and comes back with the next one.
    _write_unit "buchhwin-minimize.service" \
'[Unit]
Description=Minimize windows to a special workspace
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 %h/.local/share/fedora-buchhwin-hyprland/scripts/minimize.py
Restart=always
RestartSec=2

[Install]
WantedBy=graphical-session.target'

    # --- removable drives ----------------------------------------------------
    # --no-automount is deliberately NOT set: plugging a stick in and having it
    # appear is the whole point. --notify says so; --tray would add a second
    # drive icon next to the bar's own module.
    _write_unit "buchhwin-usb.service" \
'[Unit]
Description=Mount removable drives (udiskie)
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/udiskie --no-tray --notify --automount --file-manager nemo
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

    # --- the launcher --------------------------------------------------------
    # A stock desktop offers ~50 menu entries that exist so other software can
    # find a handler — krita alone ships one per image format. A launcher full
    # of those is one nobody trusts. Nothing is uninstalled; see the script.
    step "$(msg step_menu_cleanup)"
    run python3 "$REPO_DIR/scripts/menu-cleanup.py" || warn "$(msg warn_menu_cleanup)"

    # --- wallpaper + drives --------------------------------------------------
    # Both generate their own units from settings.lua, so the timer interval and
    # the drive list can never drift from what is configured.
    step "$(msg step_generated_units)"
    run "$REPO_DIR/scripts/wallpaper.sh" sync-timer || warn "$(msg warn_unit wallpaper-timer)"
    run python3 "$REPO_DIR/scripts/drives.py" sync || warn "$(msg warn_unit drives)"
    run python3 "$REPO_DIR/scripts/dock.py" sync || warn "$(msg warn_unit dock)"

    step "$(msg step_enable_units)"
    local u
    for u in buchhwin-keyring buchhwin-clipboard buchhwin-clipboard-image \
             buchhwin-wallpaper buchhwin-bar buchhwin-notifications \
             buchhwin-idle buchhwin-polkit buchhwin-nightlight \
             buchhwin-panel buchhwin-usb buchhwin-minimize; do
        run_quiet systemctl --user enable "$u.service" || warn "$(msg warn_unit "$u")"
    done
    run_quiet systemctl --user daemon-reload || true

    # Bluetooth is a system service and off by default on Fedora Server.
    if rpm -q bluez >/dev/null 2>&1 || (( DRY_RUN )); then
        run_quiet sudo systemctl enable bluetooth.service || true
    fi

    # So is printing. cups.socket rather than cups.service: it starts on the
    # first print job and costs nothing until then.
    if rpm -q cups >/dev/null 2>&1 || (( DRY_RUN )); then
        run_quiet sudo systemctl enable cups.socket || true
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
