#!/usr/bin/env python3
"""Every @colour a stylesheet uses must be defined by its template.

GTK drops a declaration whose colour is undefined. Not with a warning, not with
a fallback — the property simply does not apply, and the rule around it still
looks perfectly correct in the file.

That is not hypothetical. The dock's first stylesheet asked for `@barbg`,
`@pillhover` and `@overlay1`, which are waybar's colour names; panel/style.css
loads the PANEL's colours, which are called `@popupbg`, `@surface1` and
`@overlay0`. The result was a dock with no background, no hover and invisible
window dots — three rules applying cleanly to nothing.

The two stylesheets are themed from different templates on purpose (the bar and
the popups have different surfaces), so the names genuinely differ and there is
nothing to unify. What there can be is this check.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# stylesheet -> the template that generates the colours it loads
PAIRS = (
    ("panel/style.css", "theme/templates/panel-colors.css.tmpl"),
    ("dotfiles/waybar/style.css", "theme/templates/waybar-colors.css.tmpl"),
    ("dotfiles/swaync/style.css", "theme/templates/swaync-colors.css.tmpl"),
)

# @-rules, not colours.
KEYWORDS = {"import", "define", "keyframes", "media", "supports", "charset"}


def used_colours(css: str) -> set[str]:
    # Comments stripped first: this file explains the bug it prevents by naming
    # the wrong colours, and a checker that reads its own cautionary tale as
    # usage reports a failure that is not there.
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return set(re.findall(r"@([a-z0-9_]+)", css)) - KEYWORDS


def defined_colours(template: str) -> set[str]:
    return set(re.findall(r"@define-color\s+([a-z0-9_-]+)", template))


def main() -> int:
    failed = 0
    for sheet, template in PAIRS:
        sheet_path, template_path = REPO / sheet, REPO / template
        if not sheet_path.exists() or not template_path.exists():
            print(f"  ok   {sheet}: not present, nothing to check")
            continue
        missing = sorted(used_colours(sheet_path.read_text())
                         - defined_colours(template_path.read_text()))
        if missing:
            print(f"  FAIL {sheet} uses colours {template} does not define:")
            for name in missing:
                print(f"         @{name}")
            failed = 1
        else:
            print(f"  ok   {sheet}: every colour is defined")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
