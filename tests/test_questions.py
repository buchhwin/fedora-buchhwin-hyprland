#!/usr/bin/env python3
"""Drive the installer's question helpers through a real pseudo-terminal.

This exists because of a bug that nothing else here could see. ask_choice,
ask_value and confirm return their answer through a caller-supplied variable
NAME, and _ask_raw held a local of the same name — so `printf -v` wrote into
its own local, which vanished on return. Every question quietly answered
itself with its default and confirm() always meant "no". The prompt appeared,
the typed text echoed back, and the answer went nowhere.

Neither shellcheck nor `--dry-run` can reach that path: --dry-run and
--unattended both return the default on purpose, which is exactly the wrong
answer to compare against. The only way to test it is to type at it.
"""

from __future__ import annotations

import os
import pty
import re
import select
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Each case: what the user types, and what the helper must return for it.
SCRIPT = r"""
set -uo pipefail
export REPO_DIR="{repo}"
export DRY_RUN=0 UNATTENDED=0
source "$REPO_DIR/lib/common.sh"
i18n_load en

_only_de_or_us() {{ [[ "$1" == de || "$1" == us ]]; }}

printf 'R1=%s\n' "$(ask_choice 'Palette?' mocha mocha latte nord)"
printf 'R2=%s\n' "$(ask_choice 'Palette?' mocha mocha latte nord)"
printf 'R3=%s\n' "$(ask_choice 'Palette?' mocha mocha latte nord)"
printf 'R4=%s\n' "$(ask_choice 'Palette?' mocha mocha latte nord)"
printf 'R5=%s\n' "$(ask_value 'Layout' us _only_de_or_us)"
if confirm 'Go on?'; then printf 'R6=yes\n'; else printf 'R6=no\n'; fi
printf 'DONE\n'
"""

# typed input, in order
INPUT = ["2", "", "nord", "99", "latte", "xx", "de", "y"]

EXPECTED = {
    "R1": "latte",   # picked by number
    "R2": "mocha",   # plain Enter takes the default
    "R3": "nord",    # typed by name instead of by number
    "R4": "latte",   # rejected once, then accepted
    "R5": "de",      # validator rejects "xx", accepts "de"
    "R6": "yes",     # confirm actually reads the answer
}

PROMPT = re.compile(rb"(\]: |\[y/N\] )$")


def run() -> dict[str, str]:
    script = SCRIPT.format(repo=REPO)
    pid, fd = pty.fork()
    if pid == 0:                                    # child
        os.execvp("bash", ["bash", "-c", script])

    buf, sent, deadline = b"", 0, time.time() + 60
    while time.time() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.5)
        if ready:
            try:
                chunk = os.read(fd, 4096)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            if b"DONE" in buf:
                break
        if PROMPT.search(buf) and sent < len(INPUT):
            os.write(fd, INPUT[sent].encode() + b"\n")
            sent += 1
            buf += b"<sent>"
            time.sleep(0.2)
    os.close(fd)
    try:
        os.waitpid(pid, 0)
    except OSError:
        pass

    text = buf.decode(errors="replace")
    return dict(
        line.strip().split("=", 1)
        for line in text.splitlines()
        if re.fullmatch(r"R\d=.*", line.strip())
    )


def main() -> int:
    if not (REPO / "lib" / "common.sh").is_file():
        print("lib/common.sh not found", file=sys.stderr)
        return 2

    got = run()
    failed = False
    for key, want in EXPECTED.items():
        have = got.get(key)
        if have == want:
            print(f"  ok   {key}: {have}")
        else:
            print(f"  FAIL {key}: expected {want!r}, got {have!r}")
            failed = True

    # A question must never hang or crash without a terminal either: piping
    # bootstrap.sh into bash is still advertised, and there stdin is the script.
    headless = subprocess.run(
        ["bash", "-c", SCRIPT.format(repo=REPO)],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if "DONE" not in headless.stdout:
        print("  FAIL no terminal: the helpers did not fall through to defaults")
        failed = True
    else:
        print("  ok   no terminal: defaults taken, nothing blocked")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
