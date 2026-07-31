#!/usr/bin/env python3
"""Render every application's colours from a single Catppuccin palette.

This is the piece that makes "everything is themed" maintainable. Instead of
twenty hand-edited config files that drift apart, each application has one
template in theme/templates/ with placeholders, and this script renders all of
them from theme/palettes/<flavour>.json.

    apply-theme.py --flavour mocha --accent mauve

Placeholders
------------
    {{base}} {{mauve}} {{text}} ...   any colour name from the palette,
                                      rendered as #rrggbb
    {{base.hex}}                      rrggbb, no leading '#'
    {{base.rgb}}                      r, g, b   (decimal, comma separated)
    {{base.a80}}                      #rrggbbaa with alpha 0x80
    {{accent}}                        the chosen accent colour
    {{flavour}} {{accent_name}}       plain strings
    {{is_dark}}                       "true" or "false"
    {{gtk_scheme}}                    "prefer-dark" or "default"
    {{cursor_theme}} {{cursor_size}}  from settings.lua, not from the palette —
                                      the pointer is chosen by name and must
                                      survive a flavour switch

Anything that is not a known placeholder is left untouched, so a template can
contain literal braces without being mangled.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

THEME_DIR = Path(__file__).resolve().parent
REPO_DIR = THEME_DIR.parent
PALETTE_DIR = THEME_DIR / "palettes"
TEMPLATE_DIR = THEME_DIR / "templates"
MANIFEST = THEME_DIR / "manifest.json"

CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "buchhwin"

PLACEHOLDER = re.compile(r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?:\.([a-zA-Z0-9]+))?\}\}")


def load_palette(flavour: str) -> dict:
    path = PALETTE_DIR / f"{flavour}.json"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in PALETTE_DIR.glob("*.json")))
        sys.exit(f"unknown flavour '{flavour}'. Available: {available}")
    return json.loads(path.read_text())


def expand_path(raw: str) -> Path:
    return Path(
        raw.replace("$CONFIG", str(CONFIG_HOME))
           .replace("$DATA", str(DATA_HOME))
           .replace("$STATE", str(STATE_DIR))
           .replace("$HOME", str(Path.home()))
           .replace("$REPO", str(REPO_DIR))
    )


def user_setting(key: str, fallback: str) -> str:
    """Read one value out of settings.lua, or fall back.

    The cursor is the one part of the look the user picks by name rather than
    deriving from the palette, so it has to come from settings.lua — otherwise
    a theme switch would silently reset it. scripts/settings.py already knows
    how to read that file; there is no second parser here.
    """
    script = Path(__file__).resolve().parent.parent / "scripts" / "settings.py"
    if not script.exists():
        return fallback
    try:
        out = subprocess.run([sys.executable, str(script), "get", key],
                             capture_output=True, text=True, check=False,
                             timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return fallback
    # settings.py prints "not found: ..." to stdout when there is no file yet.
    if not out or out.startswith("not found") or out == "None":
        return fallback
    return out


def build_context(palette: dict, accent: str) -> dict:
    colors = palette["colors"]
    if accent not in colors:
        sys.exit(f"unknown accent '{accent}'. Available: {', '.join(sorted(colors))}")
    ctx = dict(colors)
    ctx["accent"] = colors[accent]
    ctx["_meta"] = {
        "flavour": palette["name"],
        "accent_name": accent,
        "is_dark": "true" if palette["dark"] else "false",
        "gtk_scheme": "prefer-dark" if palette["dark"] else "default",
        "cursor_theme": user_setting("look.cursor_theme", "breeze_cursors"),
        "cursor_size": user_setting("look.cursor_size", "24"),
    }
    return ctx


def render(text: str, ctx: dict) -> str:
    colors = {k: v for k, v in ctx.items() if k != "_meta"}
    meta = ctx["_meta"]

    def sub(match: re.Match) -> str:
        name, modifier = match.group(1), match.group(2)
        if name in meta and modifier is None:
            return meta[name]
        if name not in colors:
            return match.group(0)           # leave unknown braces alone
        hex6 = colors[name]
        if modifier is None:
            return f"#{hex6}"
        if modifier == "hex":
            return hex6
        if modifier == "rgb":
            r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
            return f"{r}, {g}, {b}"
        if re.fullmatch(r"a[0-9a-fA-F]{2}", modifier):
            return f"#{hex6}{modifier[1:].lower()}"
        return match.group(0)

    return PLACEHOLDER.sub(sub, text)


def write_if_changed(path: Path, content: str, dry_run: bool) -> bool:
    """Return True when the file actually changed.

    Skipping unchanged files keeps `bhctl theme` cheap and means the file
    modification times stay meaningful.
    """
    if path.exists() and path.read_text() == content:
        return False
    if dry_run:
        print(f"  [dry-run] would write {path}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return True


def reload_apps(changed: set[str]) -> None:
    """Tell running applications to pick the new colours up.

    Note: `hyprctl keyword` does NOT work with a Lua config (hyprctl(1):
    "This will not work if your config provider is lua"), so the compositor is
    reloaded wholesale instead.
    """
    def have(cmd: str) -> bool:
        return shutil.which(cmd) is not None

    def run(*cmd: str) -> None:
        with contextlib.suppress(OSError):
            subprocess.run(cmd, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if "hypr" in changed and have("hyprctl"):
        run("hyprctl", "reload")
    if "waybar" in changed:
        run("systemctl", "--user", "reload-or-restart", "buchhwin-bar.service")
    if "swaync" in changed and have("swaync-client"):
        run("swaync-client", "--reload-config")
        run("swaync-client", "--reload-css")
    if "kitty" in changed and have("kitten"):
        # Every running kitty instance, without restarting any of them.
        run("kitten", "@", "--to", "unix:/tmp/kitty", "load-config")
    if "gtk" in changed and have("gsettings"):
        pass  # handled below, needs the palette metadata


def apply_gsettings(ctx: dict) -> None:
    if shutil.which("gsettings") is None:
        return
    meta = ctx["_meta"]
    pairs = [
        ("org.gnome.desktop.interface", "color-scheme", meta["gtk_scheme"]),
        ("org.gnome.desktop.interface", "gtk-theme", "adw-gtk3-dark"
            if meta["is_dark"] == "true" else "adw-gtk3"),
        ("org.gnome.desktop.interface", "icon-theme", "Papirus-Dark"
            if meta["is_dark"] == "true" else "Papirus-Light"),
        ("org.gnome.desktop.interface", "cursor-theme", meta["cursor_theme"]),
        ("org.gnome.desktop.interface", "cursor-size", meta["cursor_size"]),
        ("org.gnome.desktop.interface", "font-name", "Inter 11"),
        ("org.gnome.desktop.interface", "monospace-font-name", "JetBrainsMono Nerd Font 11"),
    ]
    for schema, key, value in pairs:
        subprocess.run(["gsettings", "set", schema, key, value],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render all app configs from one Catppuccin palette.")
    ap.add_argument("--flavour", default="mocha")
    ap.add_argument("--accent", default="mauve")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-reload", action="store_true",
                    help="Render files but do not signal running applications.")
    args = ap.parse_args()

    palette = load_palette(args.flavour)
    ctx = build_context(palette, args.accent)

    if not MANIFEST.exists():
        sys.exit(f"missing manifest: {MANIFEST}")
    manifest = json.loads(MANIFEST.read_text())

    changed_groups: set[str] = set()
    written = 0
    for entry in manifest["files"]:
        template = TEMPLATE_DIR / entry["template"]
        if not template.exists():
            print(f"  ! missing template: {entry['template']}", file=sys.stderr)
            continue
        target = expand_path(entry["target"])
        content = render(template.read_text(), ctx)
        if write_if_changed(target, content, args.dry_run):
            written += 1
            changed_groups.add(entry.get("group", "misc"))

    # Record what is active, so bhctl and the settings GUI agree with reality.
    if not args.dry_run:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        (STATE_DIR / "theme.json").write_text(
            json.dumps({"flavour": args.flavour, "accent": args.accent}, indent=2) + "\n"
        )

    print(f"  theme: {args.flavour}/{args.accent} - {written} file(s) updated")

    if not args.no_reload and not args.dry_run:
        apply_gsettings(ctx)
        reload_apps(changed_groups)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
