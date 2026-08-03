"""Finding the icon and the name for an application.

Lifted out of scripts/dock.py when the dock stopped being a waybar config and
became a window of its own: both the generator and the dock need exactly this,
and two copies of an icon search is how they drift apart.

Two things here are not obvious, and both were measured rather than assumed:

  * The icon name is regularly NOT the application id. Nemo's desktop entry asks
    for `system-file-manager`, VS Code's for `vscode`. Looking up the id finds
    nothing for either, and finds it silently.

  * Fedora's Papirus-Dark declares `Inherits=breeze-dark,hicolor` — it does NOT
    inherit from Papirus — while carrying only part of the application icons
    itself (8178 at 64x64, but no kitty, no system-file-manager). Following the
    declared chain therefore misses most application icons, so the search order
    below is an explicit list rather than a walk of index.theme.
"""

from __future__ import annotations

import os
from pathlib import Path

_FALLBACK_THEMES = ("Papirus", "breeze-dark", "breeze", "hicolor", "Adwaita")
# Largest first, so a 32-pixel dock icon is downscaled rather than blown up.
# `scalable` leads because hicolor keeps its SVGs there; Papirus files its SVGs
# under the numbered sizes instead.
_SIZES = ("scalable", "128x128", "96x96", "84x84", "64x64", "48x48",
          "42x42", "32x32", "24x24", "22x22", "16x16")
_SECTIONS = ("apps", "mimetypes")

# Window class -> desktop entry id, for the cases where they differ and no
# amount of normalising bridges the gap. Carried over from the waybar dock's
# `app_ids-mapping`, which had to solve the same problem.
CLASS_ALIASES = {
    "brave-browser": "brave-origin",
    "de.buchhwin.controlcenter": "buchhwin-control-center",
    "code-oss": "code",
    "code - oss": "code",
}


def data_dirs() -> list[Path]:
    """Where desktop entries and icons live.

    Flatpak's export directories are named explicitly: they are in XDG_DATA_DIRS
    for a logged-in session, and not when this runs from the installer.
    """
    dirs = [Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))]
    dirs += [Path(p) for p in
             os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p]
    dirs += [Path.home() / ".local/share/flatpak/exports/share",
             Path("/var/lib/flatpak/exports/share")]
    return [d for d in dirs if d.is_dir()]


def desktop_file(app: str) -> Path | None:
    name = app if app.endswith(".desktop") else f"{app}.desktop"
    for base in data_dirs():
        candidate = base / "applications" / name
        if candidate.is_file():
            return candidate
    return None


def entry_field(app: str, field: str) -> str:
    """One field out of the [Desktop Entry] group.

    Stops at the next group header on purpose: an entry's actions carry their
    own Name= and Icon=, and reading the first match in the whole file would
    happily return "New Private Window".
    """
    path = desktop_file(app)
    if path is None:
        return ""
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError:
        return ""
    in_entry = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("["):
            if in_entry:
                break
            in_entry = stripped == "[Desktop Entry]"
            continue
        if in_entry and stripped.startswith(f"{field}="):
            return stripped.partition("=")[2].strip()
    return ""


def display_name(app: str) -> str:
    return entry_field(app, "Name") or app


def icon_path(app: str, theme: str = "Papirus-Dark") -> str | None:
    """An icon FILE for an application id, or None if nothing at all exists."""
    name = entry_field(app, "Icon") or app
    if name.startswith("/"):
        return name if Path(name).is_file() else None

    # The requested name first, the generic executable icon only if that finds
    # nothing at all — so a missing icon degrades to a plain one rather than to
    # a hole in the dock.
    for candidate in (name, "application-x-executable"):
        for base in data_dirs():
            icons = base / "icons"
            if not icons.is_dir():
                continue
            for th in (theme, *_FALLBACK_THEMES):
                for size in _SIZES:
                    for section in _SECTIONS:
                        for ext in (".svg", ".png"):
                            found = icons / th / size / section / f"{candidate}{ext}"
                            if found.is_file():
                                return str(found)
        for base in data_dirs():
            for ext in (".svg", ".png", ".xpm"):
                found = base / "pixmaps" / f"{candidate}{ext}"
                if found.is_file():
                    return str(found)
    return None


def normalise(window_class: str) -> str:
    """A window class, reduced to something comparable with a desktop id.

    `org.gnome.Calendar` and `gnome-calendar` are the same application as far as
    a dock is concerned, and neither equals the other as a string.
    """
    text = (window_class or "").strip().lower()
    if not text:
        return ""
    text = CLASS_ALIASES.get(text, text)
    # A reverse-DNS id keeps only its last component: org.gnome.Calendar
    # -> calendar. Done after the alias table so an alias can still match the
    # full id.
    if text.count(".") >= 2 and " " not in text:
        text = text.rsplit(".", 1)[-1]
    return text


def match_app(window_class: str, candidates: list[str]) -> str | None:
    """Which of `candidates` (desktop ids) this window belongs to, if any."""
    target = normalise(window_class)
    if not target:
        return None
    for candidate in candidates:
        if normalise(candidate) == target:
            return candidate
    # Second pass against what the entry calls itself, which catches a window
    # class that matches the StartupWMClass rather than the file name.
    for candidate in candidates:
        wm_class = entry_field(candidate, "StartupWMClass")
        if wm_class and normalise(wm_class) == target:
            return candidate
    return None
