#!/usr/bin/env python3
"""Cloud and network drives that show up in the file manager like Windows.

    drives.py list
    drives.py add-cloud   --provider drive|onedrive|dropbox|webdav --name GoogleDrive
    drives.py add-network --type smb|nfs|dav|sftp --host nas --share data --user jan
    drives.py mount NAME | unmount NAME | remove NAME
    drives.py sync                 rebuild units and bookmarks from settings.lua
    drives.py waybar               JSON for the bar

Two kinds, two mechanisms, one appearance
-----------------------------------------
**Cloud** goes through rclone: it mounts Google Drive, OneDrive, Dropbox or a
WebDAV server at ~/Drives/<name>. rclone opens your browser for the login, so
nothing here ever sees a password.

Google Drive is NOT done through GNOME Online Accounts, and that is not a
preference: GNOME 50 removed Google Drive *file* access entirely (libgdata,
which it relied on, has been unmaintained for years and was the last thing
keeping the insecure libsoup2 alive). Calendar, contacts and mail still come
from GOA. Files come from here. See docs/DRIVES.md.

**Network** goes through gvfs — `gio mount smb://…`. No root, no fstab entry,
no cifs-utils. The password goes into the keyring via libsecret.

Both end up as a line in ~/.config/gtk-3.0/bookmarks, which is what makes them
appear permanently in Nemo's sidebar, connected or not — the thing that makes
this feel like a mapped drive in Explorer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import settings as S

HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
UNITS = CONFIG / "systemd" / "user"
BOOKMARKS = CONFIG / "gtk-3.0" / "bookmarks"
MOUNT_ROOT = HOME / "Drives"
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))

BOOKMARK_BEGIN = "# >>> buchhwin drives >>>"
BOOKMARK_END = "# <<< buchhwin drives <<<"

CLOUD_PROVIDERS = {
    "drive":    ("Google Drive", "drive"),
    "onedrive": ("OneDrive", "onedrive"),
    "dropbox":  ("Dropbox", "dropbox"),
    "webdav":   ("Nextcloud / WebDAV", "webdav"),
}
NETWORK_SCHEMES = {"smb": "smb", "nfs": "nfs", "dav": "davs", "sftp": "sftp"}


def run(*cmd: str, check: bool = False, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=check, **kw)


def safe_name(name: str) -> str:
    """A unit and directory name that cannot surprise systemd or a shell."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "-", name).strip("-")
    return cleaned or "drive"


# ---------------------------------------------------------------------------
# settings.lua
# ---------------------------------------------------------------------------
def load() -> dict:
    return S.read()


def drives_of(data: dict) -> list[dict]:
    return list(data.get("drives") or [])


def save_drives(data: dict, drives: list[dict]) -> None:
    data["drives"] = drives
    S.write(data)


# ---------------------------------------------------------------------------
# Bookmarks — the reason any of this appears in the sidebar
# ---------------------------------------------------------------------------
def write_bookmarks(drives: list[dict]) -> None:
    """Rewrite only our block. Anything the user bookmarked stays untouched."""
    BOOKMARKS.parent.mkdir(parents=True, exist_ok=True)
    existing = BOOKMARKS.read_text().splitlines() if BOOKMARKS.exists() else []

    kept, inside = [], False
    for line in existing:
        if line.strip() == BOOKMARK_BEGIN:
            inside = True
            continue
        if line.strip() == BOOKMARK_END:
            inside = False
            continue
        if not inside:
            kept.append(line)

    block = [BOOKMARK_BEGIN]
    for d in drives:
        name = d["name"]
        if d["kind"] == "cloud":
            block.append(f"file://{MOUNT_ROOT / safe_name(name)} {name}")
        else:
            block.append(f"{network_uri(d)} {name}")
    block.append(BOOKMARK_END)

    while kept and not kept[-1].strip():
        kept.pop()
    BOOKMARKS.write_text("\n".join([*kept, *block]) + "\n")


def network_uri(d: dict) -> str:
    scheme = NETWORK_SCHEMES.get(d.get("type", "smb"), "smb")
    user = f"{d['user']}@" if d.get("user") else ""
    share = d.get("share") or ""
    return f"{scheme}://{user}{d['host']}/{share}".rstrip("/")


# ---------------------------------------------------------------------------
# systemd user units
# ---------------------------------------------------------------------------
def unit_name(name: str) -> str:
    return f"buchhwin-drive-{safe_name(name)}.service"


def write_unit(d: dict) -> None:
    UNITS.mkdir(parents=True, exist_ok=True)
    name = safe_name(d["name"])
    target = MOUNT_ROOT / name

    if d["kind"] == "cloud":
        exec_start = (
            f"/usr/bin/rclone mount {name}: {target} "
            "--vfs-cache-mode writes --dir-cache-time 30s --poll-interval 15s "
            "--umask 077 --file-perms 0600 --no-check-certificate=false"
        )
        exec_stop = f"/bin/fusermount3 -uz {target}"
    else:
        uri = network_uri(d)
        exec_start = f"/usr/bin/gio mount {uri}"
        exec_stop = f"/usr/bin/gio mount -u {uri}"

    # The important part is what is NOT here: no Requires= on the network and
    # no long TimeoutStartSec. A NAS that is switched off must cost you nothing
    # at login — the unit fails quietly and keeps retrying, and the bookmark
    # stays in the sidebar either way.
    (UNITS / unit_name(d["name"])).write_text(f"""[Unit]
Description=Drive: {d['name']}
Documentation=man:rclone(1)
After=network-online.target
Wants=network-online.target
PartOf=graphical-session.target

[Service]
Type={'notify' if d['kind'] == 'cloud' else 'oneshot'}
{'RemainAfterExit=yes' if d['kind'] != 'cloud' else ''}
ExecStartPre=/bin/mkdir -p {target}
ExecStart={exec_start}
ExecStop={exec_stop}
Restart=on-failure
RestartSec=30
TimeoutStartSec=45

[Install]
WantedBy=graphical-session.target
""")


def systemctl(*args: str) -> subprocess.CompletedProcess:
    return run("systemctl", "--user", *args)


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------
def store_password(d: dict, password: str) -> bool:
    """Put the password in the keyring. gvfs looks it up by the same
    attributes, so mounting never prompts again."""
    if shutil.which("secret-tool") is None:
        return False
    proc = subprocess.run(
        ["secret-tool", "store", "--label", f"Drive: {d['name']}",
         "xdg:schema", "org.gnome.keyring.NetworkPassword",
         "protocol", NETWORK_SCHEMES.get(d.get("type", "smb"), "smb"),
         "server", d["host"], "object", d.get("share", ""),
         "user", d.get("user", "")],
        input=password, text=True, capture_output=True, check=False)
    return proc.returncode == 0


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def state_of(d: dict) -> str:
    name = safe_name(d["name"])
    if d["kind"] == "cloud":
        if (MOUNT_ROOT / name).is_mount():
            return "mounted"
    elif run("gio", "info", network_uri(d)).returncode == 0:
        return "mounted"
    unit = unit_name(d["name"])
    active = systemctl("is-active", unit).stdout.strip()
    return {"active": "mounted", "activating": "connecting"}.get(active, active or "unknown")


def cmd_list(_args) -> int:
    drives = drives_of(load())
    if not drives:
        print("no drives configured")
        return 0
    print(f"{'NAME':<20} {'KIND':<8} {'STATE':<12} TARGET")
    for d in drives:
        target = (str(MOUNT_ROOT / safe_name(d["name"]))
                  if d["kind"] == "cloud" else network_uri(d))
        print(f"{d['name']:<20} {d['kind']:<8} {state_of(d):<12} {target}")
    return 0


def cmd_add_cloud(args) -> int:
    if shutil.which("rclone") is None:
        print("rclone is not installed", file=sys.stderr)
        return 1
    provider = args.provider
    if provider not in CLOUD_PROVIDERS:
        print(f"unknown provider: {provider}", file=sys.stderr)
        return 2
    name = safe_name(args.name or CLOUD_PROVIDERS[provider][0].replace(" ", ""))

    label, backend = CLOUD_PROVIDERS[provider]
    print(f"  {label}: rclone will open your browser. Sign in there, then come back.")
    # config_is_local=false would print a URL instead of opening a browser; on a
    # desktop the browser is what you want.
    proc = subprocess.run(["rclone", "config", "create", name, backend],
                          text=True, check=False)
    if proc.returncode != 0:
        print("rclone could not set the remote up", file=sys.stderr)
        return 1

    data = load()
    drives = [d for d in drives_of(data) if d["name"] != name]
    drives.append({"kind": "cloud", "name": name, "provider": provider,
                   "automount": not args.no_automount})
    save_drives(data, drives)
    cmd_sync(None)
    cmd_mount(argparse.Namespace(name=name))
    print(f"  {name} is ready at {MOUNT_ROOT / name}")
    return 0


def cmd_add_network(args) -> int:
    name = args.name or f"{args.host.split('.')[0]}-{args.share}"
    d = {"kind": "network", "name": name, "type": args.type,
         "host": args.host, "share": args.share, "user": args.user or "",
         "automount": not args.no_automount}

    password = args.password
    if password is None and not sys.stdin.isatty():
        password = sys.stdin.read().strip() or None
    if password:
        if store_password(d, password):
            print("  password stored in the keyring")
        else:
            print("  ! could not store the password (secret-tool missing)",
                  file=sys.stderr)

    data = load()
    drives = [x for x in drives_of(data) if x["name"] != name]
    drives.append(d)
    save_drives(data, drives)
    cmd_sync(None)
    return cmd_mount(argparse.Namespace(name=name))


def find(name: str) -> dict | None:
    for d in drives_of(load()):
        if d["name"] == name or safe_name(d["name"]) == safe_name(name):
            return d
    return None


def cmd_mount(args) -> int:
    d = find(args.name)
    if not d:
        print(f"no such drive: {args.name}", file=sys.stderr)
        return 1
    MOUNT_ROOT.mkdir(parents=True, exist_ok=True)
    proc = systemctl("start", unit_name(d["name"]))
    if proc.returncode != 0:
        print(proc.stderr.strip() or "could not mount", file=sys.stderr)
        return 1
    if d["kind"] == "network":
        link_gvfs(d)
    print(f"  {d['name']}: {state_of(d)}")
    return 0


def link_gvfs(d: dict) -> None:
    """Point ~/Drives/<name> at the gvfs mount.

    gvfs mounts land under /run/user/<uid>/gvfs/ with a generated name. That
    path is unusable from a script or a terminal, so a stable symlink makes the
    drive behave like the cloud ones.
    """
    base = RUNTIME / "gvfs"
    if not base.exists():
        return
    scheme = NETWORK_SCHEMES.get(d.get("type", "smb"), "smb")
    candidates = [p for p in base.iterdir()
                  if p.name.startswith(f"{scheme}-") and d["host"] in p.name]
    if not candidates:
        return
    target = candidates[0]
    if d.get("share"):
        deeper = target / d["share"]
        if deeper.exists():
            target = deeper
    link = MOUNT_ROOT / safe_name(d["name"])
    MOUNT_ROOT.mkdir(parents=True, exist_ok=True)
    if link.is_symlink() or link.exists():
        if link.is_symlink():
            link.unlink()
        elif link.is_dir() and not any(link.iterdir()):
            link.rmdir()
        else:
            return
    link.symlink_to(target)


def cmd_unmount(args) -> int:
    d = find(args.name)
    if not d:
        return 1
    systemctl("stop", unit_name(d["name"]))
    print(f"  {d['name']}: disconnected")
    return 0


def cmd_remove(args) -> int:
    d = find(args.name)
    if not d:
        print(f"no such drive: {args.name}", file=sys.stderr)
        return 1
    systemctl("disable", "--now", unit_name(d["name"]))
    (UNITS / unit_name(d["name"])).unlink(missing_ok=True)
    if d["kind"] == "cloud" and shutil.which("rclone"):
        run("rclone", "config", "delete", safe_name(d["name"]))
    link = MOUNT_ROOT / safe_name(d["name"])
    if link.is_symlink():
        link.unlink()

    data = load()
    save_drives(data, [x for x in drives_of(data) if x["name"] != d["name"]])
    cmd_sync(None)
    print(f"  {d['name']} removed")
    return 0


def cmd_sync(_args) -> int:
    drives = drives_of(load())
    write_bookmarks(drives)
    for d in drives:
        write_unit(d)
    systemctl("daemon-reload")
    for d in drives:
        if d.get("automount", True):
            systemctl("enable", unit_name(d["name"]))
        else:
            systemctl("disable", unit_name(d["name"]))
    print(f"  {len(drives)} drive(s) synced")
    return 0


def cmd_waybar(_args) -> int:
    drives = drives_of(load())
    if not drives:
        print(json.dumps({}))          # module disappears entirely
        return 0
    states = [(d["name"], state_of(d)) for d in drives]
    mounted = sum(1 for _, s in states if s == "mounted")
    broken = [n for n, s in states if s in ("failed", "unknown")]
    cls = "error" if broken else ("" if mounted == len(states) else "partial")
    tooltip = "\n".join(f"{n}: {s}" for n, s in states)
    print(json.dumps({"text": f"󰉋 {mounted}/{len(states)}",
                      "tooltip": tooltip, "class": cls}))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("sync").set_defaults(fn=cmd_sync)
    sub.add_parser("waybar").set_defaults(fn=cmd_waybar)

    p = sub.add_parser("add-cloud")
    p.set_defaults(fn=cmd_add_cloud)
    p.add_argument("--provider", required=True, choices=sorted(CLOUD_PROVIDERS))
    p.add_argument("--name")
    p.add_argument("--no-automount", action="store_true")

    p = sub.add_parser("add-network")
    p.set_defaults(fn=cmd_add_network)
    p.add_argument("--type", default="smb", choices=sorted(NETWORK_SCHEMES))
    p.add_argument("--host", required=True)
    p.add_argument("--share", default="")
    p.add_argument("--user", default="")
    p.add_argument("--password", help="better: pipe it in on stdin")
    p.add_argument("--name")
    p.add_argument("--no-automount", action="store_true")

    for name in ("mount", "unmount", "remove"):
        p = sub.add_parser(name)
        p.add_argument("name")
        p.set_defaults(fn={"mount": cmd_mount, "unmount": cmd_unmount,
                           "remove": cmd_remove}[name])

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
