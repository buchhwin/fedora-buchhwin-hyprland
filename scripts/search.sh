#!/usr/bin/env bash
#
# Search everything — applications, open windows, files, and arithmetic.
# Bound to ALT+Space, the way KRunner is.
#
# rofi already ships every mode this needs; the only thing missing upstream is
# a file search that is fast enough to run on every keystroke. That is what the
# "files" mode below is: plocate reads an index, so it answers in milliseconds.
# `fd` would walk the filesystem on each character and turn the launcher into a
# disk grinder — it is used only for the fallback, where there is no index.
#
#   search.sh              the combined launcher
#   search.sh files <str>  the file mode, called back by rofi
set -euo pipefail

SELF="$(readlink -f "$0")"
MAX_RESULTS=40

# --- the file mode ----------------------------------------------------------
# rofi script modes are called twice: once with no argument to list entries,
# and once with the chosen entry. Both are handled here.
if [[ "${1:-}" == "files" ]]; then
    query="${2:-}"

    # Second call: the user picked something. Open it and stop.
    if [[ -n "${ROFI_RETV:-}" && "$ROFI_RETV" == "1" && -e "$query" ]]; then
        exec gio open "$query"
    fi

    printf '\0prompt\x1ffiles\n'
    printf '\0no-custom\x1ftrue\n'
    [[ -z "$query" ]] && exit 0

    if command -v plocate >/dev/null 2>&1 && plocate --version >/dev/null 2>&1; then
        # --limit before --ignore-case so a broad query cannot stall the menu.
        plocate --limit "$MAX_RESULTS" --ignore-case -- "$query" 2>/dev/null || true
    else
        # No index yet. Search the home directory only — anything wider without
        # an index takes long enough that the launcher feels broken.
        fd --max-results "$MAX_RESULTS" --ignore-case --hidden \
           --exclude .git --exclude node_modules \
           "$query" "$HOME" 2>/dev/null || true
    fi
    exit 0
fi

# --- calculator -------------------------------------------------------------
# KRunner answers "12*8" without being asked to. Only digits and operators, so
# a search for a file called "2024" is never mistaken for arithmetic.
calc_mode() {
    local expr="${1:-}"
    # The patterns live in variables: a bracket expression written inline
    # inside [[ =~ ]] ends the test at its first ']', which is a syntax error
    # rather than a wrong match, so it fails loudly — but only at runtime.
    local arithmetic='^[0-9.+*/()%^ -]+$'
    local has_operator='[-+*/^%]'
    [[ "$expr" =~ $arithmetic ]] || return 0
    [[ "$expr" =~ $has_operator ]] || return 0
    local result
    result="$(python3 -c "
import ast, operator, sys
ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Mod: operator.mod, ast.Pow: operator.pow,
       ast.USub: operator.neg, ast.UAdd: operator.pos}
def ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)): return n.value
    if isinstance(n, ast.BinOp): return ops[type(n.op)](ev(n.left), ev(n.right))
    if isinstance(n, ast.UnaryOp): return ops[type(n.op)](ev(n.operand))
    raise ValueError
try:
    v = ev(ast.parse(sys.argv[1], mode='eval').body)
    print(int(v) if isinstance(v, float) and v.is_integer() else round(v, 10))
except Exception:
    pass
" "$expr" 2>/dev/null)"
    # Deliberately not `eval`: this string comes straight from a text box, and
    # ast with a fixed operator table cannot run anything.
    [[ -n "$result" ]] && printf '%s\n' "$result"
}

if [[ "${1:-}" == "calc" ]]; then
    calc_mode "${2:-}"
    exit 0
fi

# --- frequently used ---------------------------------------------------------
# The applications you actually open, best first, from the counts
# scripts/app-usage.py keeps. Ranked by launches with a 30-day half-life, so it
# reflects this month rather than "most used since installation".
#
# It appears as one more mode rather than reordering drun: drun's own order is
# alphabetical and predictable, and quietly shuffling it under people is how a
# launcher stops being learnable.
frequent_mode() {
    local id name file
    while read -r id; do
        [[ -n "$id" ]] || continue
        name="$id"
        for dir in /usr/share/applications /usr/local/share/applications \
                   "$HOME/.local/share/applications" \
                   /var/lib/flatpak/exports/share/applications; do
            file="$dir/$id.desktop"
            if [[ -f "$file" ]]; then
                name="$(sed -n 's/^Name=//p' "$file" | head -1)"
                break
            fi
        done
        printf '%s\0icon\x1f%s\n' "${name:-$id}" "$id"
    done < <(python3 "$(dirname "$0")/app-usage.py" top 12 2>/dev/null)
}

if [[ "${1:-}" == "frequent" ]]; then
    if [[ -n "${2:-}" ]]; then
        # rofi hands back the row it was given; launch by class is the same
        # guess the counter records, so gtk-launch on the id is the best we can
        # do and failing that, run it as a command.
        gtk-launch "$2" 2>/dev/null || setsid "$2" >/dev/null 2>&1 &
        exit 0
    fi
    frequent_mode
    exit 0
fi

# --- the launcher itself ----------------------------------------------------
exec rofi -show combi -modes "combi" \
     -combi-modes "drun,window,files:$SELF files,calc:$SELF calc,frequent:$SELF frequent" \
     -matching fuzzy -sort \
     -theme-str 'window { width: 46%; }'
