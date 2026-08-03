"""The settings file, and what it takes to make a change visible."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import settings as S

from .helpers import run


class Settings:
    """The settings file, loaded once and written on demand."""

    def __init__(self) -> None:
        self.data = S.read()
        self._dirty = False

    def get(self, dotted: str, default=None):
        try:
            return S.get_path(self.data, dotted)
        except (KeyError, IndexError, TypeError):
            return default

    def set(self, dotted: str, value) -> None:
        if self.get(dotted) == value:
            return
        S.set_path(self.data, dotted, value)
        self._dirty = True

    @property
    def dirty(self) -> bool:
        return self._dirty

    def save(self) -> None:
        if not self._dirty:
            return
        S.write(self.data)
        self._dirty = False

    def apply(self) -> list[str]:
        """Write the file, then run everything that turns it into a desktop.

        This used to write settings.lua, reload Hyprland and restart the bar —
        and nothing else. That made two settings simply not work: the pointer
        theme reaches GTK and gsettings only through theme/apply-theme.py, and
        the dock exists only once scripts/dock.py has generated its config and
        unit. Both ran in the installer and nowhere else, so changing them in
        this window did exactly nothing.

        The idle step is the same story, found later and worse: the whole Power
        page wrote idle.* into settings.lua and NOTHING read it, because the
        generator its own config file named had never been written. Dim, lock,
        screen-off and suspend were decoration.

        `systemctl --user reload`, NOT reload-or-restart. The bar's unit has an
        ExecReload (SIGUSR2), and a restart would kill everything in the unit's
        cgroup — which includes this very window when it was opened from the
        bar's own settings button. Apply was shooting itself.

        Returns the list of steps that failed, so the window can say so instead
        of reporting "Applied" over a generator that died in a traceback.
        """
        self.save()
        steps = (
            ("theme",     (sys.executable, str(REPO / "theme" / "apply-theme.py"))),
            ("dock",      (sys.executable, str(REPO / "scripts" / "dock.py"), "sync")),
            ("wallpaper", (str(REPO / "scripts" / "wallpaper.sh"), "sync-timer")),
            ("drives",    (sys.executable, str(REPO / "scripts" / "drives.py"), "sync")),
            ("idle",      (str(REPO / "scripts" / "idle-config.sh"),)),
            ("hyprland",  ("hyprctl", "reload")),
            ("bar",       ("systemctl", "--user", "reload", "buchhwin-bar.service")),
        )
        failed = []
        for name, cmd in steps:
            ok, why = run(*cmd)
            if not ok:
                failed.append(f"{name}: {why}")
        return failed
