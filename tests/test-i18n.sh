#!/usr/bin/env bash
#
# The translation tables must agree, and every key the code asks for must
# exist. msg() falls back to English for a missing key and prints the raw key
# name only when it is missing from BOTH files — which means a key forgotten in
# de.sh is INVISIBLE unless something checks. Testing in German does not reveal
# it either: the English sentence appears and reads perfectly well.
#
# Run from anywhere: tests/test-i18n.sh
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 2

fail=0
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

collect() {   # collect <file> <out>
    # A separate shell, and no local MSG anywhere near it. The tables are
    # declared with `declare -gA MSG`, so sourcing them inside a function that
    # has its OWN MSG leaves the local one shadowing the global — and the list
    # comes back empty while looking like it worked.
    bash -c 'source "$1"; printf "%s\n" "${!MSG[@]}"' _ "$1" | sort >"$2"
}

collect i18n/en.sh "$tmp/en"
collect i18n/de.sh "$tmp/de"

missing_de="$(comm -23 "$tmp/en" "$tmp/de")"
if [[ -n "$missing_de" ]]; then
    printf '  FAIL missing from i18n/de.sh (would silently stay English):\n'
    printf '    %s\n' $missing_de
    fail=1
else
    printf '  ok   de.sh covers every English key (%s)\n' "$(wc -l <"$tmp/en")"
fi

stale_de="$(comm -13 "$tmp/en" "$tmp/de")"
if [[ -n "$stale_de" ]]; then
    printf '  FAIL in i18n/de.sh but not in i18n/en.sh (dead keys):\n'
    printf '    %s\n' $stale_de
    fail=1
else
    printf '  ok   de.sh has no keys English does not\n'
fi

# Every key the code asks for has to be defined somewhere, or the user is shown
# a bare identifier such as "warn_update".
grep -rhoE 'msg [a-z_]+' lib/ install.sh bin/ scripts/ 2>/dev/null \
    | awk '{print $2}' | sort -u >"$tmp/used"
undefined="$(comm -23 "$tmp/used" "$tmp/en")"
if [[ -n "$undefined" ]]; then
    printf '  FAIL used in code but defined nowhere:\n'
    printf '    %s\n' $undefined
    fail=1
else
    printf '  ok   all %s keys used in code are defined\n' "$(wc -l <"$tmp/used")"
fi

exit "$fail"
