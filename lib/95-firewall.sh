#!/usr/bin/env bash
# Phase 95 — the firewall: ufw, on by default.
#
# THIS PHASE RUNS LAST, ON PURPOSE.
#
# The installer is very often driven over SSH. `ufw enable` with a default-deny
# incoming policy cuts the connection the instant it is applied — unless the SSH
# rule is already in place. So: the rule first, the switch second, and the whole
# thing at the very end of the run, where a mistake costs you a reconnect rather
# than a half-installed machine.
#
# Why ufw and not firewalld: a deliberate choice, with real trade-offs written
# down in docs/SECURITY.md. Fedora integrates firewalld (NetworkManager,
# Cockpit, libvirt talk to it) and ufw goes through the iptables-nft compat
# layer. ufw is simpler to reason about day to day, which is the reason it was
# picked. Both must never run at once.

phase_firewall() {
    (( NO_FIREWALL )) && { section "$(msg sec_firewall)"; info "$(msg info_firewall_skipped)"; return 0; }

    section "$(msg sec_firewall)"
    dnf_install ufw

    # --- firewalld out of the way -------------------------------------------
    # Masked, not just disabled: a package update would otherwise happily start
    # it again, and two firewalls quietly fighting is worse than either alone.
    if rpm -q firewalld >/dev/null 2>&1; then
        step "$(msg step_firewalld_off)"
        run_quiet sudo systemctl disable --now firewalld.service || true
        run_quiet sudo systemctl mask firewalld.service || true
    fi

    # --- rules BEFORE enabling ----------------------------------------------
    step "$(msg step_ufw_rules)"
    run sudo ufw --force reset >/dev/null 2>&1 || true
    run sudo ufw default deny incoming
    run sudo ufw default allow outgoing

    # SSH first. Everything else in this phase depends on still having a
    # connection when it finishes.
    run sudo ufw allow 22/tcp comment 'SSH'

    # mDNS, or "nas.local" stops resolving and every network drive has to be
    # entered as a bare IP address.
    run sudo ufw allow 5353/udp comment 'mDNS (avahi)'

    # --- now switch it on ----------------------------------------------------
    step "$(msg step_ufw_enable)"
    run sudo ufw --force enable
    run_quiet sudo systemctl enable ufw.service || true

    if ! (( DRY_RUN )); then
        # Prove the connection survived rather than assuming it: if this line
        # never prints, the rule ordering above is wrong.
        if sudo ufw status | grep -q '22/tcp'; then
            ok "$(msg ok_firewall)"
        else
            fail "$(msg fail_firewall_ssh)"
        fi
    fi
}
