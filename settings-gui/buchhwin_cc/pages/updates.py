"""Settings page: updates.

Three things can be out of date and each has its own mechanism: system packages
(dnf), the sandboxed applications (flatpak), and this project itself (git). The
page checks all three and can start each one.

Checking is unprivileged and safe, so it happens by itself when the page opens.
Installing is not: it needs root for packages and a polkit prompt for system
flatpaks, and it takes minutes. So installing opens a TERMINAL rather than
running silently — you can see the progress, answer the password prompt, and
read what went wrong. That is the same choice the rclone setup already makes.
"""

from __future__ import annotations

import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk

from ..helpers import REPO, group, page

# dnf's exit codes: 0 = nothing to do, 100 = updates available, 1 = error.
# Treating 100 as failure is the classic way to build an update page that
# always claims something is broken.
DNF_UPDATES_AVAILABLE = 100


def _run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return -1, ""
    return proc.returncode, proc.stdout


def check_packages() -> tuple[int, str]:
    """(count, detail). Count -1 means the check itself failed."""
    code, out = _run(["dnf5", "check-upgrade", "--refresh"])
    if code == -1:
        code, out = _run(["dnf", "check-update", "--refresh"])
    if code == 0:
        return 0, ""
    if code != DNF_UPDATES_AVAILABLE:
        return -1, ""
    # Package lines look like "name.arch  version  repo"; headers and blank
    # lines do not have three fields.
    names = [line.split()[0] for line in out.splitlines()
             if line.strip() and not line.startswith(" ") and len(line.split()) >= 3]
    return len(names), ", ".join(names[:6])


def check_flatpaks() -> tuple[int, str]:
    """Updates on flathub.

    Named remote on purpose. Asking every remote pulls in Fedora's OCI one,
    which needs a polkit authorisation to build its summary — measured:
    "Flatpak system operation GenerateOciSummary not allowed for user". Inside
    the session that would pop a password prompt just because somebody opened
    this page, which is not a thing a settings page may do. Everything the
    installer installs comes from flathub (lib/40-apps.sh).
    """
    code, out = _run(["flatpak", "remote-ls", "flathub", "--updates",
                      "--columns=application"], timeout=150)
    if code != 0:
        return -1, ""
    apps = [line.strip() for line in out.splitlines()
            if line.strip() and not line.startswith("error")]
    return len(apps), ", ".join(apps[:6])


def check_project() -> tuple[int, str]:
    """Commits waiting on the remote, and the newest subject lines."""
    if _run(["git", "-C", str(REPO), "fetch", "--quiet"], timeout=60)[0] != 0:
        return -1, ""
    code, out = _run(["git", "-C", str(REPO), "rev-list", "--count", "HEAD..@{u}"],
                     timeout=20)
    if code != 0 or not out.strip().isdigit():
        return -1, ""
    count = int(out.strip())
    if count == 0:
        return 0, ""
    _, log = _run(["git", "-C", str(REPO), "log", "--oneline", "--no-decorate",
                   "-3", "HEAD..@{u}"], timeout=20)
    return count, " · ".join(line.split(" ", 1)[-1] for line in log.splitlines())


def build(win):
    p = page(_("Updates"), "software-update-available-symbolic")

    g = group(p, _("Available updates"),
              _("Checked when this page opens. Installing opens a terminal, so "
                "you can see the progress and answer the password prompt."))

    win._update_rows = {}
    for key, title in (("packages", _("System packages")),
                       ("flatpaks", _("Applications (Flatpak)")),
                       ("project", _("Buchhwin desktop"))):
        row = Adw.ActionRow(title=title, subtitle=_("Checking…"))
        row.set_subtitle_lines(0)
        button = Gtk.Button(label=_("Install"), valign=Gtk.Align.CENTER)
        button.set_sensitive(False)
        button.connect("clicked", lambda _b, k=key: _install(win, k))
        row.add_suffix(button)
        g.add(row)
        win._update_rows[key] = (row, button)

    refresh = Adw.ActionRow(
        title=_("Check again"),
        subtitle=_("Reads package metadata and fetches from the git remote. "
                   "Changes nothing."))
    again = Gtk.Button(label=_("Check"), valign=Gtk.Align.CENTER)
    again.connect("clicked", lambda _b: _check(win))
    refresh.add_suffix(again)
    g.add(refresh)

    win.add_page(p, "updates", _("Updates"),
                 "software-update-available-symbolic")
    _check(win)


def _check(win) -> None:
    """Check all three in one background thread.

    Off the main thread without exception: `dnf check-upgrade --refresh` can
    take a minute on a cold cache, and a settings window frozen for a minute
    reads as a crash.
    """
    for row, button in win._update_rows.values():
        row.set_subtitle(_("Checking…"))
        button.set_sensitive(False)

    def work() -> None:
        results = {
            "packages": check_packages(),
            "flatpaks": check_flatpaks(),
            "project": check_project(),
        }
        GLib.idle_add(_show, win, results)

    threading.Thread(target=work, daemon=True).start()


def _show(win, results: dict) -> bool:
    for key, (count, detail) in results.items():
        row, button = win._update_rows[key]
        if count < 0:
            row.set_subtitle(_("Could not check"))
            button.set_sensitive(False)
        elif count == 0:
            row.set_subtitle(_("Up to date"))
            button.set_sensitive(False)
        else:
            text = _("{n} available").format(n=count)
            row.set_subtitle(f"{text} — {detail}" if detail else text)
            button.set_sensitive(True)
    return False


def _install(win, key: str) -> None:
    """Open a terminal and run the update in it."""
    terminal = (win.s.get("programs.terminal", "kitty") or "kitty").split()[0]
    commands = {
        # bhctl is called by absolute path: ~/.local/bin is not on the PATH of
        # every context this window might be started from.
        "project": [str(REPO / "bin" / "bhctl"), "update"],
        "packages": ["sudo", "dnf5", "upgrade"],
        "flatpaks": ["flatpak", "update"],
    }
    cmd = commands.get(key)
    if cmd is None:
        return
    try:
        subprocess.Popen([terminal, "-e", *cmd], start_new_session=True)
    except OSError as exc:
        win.toast(_("Could not open a terminal: {}").format(exc))
        return
    win.toast(_("Running in a terminal — check again when it finishes"))
