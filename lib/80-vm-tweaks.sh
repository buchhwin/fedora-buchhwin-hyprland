#!/usr/bin/env bash
# Phase 80 — adjustments for virtual machines.
#
# A VM WITHOUT accelerated rendering runs through llvmpipe on the CPU. Blur and
# animations are then unusably slow and say nothing about real hardware, so
# they are switched off — but through the SAME settings file the GUI writes,
# not a second config branch. One version runs everywhere.
#
# A VM WITH VirGL is a different machine entirely and must be left alone. This
# phase used to fire on "is a VM" alone, and that was actively harmful: forcing
# LIBGL_ALWAYS_SOFTWARE=1 pins Mesa to swrast, whose EGL device carries no DRM
# node, so Hyprland's renderer fails to initialise and NOTHING draws at all.
# The workaround for having no GPU was what prevented using the one we had.

# ⚠️ gpu_is_accelerated() answers "yes" for any machine with no virtio GPU at
# all, because that is real hardware — or a hypervisor whose graphics it cannot
# interrogate. VirtualBox is the second case: it presents VMSVGA, not virtio, so
# the check waves it through as accelerated whether or not its 3D actually
# works. There is no reliable way to ask Mesa before a compositor exists, so
# --software-render is the honest answer: a switch, documented, rather than a
# guess that fails as a black screen.
phase_vm_tweaks() {
    if (( SOFTWARE_RENDER )); then
        section "$(msg sec_vm)"
        info "$(msg info_vm_forced)"
    elif (( ! IS_VM )); then
        return 0
    elif gpu_is_accelerated; then
        section "$(msg sec_vm)"
        # A machine that gained VirGL after an earlier install still carries the
        # old file, and it would keep the screen black. Clear it out.
        if [[ -f "$CONFIG_HOME/uwsm/env-hyprland" ]] && (( ! DRY_RUN )); then
            rm -f "$CONFIG_HOME/uwsm/env-hyprland"
        fi
        ok "$(msg ok_vm_accelerated)"
        # Said out loud, because "accelerated" here can also mean "could not be
        # checked", and somebody staring at a black screen needs to know which
        # branch ran.
        info "$(msg info_vm_hint_software)"
        return 0
    else
        section "$(msg sec_vm)"
        info "$(msg info_vm_explain)"
    fi

    # Software rendering hints. Mesa picks llvmpipe by itself when there is no
    # accelerated device, but being explicit avoids a silent fallback to an
    # unusable driver on virtio-gpu without VirGL.
    if (( DRY_RUN )); then
        printf '     %s[dry-run]%s write %s/uwsm/env-hyprland\n' "$C_DIM" "$C_RESET" "$CONFIG_HOME"
    else
        mkdir -p "$CONFIG_HOME/uwsm"
        cat >"$CONFIG_HOME/uwsm/env-hyprland" <<'EOF'
# Virtual machine without VirGL: no GPU, render on the CPU.
export WLR_RENDERER_ALLOW_SOFTWARE=1
export LIBGL_ALWAYS_SOFTWARE=1
export AQ_NO_MODIFIERS=1

# GTK4 draws through GSK, which picks OpenGL by default and does NOT fall back
# on its own when that turns out to be unusable. Everything in this desktop that
# is not the bar is GTK4 — the settings window and, more importantly, the
# resident panel daemon that every popup in the bar talks to. When it cannot
# start, the bar still looks perfectly fine and no click does anything at all.
#
# "cairo" is GTK's own software renderer, and the name is taken from
# `GSK_RENDERER=help` on this GTK, which lists broadway, cairo, opengl, gl and
# vulkan — anything else is warned about and ignored, which would look exactly
# like "the workaround did not help".
export GSK_RENDERER=cairo
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
