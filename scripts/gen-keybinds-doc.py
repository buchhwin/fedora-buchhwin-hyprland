#!/usr/bin/env python3
"""Generate docs/KEYBINDS.md from the shipped settings.

Documentation that is typed by hand drifts from the configuration within a
week. This reads settings.example.lua, so the table in the docs is the table
that is actually loaded. CI runs it with --check and fails if the file on disk
is out of date.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings as S

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = REPO / "dotfiles" / "hypr" / "settings.example.lua"
OUT = REPO / "docs" / "KEYBINDS.md"

# Bindings that live in binds.lua rather than settings.lua, because they are
# the grammar of the window manager rather than a preference.
STRUCTURAL = [
    ("SUPER + 1 … 0", "Switch workspace"),
    ("SUPER + SHIFT + 1 … 0", "Move window to workspace"),
    ("SUPER + h j k l  /  arrows", "Move focus"),
    ("SUPER + SHIFT + h j k l", "Move window"),
    ("SUPER + CTRL + h j k l", "Resize window"),
    ("SUPER + scroll", "Cycle workspaces"),
    ("SUPER + left mouse", "Drag window"),
    ("SUPER + right mouse", "Resize window by dragging"),
]

MEDIA = [
    ("Volume up / down / mute", "Also on the lock screen"),
    ("Mic mute", "Also on the lock screen"),
    ("Brightness up / down", "Also on the lock screen"),
    ("Play / pause / next / previous", "via playerctl"),
]

HEADER = """# Keyboard shortcuts

`SUPER` is the Windows key.

> Generated from `dotfiles/hypr/settings.example.lua` by
> `scripts/gen-keybinds-doc.py`. Do not edit by hand — change the settings
> instead, or use the settings GUI (`SUPER + I`), which can record a
> combination instead of asking you to type it.

"""


def table(rows: list[tuple[str, str]]) -> str:
    out = ["| Keys | Action |", "|---|---|"]
    out += [f"| `{k}` | {d} |" for k, d in rows]
    return "\n".join(out) + "\n"


def build() -> str:
    data = S.read(EXAMPLE)
    binds = data.get("binds", [])
    rows = [(b.get("key", ""), b.get("desc") or b.get("arg", "")) for b in binds]

    text = HEADER
    text += "## Configurable\n\nEvery line below is editable in the settings GUI.\n\n"
    text += table(rows)
    text += "\n## Structural\n\n"
    text += ("These are not in `settings.lua`: ten workspace switches and four "
             "focus directions in a settings list would be noise, not choice.\n\n")
    text += table(STRUCTURAL)
    text += "\n## Media and hardware keys\n\n"
    text += table(MEDIA)
    text += ("\n---\n\n`SUPER + /` shows this list in a searchable menu, built from "
             "your own configuration rather than from this file — so it is correct "
             "even if you have changed things.\n")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the file on disk differs (for CI)")
    args = ap.parse_args()

    text = build()
    if args.check:
        current = OUT.read_text() if OUT.exists() else ""
        if current != text:
            print("docs/KEYBINDS.md is out of date — run scripts/gen-keybinds-doc.py",
                  file=sys.stderr)
            return 1
        print("docs/KEYBINDS.md is up to date")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT.relative_to(REPO)} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
