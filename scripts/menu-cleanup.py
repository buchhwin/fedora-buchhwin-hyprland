#!/usr/bin/env python3
"""Keep the launcher to things a person would actually start.

A stock Fedora desktop offers around fifty menu entries that exist only so
other software can find a handler: krita ships one per image format it can
open — over thirty of them — and there are entries for the certificate prompt,
the geolocation demo agent, the map URL handlers, the portal, and the autostart
helpers. None of them do anything useful when clicked.

The fix is the one the spec provides: a user-level .desktop of the same name
with NoDisplay=true shadows the system one, and menus honour it. (This is NOT
the same as Hidden=true in ~/.config/autostart, which this session's launcher
ignores — see lib/70-services.sh. Menus and autostart obey different keys.)

Nothing is deleted and nothing is uninstalled: krita still opens .psd files,
the portal still works. They simply stop cluttering the list.

    menu-cleanup.py            hide the noise
    menu-cleanup.py --list     show what would be hidden, change nothing
    menu-cleanup.py --restore  undo, completely
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
USER_APPS = DATA_HOME / "applications"
SYSTEM_DIRS = [
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
]

MARKER = "X-Buchhwin-Hidden"

# Matched against the .desktop file name, without the suffix.
NOISE = [
    r"krita_.*",                    # one per supported image format, 30+ of them
    r"gcr-.*",                      # certificate and key prompts
    r"geoclue-demo-agent",
    r"nm-applet",                   # the bar has its own network module
    r".*-geo-handler",              # openstreetmap, google-maps, wheelmap
    r"nemo-autorun-software",
    r"nemo-autostart",
    r"xdg-desktop-portal-.*",
    r"satty",                       # opened by the screenshot script, not by hand
    r"kitty-open",                  # the "open with kitty" handler, not kitty
    r"org\.gnome\.Evolution-alarm-notify",
    r"org\.gnome\.evolution-data-server\..*",
    r"org\.gnome\.goa-daemon",
    r"org\.gnome\.OnlineAccounts\..*",
    r"gkbd-keyboard-display",
    r"remmina-gnome",               # the session helper, not Remmina itself
    r"org\.remmina\.Remmina-file",
]
NOISE_RE = re.compile("^(?:%s)$" % "|".join(NOISE))


def system_entries() -> dict[str, Path]:
    """Every visible system entry, newest directory wins."""
    found: dict[str, Path] = {}
    for directory in SYSTEM_DIRS:
        if not directory.is_dir():
            continue
        for path in directory.glob("*.desktop"):
            found.setdefault(path.stem, path)
    return found


def is_noise(stem: str) -> bool:
    return bool(NOISE_RE.match(stem))


def already_hidden(path: Path) -> bool:
    try:
        return "NoDisplay=true" in path.read_text(errors="replace")
    except OSError:
        return False


def hide(stem: str, source: Path) -> bool:
    """Write the shadowing entry. Returns True when something changed."""
    target = USER_APPS / f"{stem}.desktop"
    if target.exists() and MARKER in target.read_text(errors="replace"):
        return False

    # A .desktop that shadows another must still be a valid entry, or some
    # implementations ignore it and the system one shows through. Name and Exec
    # are copied from the original for exactly that reason.
    name, exec_line = stem, "/bin/true"
    try:
        for line in source.read_text(errors="replace").splitlines():
            if line.startswith("Name=") and name == stem:
                name = line.split("=", 1)[1]
            elif line.startswith("Exec=") and exec_line == "/bin/true":
                exec_line = line.split("=", 1)[1]
    except OSError:
        pass

    USER_APPS.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={name}\n"
        f"Exec={exec_line}\n"
        "NoDisplay=true\n"
        f"{MARKER}=hidden by menu-cleanup.py; delete this file to bring it back\n"
    )
    return True


def restore() -> int:
    removed = 0
    if not USER_APPS.is_dir():
        return 0
    for path in USER_APPS.glob("*.desktop"):
        try:
            if MARKER in path.read_text(errors="replace"):
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show, change nothing")
    ap.add_argument("--restore", action="store_true", help="undo completely")
    args = ap.parse_args()

    if args.restore:
        print(f"  restored {restore()} entry(s)")
        return 0

    entries = system_entries()
    noisy = sorted(stem for stem in entries if is_noise(stem))

    if args.list:
        for stem in noisy:
            print(f"  {stem}")
        print(f"  -- {len(noisy)} of {len(entries)} entries would be hidden")
        return 0

    changed = sum(hide(stem, entries[stem]) for stem in noisy)
    print(f"  hid {changed} entry(s), {len(noisy)} matched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
