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

# --- the launcher itself ----------------------------------------------------
exec rofi -show combi -modes "combi" \
     -combi-modes "drun,window,files:$SELF files,calc:$SELF calc" \
     -matching fuzzy -sort \
     -theme-str 'window { width: 46%; }'
