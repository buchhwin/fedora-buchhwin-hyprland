#!/usr/bin/env python3
"""Every tree that calls _() must install it.

`_()` is not a Python builtin. It exists because something called
`gettext.install()`, which puts it into builtins for every module imported
afterwards. Miss that call and the code still imports, still passes ruff, and
raises `NameError: name '_' is not defined` at the moment the string is needed.

That is not hypothetical: the dock's context menu used _() inside panel/, whose
entry point had never installed gettext. The menu never opened. The traceback
only appeared in the journal, because the exception happened inside a GTK
signal handler and GTK carried on.

⚠️ ruff cannot catch this. pyproject.toml declares `builtins = ["_"]` — correct
for the settings application, and precisely the blind spot for anything else.
Suppressing a warning in one place made it invisible everywhere.

So: for each tree, find whether any file uses _() and whether some file in it
installs gettext. Those two answers have to agree.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The trees that ship Python with user-visible strings, and the file that is
# expected to do the installing.
TREES = (
    ("panel", "panel/panel.py"),
    ("settings-gui", "settings-gui/buchhwin-control-center"),
)

USES = re.compile(r"(?<![\w.])_\(")
INSTALLS = re.compile(r"gettext\b[\s\S]{0,400}?\.install\(")


def python_files(tree: Path):
    for path in sorted(tree.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        if path.suffix == ".py" or (path.is_file() and path.suffix == ""):
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue
            if path.suffix == ".py" or text.startswith("#!"):
                yield path, text


def main() -> int:
    failed = 0
    for name, entry_point in TREES:
        tree = REPO / name
        if not tree.exists():
            print(f"  ok   {name}: not present")
            continue

        users = [p.relative_to(REPO) for p, text in python_files(tree) if USES.search(text)]
        entry = REPO / entry_point
        installs = entry.exists() and bool(INSTALLS.search(entry.read_text()))

        if users and not installs:
            print(f"  FAIL {name}: uses _() but {entry_point} never installs gettext")
            for path in users:
                print(f"         {path}")
            failed = 1
        elif users:
            print(f"  ok   {name}: {len(users)} file(s) use _(), {entry_point} installs it")
        else:
            print(f"  ok   {name}: does not use _()")
    return failed


if __name__ == "__main__":
    raise SystemExit(main())
