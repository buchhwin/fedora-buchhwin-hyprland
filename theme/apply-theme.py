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


_SETTINGS_CACHE: dict | None = None


def _all_settings() -> dict:
    """Read settings.lua once, not once per key.

    Every call to settings.py spawns Python AND a Lua interpreter. Four keys
    meant four of those, and with the rest of a render that pushed this script
    past the settings app's 20-second budget for a single step — Apply reported
    "theme: timed out" and skipped it. One `dump` costs the same as one `get`.
    """
    global _SETTINGS_CACHE
    if _SETTINGS_CACHE is not None:
        return _SETTINGS_CACHE
    _SETTINGS_CACHE = {}
    script = Path(__file__).resolve().parent.parent / "scripts" / "settings.py"
    if script.exists():
        try:
            out = subprocess.run([sys.executable, str(script), "dump"],
                                 capture_output=True, text=True, check=False,
                                 timeout=15).stdout
            _SETTINGS_CACHE = json.loads(out) if out.strip() else {}
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            _SETTINGS_CACHE = {}
    return _SETTINGS_CACHE


def user_setting(key: str, fallback: str) -> str:
    """Read one value out of settings.lua, or fall back.

    The cursor is the one part of the look the user picks by name rather than
    deriving from the palette, so it has to come from settings.lua — otherwise
    a theme switch would silently reset it. scripts/settings.py already knows
    how to read that file; there is no second parser here.
    """
    node = _all_settings()
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return fallback
        node = node[part]
    if node is None or isinstance(node, (dict, list)):
        return fallback
    return str(node)


def build_context(palette: dict, accent: str) -> dict:
    colors = palette["colors"]
    if accent not in colors:
        sys.exit(f"unknown accent '{accent}'. Available: {', '.join(sorted(colors))}")
    ctx = dict(colors)
    ctx["accent"] = colors[accent]
    dark = bool(palette["dark"])
    ctx["_meta"] = {
        "flavour": palette["name"],
        "accent_name": accent,
        "is_dark": "true" if dark else "false",
        "gtk_scheme": "prefer-dark" if dark else "default",
        # Derived here and NOWHERE else. The GTK3 template used to hard-code
        # adw-gtk3-dark, Papirus-Dark and prefer-dark-theme=1 while
        # apply_gsettings() worked it out properly — so a light palette got a
        # dark GTK3 theme and dark icons, and Latte simply looked broken.
        # One source, three consumers.
        "gtk_theme": "adw-gtk3-dark" if dark else "adw-gtk3",
        "icon_theme": "Papirus-Dark" if dark else "Papirus-Light",
        "prefer_dark": "1" if dark else "0",
        # Window buttons. GTK's default is "appmenu:close" — a close button and
        # nothing else, which is why no window had minimize or maximize.
        "button_layout": "appmenu:minimize,maximize,close",
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
    if "bat" in changed and have("bat"):
        # bat reads themes from a binary cache, not from the .tmTheme file, so
        # writing the file alone changes nothing at all.
        run("bat", "cache", "--build")
    if "vscode" in changed:
        merge_vscode()
    if "brave" in changed:
        merge_brave()


def _merge_json(path: Path, updates: dict) -> None:
    """Merge keys into a JSON file, keeping everything already in it.

    These two files belong to the applications, not to us. Overwriting them
    would throw away every preference the user has set — which is exactly the
    kind of "theming" that makes people uninstall a theme.
    """
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text() or "{}")
        except (OSError, json.JSONDecodeError):
            return                      # unreadable: leave it entirely alone
    if not isinstance(data, dict):
        return
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(data.get(key), dict):
            data[key].update(value)
        else:
            data[key] = value
    with contextlib.suppress(OSError):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")


def merge_vscode() -> None:
    source = STATE_DIR / "vscode-colors.json"
    target = CONFIG_HOME / "Code" / "User" / "settings.json"
    if not source.exists() or not target.parent.parent.exists():
        return                          # VS Code not installed: nothing to do
    try:
        wanted = json.loads(source.read_text())
    except (OSError, json.JSONDecodeError):
        return
    wanted.pop("//", None)
    wanted.pop("//2", None)
    _merge_json(target, wanted)


def merge_brave() -> None:
    """Brave's frame colour lives in Local State, as decimal RGB."""
    source = STATE_DIR / "brave-theme.txt"
    target = (CONFIG_HOME / "BraveSoftware" / "Brave-Browser" / "Local State")
    if not source.exists() or not target.exists():
        return
    values = {}
    try:
        for line in source.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, hex6 = line.split("=", 1)
                values[key.strip()] = hex6.strip()
    except OSError:
        return
    frame = values.get("frame")
    if not frame or len(frame) != 6:
        return
    rgb = [int(frame[i:i + 2], 16) for i in (0, 2, 4)]
    _merge_json(target, {"brave": {"theme": {"user_color_scheme": 1},
                                   "custom_theme_color": rgb}})


def apply_cursor(ctx: dict, dry_run: bool = False) -> None:
    """Make the pointer change everywhere, not just in GTK applications.

    Setting gsettings alone looks like it works — `gsettings get` returns the new
    name — and changes nothing you can see, because the pointer you look at over
    the wallpaper is drawn by the COMPOSITOR. Four separate consumers each read a
    different source, and three of them were never written:

      GTK             gsettings + gtk-3.0/settings.ini   (was already handled)
      Hyprland        `hyprctl setcursor`, or its env at startup
      systemd units   ~/.config/uwsm/env   (bar, popups, notifications)
      X11 / XWayland  ~/.icons/default/index.theme

    Everything here is idempotent and survives a missing file or a missing
    hyprctl; a pointer theme is not worth an exception.
    """
    meta = ctx["_meta"]
    theme, size = meta["cursor_theme"], str(meta["cursor_size"])

    # 1. The compositor, live. This is the one that repaints the pointer over the
    #    wallpaper, the bar and every client that does not set its own cursor.
    if shutil.which("hyprctl") and not dry_run:
        subprocess.run(["hyprctl", "setcursor", theme, size], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. libXcursor's fallback, used by XWayland, SDL and several Electron
    #    builds when XCURSOR_THEME is absent — which it is for anything not
    #    started by Hyprland itself.
    default_icons = Path.home() / ".icons" / "default"
    with contextlib.suppress(OSError):
        default_icons.mkdir(parents=True, exist_ok=True)
        write_if_changed(default_icons / "index.theme",
                         "[Icon Theme]\n"
                         "Name=Default\n"
                         "Comment=Generated by buchhwin — do not edit\n"
                         f"Inherits={theme}\n", dry_run)

    # 3. The session environment. The bar, the popups and swaync run as systemd
    #    user units, so they inherit uwsm/env — not Hyprland's own env. It listed
    #    a hard-coded size and no theme at all.
    env_file = CONFIG_HOME / "uwsm" / "env"
    wanted = {"XCURSOR_THEME": theme, "HYPRCURSOR_THEME": theme,
              "XCURSOR_SIZE": size, "HYPRCURSOR_SIZE": size}
    with contextlib.suppress(OSError):
        env_file.parent.mkdir(parents=True, exist_ok=True)
        lines = env_file.read_text().splitlines() if env_file.exists() else []
        kept = [ln for ln in lines
                if not any(ln.strip().startswith(f"export {k}=") for k in wanted)]
        while kept and not kept[-1].strip():
            kept.pop()
        block = [f'export {k}="{v}"' for k, v in wanted.items()]
        write_if_changed(env_file, "\n".join([*kept, *block]) + "\n", dry_run)

    # 4. Hand the new values to things started later by D-Bus or systemd. Without
    #    this they keep the environment from login until the next one.
    for cmd in (["dbus-update-activation-environment", "--systemd",
                 *(f"{k}={v}" for k, v in wanted.items())],
                ["systemctl", "--user", "import-environment", *wanted]):
        if shutil.which(cmd[0]) and not dry_run:
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)


def apply_gsettings(ctx: dict) -> None:
    if shutil.which("gsettings") is None:
        return
    meta = ctx["_meta"]
    pairs = [
        ("org.gnome.desktop.interface", "color-scheme", meta["gtk_scheme"]),
        # Same values the templates use, from the same place — they used to be
        # worked out twice and disagreed.
        ("org.gnome.desktop.interface", "gtk-theme", meta["gtk_theme"]),
        ("org.gnome.desktop.interface", "icon-theme", meta["icon_theme"]),
        ("org.gnome.desktop.interface", "cursor-theme", meta["cursor_theme"]),
        ("org.gnome.desktop.interface", "cursor-size", meta["cursor_size"]),
        ("org.gnome.desktop.interface", "font-name", "Inter 11"),
        ("org.gnome.desktop.interface", "monospace-font-name", "JetBrainsMono Nerd Font 11"),
        # The schema that actually controls the titlebar buttons for GTK4 and
        # libadwaita. It was never touched, so every window had close only.
        ("org.gnome.desktop.wm.preferences", "button-layout", meta["button_layout"]),
    ]
    for schema, key, value in pairs:
        subprocess.run(["gsettings", "set", schema, key, value],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render all app configs from one Catppuccin palette.")
    # No default= here on purpose. With `default="mocha"` every caller that
    # omitted the flag silently re-rendered mocha/mauve and overwrote
    # theme.json — so pressing Apply on ANY settings page threw away the
    # flavour the user had chosen. Falling back to settings.lua instead means
    # "no argument" means "whatever is configured", which is what both the
    # settings app and `bhctl restore` actually want.
    ap.add_argument("--flavour")
    ap.add_argument("--accent")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-reload", action="store_true",
                    help="Render files but do not signal running applications.")
    args = ap.parse_args()
    if not args.flavour:
        args.flavour = user_setting("theme.flavour", "mocha")
    if not args.accent:
        args.accent = user_setting("theme.accent", "mauve")

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
        apply_cursor(ctx)
        reload_apps(changed_groups)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
