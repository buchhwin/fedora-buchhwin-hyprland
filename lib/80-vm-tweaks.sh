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
    (( SOFTWARE_RENDER )) || (( IS_VM )) || return 0
    section "$(msg sec_vm)"

    # Inside a VM the EDID physical size comes from the hypervisor, not from a
    # panel, so Hyprland's "auto" scale is derived from a number nobody
    # measured — and a VM that reports nonsense lands on 2, which is exactly
    # the "everything is twice as big" a first VirtualBox install produced.
    # Written into settings.lua, so the Displays page can override it.
    if (( IS_VM )); then
        step "$(msg step_vm_scale)"
        run python3 "$REPO_DIR/scripts/settings.py" set monitor_scale=1 \
            || warn "$(msg warn_vm_scale)"
    fi

    if (( ! SOFTWARE_RENDER )) && gpu_is_accelerated; then
        # A machine that gained VirGL after an earlier install still carries the
        # old file, and it would keep the screen black. Clear it out.
        if [[ -f "$CONFIG_HOME/uwsm/env-hyprland" ]] && (( ! DRY_RUN )); then
            rm -f "$CONFIG_HOME/uwsm/env-hyprland"
        fi

        # "Accelerated" here means one of two very different things, and the
        # difference decides whether the desktop works at all. With a virtio GPU
        # the VirGL bit was actually READ. Without one — VirtualBox presents
        # VMSVGA — nothing was measured; the answer is "no idea" wearing the
        # same clothes as "yes".
        #
        # For that second case GTK4 is put on its software renderer and nothing
        # else is touched. GSK picks OpenGL and does not fall back on its own,
        # and everything here that is not the bar is GTK4 — the settings window
        # and the panel daemon that draws the dock and every popup. In software
        # those cost almost nothing (a few small windows), while Hyprland keeps
        # using whatever actually works. Switching Mesa off wholesale instead
        # would throw away a working compositor to protect two dialogs.
        if gpu_check_is_conclusive; then
            ok "$(msg ok_vm_accelerated)"
        else
            info "$(msg info_vm_unverifiable)"
            if (( DRY_RUN )); then
                printf '     %s[dry-run]%s write %s/uwsm/env-hyprland\n' \
                    "$C_DIM" "$C_RESET" "$CONFIG_HOME"
            else
                mkdir -p "$CONFIG_HOME/uwsm"
                cat >"$CONFIG_HOME/uwsm/env-hyprland" <<'EOF'
# This VM's 3D could not be verified — it presents no virtio GPU, so there was
# no VirGL bit to read. Hyprland is left alone; only GTK4 is put on its software
# renderer, because it does not fall back by itself and the panel daemon failing
# to start looks like a bar where no click does anything.
export GSK_RENDERER=cairo
EOF
            fi
            info "$(msg info_vm_hint_software)"
        fi
        return 0
    fi

    (( SOFTWARE_RENDER )) && info "$(msg info_vm_forced)" || info "$(msg info_vm_explain)"

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
