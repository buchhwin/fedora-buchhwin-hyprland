#!/usr/bin/env bash
#
# Every `hyprctl dispatch` in this repository has to speak Lua.
#
# Hyprland 0.55 replaced hyprlang with a Lua config provider, and hyprctl now
# wraps whatever it is given in hl.dispatch(...). The old word form that every
# tutorial still shows is therefore a Lua SYNTAX ERROR — which hyprctl reports
# on STDOUT and then exits 0 for. Nothing fails, nothing is logged, the thing
# simply does not happen.
#
# That is not a hypothetical: window snapping had never worked once, in ten
# call sites across four files, and the screen-off step in hypridle.conf was
# still broken three releases later. It survived because it is not a .lua file
# and not a .sh file, so every review that went looking at "the Hyprland
# config" walked straight past it.
#
# The rule, and it is deliberately mechanical: an occurrence must either
#   - be quoted in prose with backticks (`hyprctl dispatch dpms off`), which is
#     how this repository writes about the broken form, or
#   - be a real call naming a dispatcher under hl.
#
# Run from anywhere: tests/test-dispatch.sh
set -uo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 2

fail=0
checked=0
bad=()

# git ls-files where there is a git repository: it is exactly what CI checks
# out, and it leaves __pycache__ and build leftovers out without a filter list
# that would need maintaining. But an installed copy has no .git — this test was
# written with git ls-files alone and reported "all 0 occurrences, ok" when run
# on a test VM, which is the same kind of green nothing this file exists to
# prevent. Hence the fallback, and the count check below it.
# --others --exclude-standard, not a bare ls-files: a file that has been
# written but not yet `git add`ed is exactly the file most likely to carry a
# fresh mistake, and a bare ls-files does not list it. That is not theoretical
# either — the first run of this test reported a clean 13 because the two files
# added alongside it were still untracked.
list_files() {
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        git ls-files -z --cached --others --exclude-standard
    else
        find . -name .git -prune -o -name __pycache__ -prune -o -type f -print0
    fi
}

mapfile -d '' -t files < <(list_files)
if (( ${#files[@]} == 0 )); then
    printf '  FAIL nothing to scan — this test cannot pass by finding no files\n'
    exit 1
fi

while IFS= read -r hit; do
    file="${hit%%:*}"
    rest="${hit#*:}"
    number="${rest%%:*}"
    text="${rest#*:}"
    # This file itself. Its failure message and its own grep pattern contain the
    # string by necessity, and no wording gets around that.
    [[ "${file##*/}" == "test-dispatch.sh" ]] && continue
    checked=$((checked + 1))

    # Prose. Every mention of the broken form in this repository is inside
    # backticks, in a comment explaining why it is broken.
    [[ "$text" == *'`hyprctl dispatch'* ]] && continue

    # A real call. The quoting differs by file type — bare in a .conf, single
    # quotes in a shell script, escaped double quotes inside JSON — so only the
    # hl. prefix is required.
    [[ "$text" =~ hyprctl[[:space:]]+dispatch[[:space:]]+[\'\"\\]*hl\. ]] && continue

    bad+=("$file:$number: $(printf '%s' "$text" | sed 's/^[[:space:]]*//')")
    fail=1
done < <(grep -n 'hyprctl dispatch' "${files[@]}" 2>/dev/null)

if (( fail )); then
    printf '  FAIL old-style hyprctl dispatch (a Lua syntax error that exits 0):\n'
    printf '    %s\n' "${bad[@]}"
    printf '\n    Use the Lua form, e.g.\n'
    printf '      hyprctl dispatch %s\n' "'hl.dsp.dpms({ action = \"off\" })'"
    printf '    or put the mention in backticks if it is documentation.\n'
else
    printf '  ok   all %s hyprctl dispatch occurrences are Lua or documented\n' "$checked"
fi

exit "$fail"
