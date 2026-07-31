#!/usr/bin/env bash
# Phase 90 — say plainly what happened.
#
# The old script printed a cheerful message no matter what went wrong. This one
# reports installed / skipped / warnings / failures and exits non-zero if
# anything actually failed.

phase_summary() {
    section "$(msg sec_summary)"

    printf '  %s%-12s%s %d\n' "$C_GREEN" "$(msg sum_installed)" "$C_RESET" "${#INSTALLED[@]}"
    printf '  %s%-12s%s %d\n' "$C_DIM"   "$(msg sum_skipped)"   "$C_RESET" "${#SKIPPED[@]}"
    printf '  %s%-12s%s %d\n' "$C_YELLOW" "$(msg sum_warnings)" "$C_RESET" "${#WARNINGS[@]}"
    printf '  %s%-12s%s %d\n' "$C_RED"   "$(msg sum_failures)"  "$C_RESET" "${#FAILURES[@]}"

    if (( ${#WARNINGS[@]} )); then
        printf '\n  %s%s%s\n' "$C_YELLOW" "$(msg sum_warn_header)" "$C_RESET"
        printf '    - %s\n' "${WARNINGS[@]}"
    fi
    if (( ${#FAILURES[@]} )); then
        printf '\n  %s%s%s\n' "$C_RED" "$(msg sum_fail_header)" "$C_RESET"
        printf '    - %s\n' "${FAILURES[@]}"
    fi

    printf '\n  %s\n' "$(msg sum_log "$LOG_FILE")"

    if (( DRY_RUN )); then
        printf '\n  %s%s%s\n\n' "$C_BOLD" "$(msg sum_dry_run)" "$C_RESET"
        return 0
    fi

    if (( ${#FAILURES[@]} )); then
        printf '\n  %s%s%s\n\n' "$C_RED" "$(msg sum_incomplete)" "$C_RESET"
        return 1
    fi

    printf '\n%s%s%s\n' "$C_BOLD$C_GREEN" "$(msg sum_done)" "$C_RESET"
    printf '  %s\n' "$(msg sum_next_reboot)"
    printf '  %s\n' "$(msg sum_next_keys)"
    printf '  %s\n\n' "$(msg sum_next_settings)"
    return 0
}
