"""Settings page: sound.

Extracted from the single 1392-line file the settings app used to be. Each page
is one module exporting build(win); `win` is the Window, which still owns the
shared helpers (toast, add_page, _launch_row, _spawn) so a page can use them
without importing the window back and creating a cycle.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from ..helpers import (ACCENTS, FLAVOURS, REPO, STATE, combo_row,  # noqa: F401
                       cursor_themes, group, page, pinnable_apps, run,
                       run_lines, slider_row, spin_row, switch_row)
from ..keycapture import KeyCaptureDialog  # noqa: E402


def build(win):
    """Live device state, not stored preferences.

    Nothing on this page goes into settings.lua: which speaker is the
    default is a property of the machine right now, and writing it to a
    file that syncs to another computer would be actively wrong.
    """
    p = page(_("Sound"), "audio-volume-high-symbolic")

    g = group(p, _("Output"), _("Where sound comes out."))
    sinks = _audio_devices(win, "sinks", "get-default-sink")
    if sinks:
        for name, label, is_default in sinks:
            row = Adw.ActionRow(title=label,
                                subtitle=_("Default") if is_default else "")
            button = Gtk.Button(label=_("Use this"), valign=Gtk.Align.CENTER)
            button.set_sensitive(not is_default)
            button.connect("clicked", lambda *a, _f=_on_default_sink: _f(win, *a[1:]), name)
            row.add_suffix(button)
            g.add(row)
    else:
        g.add(Adw.ActionRow(title=_("No output devices found")))

    g = group(p, _("Input"), _("Microphones."))
    sources = _audio_devices(win, "sources", "get-default-source")
    real = [s for s in sources if ".monitor" not in s[0]]
    if real:
        for name, label, is_default in real:
            row = Adw.ActionRow(title=label,
                                subtitle=_("Default") if is_default else "")
            button = Gtk.Button(label=_("Use this"), valign=Gtk.Align.CENTER)
            button.set_sensitive(not is_default)
            button.connect("clicked", lambda *a, _f=_on_default_source: _f(win, *a[1:]), name)
            row.add_suffix(button)
            g.add(row)
    else:
        g.add(Adw.ActionRow(title=_("No microphones found")))

    g = group(p, _("More"))
    win._launch_row(g, _("Per-application volume"),
                     _("Levels for each running program"),
                     ["pavucontrol"])

    win.add_page(p, "sound", _("Sound"), "audio-volume-high-symbolic")


def _audio_devices(win, kind: str, default_cmd: str):
    import json as _json
    raw = "\n".join(run_lines(["pactl", "-f", "json", "list", kind], timeout=6))
    try:
        devices = _json.loads(raw) if raw.strip() else []
    except ValueError:
        devices = []
    default = "".join(run_lines(["pactl", default_cmd], timeout=6))
    out = []
    for d in devices:
        name = d.get("name", "")
        label = (d.get("description")
                 or d.get("properties", {}).get("device.description")
                 or name)
        out.append((name, label, name == default))
    return out


def _on_default_sink(win, _b, name):
    subprocess.run(["pactl", "set-default-sink", name], check=False)
    win.toast(_("Output device changed"))


def _on_default_source(win, _b, name):
    subprocess.run(["pactl", "set-default-source", name], check=False)
    win.toast(_("Microphone changed"))

# -- Network -------------------------------------------------------------
