#!/usr/bin/env bash
# Phase 80 — adjustments for virtual machines.
#
# A VM without GPU passthrough renders through llvmpipe on the CPU. Blur and
# animations are then unusably slow and say nothing about real hardware, so
# they are switched off — but through the SAME settings file the GUI writes,
# not a second config branch. One version runs everywhere.

phase_vm_tweaks() {
    (( IS_VM )) || return 0

    section "$(msg sec_vm)"
    info "$(msg info_vm_explain)"

    # Software rendering hints. Mesa picks llvmpipe by itself when there is no
    # accelerated device, but being explicit avoids a silent fallback to an
    # unusable driver on virtio-gpu without VirGL.
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s write %s/uwsm/env-hyprland\n' "$C_DIM" "$C_RESET" "$CONFIG_HOME"
    else
        mkdir -p "$CONFIG_HOME/uwsm"
        cat >"$CONFIG_HOME/uwsm/env-hyprland" <<'EOF'
# Virtual machine: no GPU, render on the CPU.
export WLR_RENDERER_ALLOW_SOFTWARE=1
export LIBGL_ALWAYS_SOFTWARE=1
export AQ_NO_MODIFIERS=1
EOF
    fi

    # Turn the expensive effects off in the file the settings GUI owns, so the
    # user can turn them back on from the GUI without editing anything.
    step "$(msg step_vm_effects)"
    run python3 "$REPO_DIR/scripts/settings.py" set \
        look.blur=false \
        look.shadow=false \
        look.animations=false \
        look.inactive_opacity=1.0 \
        look.terminal_opacity=1.0 \
        || warn "$(msg warn_vm_effects)"

    ok "$(msg ok_vm)"
}
