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
import json
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
NOISE_RE = re.compile("^(?:{})$".format("|".join(NOISE)))


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
    # implementations ignore it and the system one shows through.
    #
    # And it must be a COMPLETE one. The shadow replaces the system file for
    # every purpose, not just for display: if it omits Icon, MimeType or
    # StartupWMClass, hiding an application from the launcher also strips its
    # icon everywhere, drops its file associations, and breaks the window rules
    # that match on its class. Fine for the noise list this started as; a
    # regression the moment a real application like Krita is hidden.
    copied = {"Name": stem, "Exec": "/bin/true"}
    keep = ("Name", "GenericName", "Comment", "Exec", "TryExec", "Icon",
            "Categories", "MimeType", "Keywords", "StartupWMClass", "Terminal",
            "Path", "StartupNotify")
    try:
        in_main = False
        for line in source.read_text(errors="replace").splitlines():
            if line.startswith("["):
                # Only the [Desktop Entry] group; actions have their own Name=
                # and Exec= and would otherwise overwrite the real ones.
                in_main = line.strip() == "[Desktop Entry]"
                continue
            if not in_main or "=" not in line:
                continue
            key, value = line.split("=", 1)
            base = key.split("[", 1)[0]        # drop Name[de] and friends
            if base in keep and base not in copied:
                copied[base] = value
            elif base in keep and base in ("Name", "Exec") and copied[base] in (stem, "/bin/true"):
                copied[base] = value
    except OSError:
        pass

    lines = ["[Desktop Entry]", "Type=Application"]
    lines += [f"{k}={v}" for k, v in copied.items()]
    lines.append("NoDisplay=true")
    lines.append(f"{MARKER}=hidden by buchhwin; delete this file to bring it back")

    USER_APPS.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n")
    return True


def restore(only: str | None = None) -> int:
    """Un-hide everything, or one entry by its stem."""
    removed = 0
    if not USER_APPS.is_dir():
        return 0
    for path in USER_APPS.glob("*.desktop"):
        if only is not None and path.stem != only:
            continue
        try:
            if MARKER in path.read_text(errors="replace"):
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def all_entries() -> list[dict]:
    """Every visible application, plus the ones WE have hidden.

    Deliberately not built on the NoDisplay filter the rest of the project
    uses: a list that hides hidden entries could never be used to un-hide one.
    Entries hidden by their own packager (NoDisplay in the system file, with no
    marker of ours) stay out — they were never meant to be listed.
    """
    found: dict[str, dict] = {}
    for directory in SYSTEM_DIRS:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.desktop")):
            if path.stem in found:
                continue
            name, no_display = path.stem, False
            try:
                for line in path.read_text(errors="replace").splitlines():
                    if line.startswith("Name=") and name == path.stem:
                        name = line.split("=", 1)[1]
                    elif line.strip() == "NoDisplay=true":
                        no_display = True
            except OSError:
                continue
            if no_display:
                continue
            found[path.stem] = {"id": path.stem, "name": name, "hidden": False}

    for path in USER_APPS.glob("*.desktop"):
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        if MARKER not in text:
            continue
        name = path.stem
        for line in text.splitlines():
            if line.startswith("Name="):
                name = line.split("=", 1)[1]
                break
        found[path.stem] = {"id": path.stem, "name": name, "hidden": True}

    return sorted(found.values(), key=lambda e: e["name"].lower())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show, change nothing")
    ap.add_argument("--restore", action="store_true", help="undo completely")
    # The settings app drives these three. Everything it needs is here rather
    # than in the GUI, so hiding an application means the same thing however it
    # is asked for.
    ap.add_argument("--all-json", action="store_true",
                    help="every listable application, as JSON, with its hidden state")
    ap.add_argument("--hide", metavar="ID", help="hide one entry by desktop id")
    ap.add_argument("--show", metavar="ID", help="un-hide one entry by desktop id")
    args = ap.parse_args()

    if args.all_json:
        print(json.dumps(all_entries(), indent=2))
        return 0

    if args.show:
        print(f"  restored {restore(args.show)} entry(s)")
        return 0

    if args.hide:
        entries = system_entries()
        source = entries.get(args.hide)
        if source is None:
            print(f"  no such entry: {args.hide}", file=sys.stderr)
            return 1
        print(f"  hid {int(hide(args.hide, source))} entry(s)")
        return 0

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
