"""The settings window: the sidebar, the Apply button, and shared helpers.

The pages themselves live in buchhwin_cc/pages/, one module each. They are
listed here in the order they appear, which is the only place that order is
written down.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .pages import (about, accounts, apps, autostart, defaults, displays,  # noqa: E402
                    drives, input as input_page, keys, look, network, power,
                    sound, theme, updates, wallpaper, welcome)
from .helpers import REPO, STATE  # noqa: E402
# S is the settings.lua reader/writer, on sys.path courtesy of store.py. The
# drives page reloads the file after drives.py has rewritten it, so it needs
# the module itself and not the Settings wrapper's cached copy.
from .store import S, Settings  # noqa: E402

# The order of the sidebar. Look first because it is what people open the
# window for; About last because nobody opens it for that.
# Welcome first on a fresh install and last afterwards: it is where a new
# user should land, and where an old one should not have to scroll past it.
PAGES = ([welcome] if not welcome.seen() else []) + [
    look, theme, keys, defaults, wallpaper, drives, accounts, input_page,
    sound, network, displays, apps, power, autostart, updates,
] + ([] if not welcome.seen() else [welcome]) + [about]


class Window(Adw.ApplicationWindow):

    def __init__(self, app, settings: Settings):
        super().__init__(application=app, default_width=1000, default_height=720)
        self.s = settings
        self.set_title(_("Settings"))
        self._page_titles: dict[str, str] = {}
        self._index: list[dict] = []

        self.toasts = Adw.ToastOverlay()
        self.set_content(self.toasts)

        # The page list is down the side, not across the top. With fifteen
        # pages a header row runs out of width and truncates every title to an
        # ellipsis — which is what it was doing. A sidebar shows all of them,
        # in full, and has room for more.
        self.stack = Adw.ViewStack()

        sidebar_view = Adw.ToolbarView()
        sidebar_header = Adw.HeaderBar()
        sidebar_header.set_title_widget(Adw.WindowTitle(title=_("Settings")))
        sidebar_view.add_top_bar(sidebar_header)

        # Search across every page. Sixteen pages is past the point where you
        # can remember which one holds "blur strength", and hunting for a
        # setting is the thing people actually do in a settings window.
        self.search = Gtk.SearchEntry(placeholder_text=_("Search settings"))
        self.search.set_margin_start(6)
        self.search.set_margin_end(6)
        self.search.set_margin_bottom(6)
        self.search.connect("search-changed", self._on_search)
        self.search.connect("stop-search", lambda _e: self.search.set_text(""))
        sidebar_view.add_top_bar(self.search)

        # A hand-built list rather than Gtk.StackSidebar: that widget only
        # takes a Gtk.Stack, and Adw.ViewStack is not one — passing it produces
        # "invalid (NULL) pointer instance" and the window never appears.
        # Building it here also means the sidebar can show the page icons,
        # which StackSidebar cannot.
        self.sidebar = Gtk.ListBox()
        self.sidebar.add_css_class("navigation-sidebar")
        self.sidebar.set_vexpand(True)
        self.sidebar.connect("row-selected", self._on_page_selected)

        # The results list replaces the page list while searching. Two lists
        # rather than one that changes meaning: the page list keeps its
        # selection, so clearing the search puts you back where you were.
        self.results = Gtk.ListBox()
        self.results.add_css_class("navigation-sidebar")
        self.results.set_vexpand(True)
        self.results.connect("row-activated", self._on_result_activated)

        self._sidebar_stack = Gtk.Stack()
        for child, name in ((self.sidebar, "pages"), (self.results, "results")):
            scroller = Gtk.ScrolledWindow()
            scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            scroller.set_child(child)
            self._sidebar_stack.add_named(scroller, name)
        sidebar_view.set_content(self._sidebar_stack)

        content_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        # Its own title widget, or libadwaita falls back to the NavigationPage
        # title — which was also "Settings", so the word stood twice side by
        # side and neither half told you which page you were on.
        self.content_title = Adw.WindowTitle(title=_("Settings"))
        header.set_title_widget(self.content_title)
        apply_btn = Gtk.Button(label=_("Apply"))
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self.on_apply)
        header.pack_end(apply_btn)
        content_view.add_top_bar(header)
        content_view.set_content(self.stack)

        split = Adw.NavigationSplitView(
            sidebar=Adw.NavigationPage(child=sidebar_view, title=_("Settings")),
            content=Adw.NavigationPage(child=content_view, title=_("Settings")),
        )
        # Collapse on a narrow window so the app stays usable on a small screen
        # instead of showing a sidebar and a sliver of content.
        breakpoint_ = Adw.Breakpoint.new(
            Adw.BreakpointCondition.parse("max-width: 700sp"))
        breakpoint_.add_setter(split, "collapsed", True)
        self.add_breakpoint(breakpoint_)
        self.toasts.set_child(split)

        # One line per page would mean touching this file for every new one.
        # The list at the top of the module is the single place the order is
        # written down.
        for module in PAGES:
            module.build(self)

        # Ctrl+F, and plain typing, land in the search box.
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key)
        self.add_controller(controller)

    # -- helpers -------------------------------------------------------------

    def add_page(self, widget, name, title, icon):
        self.stack.add_titled_with_icon(widget, name, title, icon)

        row = Gtk.ListBoxRow()
        row.set_name(name)
        # Remembered so the content header can name the page that is showing.
        self._page_titles[name] = title
        self._index_page(widget, name, title)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.append(Gtk.Image.new_from_icon_name(icon))
        box.append(Gtk.Label(label=title, xalign=0))
        row.set_child(box)
        self.sidebar.append(row)

        # The first page added is the one shown, so the sidebar and the content
        # agree from the start rather than after the first click.
        if self.sidebar.get_row_at_index(1) is None:
            self.sidebar.select_row(row)

    # -- search --------------------------------------------------------------

    def _index_page(self, widget, name: str, title: str) -> None:
        """Record every row on a page so the search can find it.

        Walks the finished widget tree instead of asking the page modules to
        register their rows. Sixteen modules would each need the same three
        lines, and every future page would need them too — and the one that
        forgot would simply be unfindable, with nothing to show that it was.
        """
        def walk(widget):
            child = widget.get_first_child()
            while child is not None:
                if isinstance(child, Adw.PreferencesRow):
                    row_title = child.get_title() or ""
                    subtitle = ""
                    if hasattr(child, "get_subtitle"):
                        subtitle = child.get_subtitle() or ""
                    if row_title:
                        self._index.append({
                            "page": name, "page_title": title,
                            "title": row_title, "subtitle": subtitle,
                            "row": child,
                        })
                walk(child)
                child = child.get_next_sibling()
        walk(widget)

    def _on_key(self, _c, keyval, _code, state):
        ctrl = state & Gdk.ModifierType.CONTROL_MASK
        if ctrl and keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self.search.grab_focus()
            return True
        return False

    def _on_search(self, entry) -> None:
        needle = entry.get_text().strip().lower()
        if not needle:
            self._sidebar_stack.set_visible_child_name("pages")
            return

        while (row := self.results.get_row_at_index(0)) is not None:
            self.results.remove(row)

        matches = [e for e in self._index
                   if needle in e["title"].lower()
                   or needle in e["subtitle"].lower()
                   or needle in e["page_title"].lower()][:40]

        for entry_ in matches:
            row = Adw.ActionRow(title=entry_["title"],
                                subtitle=entry_["page_title"],
                                activatable=True)
            row._target = entry_
            self.results.append(row)

        if not matches:
            self.results.append(Adw.ActionRow(title=_("Nothing found"),
                                              subtitle=needle))
        self._sidebar_stack.set_visible_child_name("results")

    def _on_result_activated(self, _listbox, row) -> None:
        target = getattr(row, "_target", None)
        if target is None:
            return
        i = 0
        while (page_row := self.sidebar.get_row_at_index(i)) is not None:
            if page_row.get_name() == target["page"]:
                self.sidebar.select_row(page_row)
                break
            i += 1
        # grab_focus scrolls the row into view, which is the whole point of
        # jumping to it — landing on the right page but at the top would leave
        # you hunting again.
        GLib.idle_add(target["row"].grab_focus)

    def _on_page_selected(self, _listbox, row):
        if row is None:
            return
        name = row.get_name()
        self.stack.set_visible_child_name(name)
        self.content_title.set_title(self._page_titles.get(name, _("Settings")))

    def toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))

    def on_apply(self, btn=None):
        if not self.s.dirty:
            self.toast(_("Nothing to apply"))
            return

        # Off the main thread: apply() runs six subprocesses and takes a second
        # or two. Doing that inline freezes the window mid-click, which reads
        # as a crash rather than as work.
        if btn is not None:
            btn.set_sensitive(False)
            btn.set_label(_("Applying…"))

        def done(failed: list[str]) -> bool:
            if btn is not None:
                btn.set_sensitive(True)
                btn.set_label(_("Apply"))
            if failed:
                # Name what broke. "Applied" over a failed step is worse than
                # no message at all: it sends you looking in the wrong place.
                self.toast(_("Applied, but failed: {}").format(", ".join(failed)))
                for line in failed:
                    print(f"apply: {line}", file=sys.stderr)
            else:
                self.toast(_("Applied"))
            return False

        def work() -> None:
            try:
                failed = self.s.apply()
            except Exception as exc:                      # noqa: BLE001
                failed = [str(exc)]
            GLib.idle_add(done, failed)

        threading.Thread(target=work, daemon=True).start()

    # -- pages ---------------------------------------------------------------

    def _launch_row(self, g, title, subtitle, cmd):
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        button = Gtk.Button(label=_("Open"), valign=Gtk.Align.CENTER)
        button.connect("clicked", lambda _b: self._spawn(cmd))
        row.add_suffix(button)
        g.add(row)
        return row

    def _spawn(self, cmd):
        try:
            Gio.Subprocess.new(cmd, Gio.SubprocessFlags.NONE)
        except GLib.Error as exc:
            self.toast(_("Could not start %s") % cmd[0])
            print(exc, file=sys.stderr)

    def _rebuild_autostart(self):
        while (child := self.auto_group.get_first_child()) is not None:
            if isinstance(child, Adw.PreferencesRow):
                self.auto_group.remove(child)
            else:
                break
        for index, cmd in enumerate(self.s.get("autostart", []) or []):
            row = Adw.ActionRow(title=cmd)
            btn = Gtk.Button(icon_name="user-trash-symbolic",
                             valign=Gtk.Align.CENTER)
            btn.add_css_class("flat")
            btn.add_css_class("destructive-action")
            btn.connect("clicked", lambda _b, i=index: self._remove_autostart(i))
            row.add_suffix(btn)
            self.auto_group.add(row)

        add = Adw.EntryRow(title=_("Add a command"))
        add.connect("entry-activated", self._add_autostart)
        self.auto_group.add(add)

    def _add_autostart(self, entry):
        cmd = entry.get_text().strip()
        if not cmd:
            return
        items = list(self.s.get("autostart", []) or [])
        items.append(cmd)
        self.s.set("autostart", items)
        entry.set_text("")
        self._rebuild_autostart()

    def _remove_autostart(self, index: int):
        items = list(self.s.get("autostart", []) or [])
        if 0 <= index < len(items):
            items.pop(index)
            self.s.set("autostart", items)
            self._rebuild_autostart()


    # -- default applications -------------------------------------------------

    def _set_default(self, key: str, command: str | None):
        if command:
            self.s.set(key, command)

    def _apply_mime(self, _btn):
        """Point the common MIME types at the chosen programs."""
        pairs = [
            (self.s.get("programs.browser"), ["x-scheme-handler/http",
                                              "x-scheme-handler/https", "text/html"]),
            (self.s.get("programs.file_manager"), ["inode/directory"]),
            (self.s.get("programs.image_viewer"), ["image/png", "image/jpeg", "image/webp"]),
            (self.s.get("programs.mail"), ["x-scheme-handler/mailto"]),
        ]
        applied = 0
        for command, types in pairs:
            if not command:
                continue
            binary = command.split()[0]
            desktop = self._desktop_for(binary)
            if not desktop:
                continue
            for mime in types:
                subprocess.run(["xdg-mime", "default", desktop, mime], check=False,
                               capture_output=True)
                applied += 1
        self.toast(_("{} file associations set").format(applied))

    @staticmethod

    def _desktop_for(binary: str) -> str | None:
        for base in ("/usr/share/applications", "/usr/local/share/applications",
                     str(Path(os.environ.get("XDG_DATA_HOME",
                                             Path.home() / ".local/share")) / "applications")):
            d = Path(base)
            if not d.is_dir():
                continue
            for entry in d.glob("*.desktop"):
                try:
                    if f"Exec={binary}" in entry.read_text(errors="replace"):
                        return entry.name
                except OSError:
                    continue
        return None

    # -- drives ---------------------------------------------------------------

    def _drives(self) -> list[dict]:
        return list(self.s.get("drives", []) or [])

    def _rebuild_drives(self):
        for grp in (self.cloud_group, self.net_group):
            while (child := grp.get_first_child()) is not None:
                if isinstance(child, Adw.PreferencesRow):
                    grp.remove(child)
                else:
                    break

        for d in self._drives():
            target = grp = None
            if d.get("kind") == "cloud":
                grp = self.cloud_group
                target = f"~/Drives/{d['name']}"
            else:
                grp = self.net_group
                user = f"{d.get('user')}@" if d.get("user") else ""
                target = f"{d.get('type', 'smb')}://{user}{d.get('host', '')}/{d.get('share', '')}"
            row = Adw.ActionRow(title=d["name"], subtitle=target)

            state = Gtk.Label(label="…")
            state.add_css_class("dim-label")
            row.add_suffix(state)
            self._refresh_drive_state(d["name"], state)

            connect = Gtk.Button(icon_name="view-refresh-symbolic",
                                 valign=Gtk.Align.CENTER, tooltip_text=_("Connect"))
            connect.add_css_class("flat")
            connect.connect("clicked", lambda _b, n=d["name"], l=state:
                            self._drive_cmd("mount", n, l))
            row.add_suffix(connect)

            remove = Gtk.Button(icon_name="user-trash-symbolic",
                                valign=Gtk.Align.CENTER, tooltip_text=_("Remove"))
            remove.add_css_class("flat")
            remove.add_css_class("destructive-action")
            remove.connect("clicked", lambda _b, n=d["name"]: self._drive_remove(n))
            row.add_suffix(remove)
            grp.add(row)

        add_cloud = Adw.ActionRow(
            title=_("Add cloud storage"),
            subtitle=_("Your browser opens for the sign-in"))
        for label, provider in ((_("Google Drive"), "drive"), (_("OneDrive"), "onedrive"),
                                (_("Dropbox"), "dropbox"), (_("WebDAV"), "webdav")):
            b = Gtk.Button(label=label, valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda _b, pr=provider: self._drive_add_cloud(pr))
            add_cloud.add_suffix(b)
        self.cloud_group.add(add_cloud)

        add_net = Adw.ActionRow(title=_("Add a network drive"))
        b = Gtk.Button(label=_("Add…"), valign=Gtk.Align.CENTER)
        b.add_css_class("suggested-action")
        b.connect("clicked", lambda _b: self._drive_add_network_dialog())
        add_net.add_suffix(b)
        self.net_group.add(add_net)

    def _drives_script(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(REPO / "scripts" / "drives.py"), *args],
                              capture_output=True, text=True, check=False)

    def _refresh_drive_state(self, name: str, label: Gtk.Label):
        out = self._drives_script("list").stdout
        for line in out.splitlines():
            if line.startswith(name + " ") or line.split()[:1] == [name]:
                parts = line.split()
                if len(parts) >= 3:
                    label.set_label(parts[2])
                return
        label.set_label("—")

    def _drive_cmd(self, cmd: str, name: str, label: Gtk.Label | None = None):
        proc = self._drives_script(cmd, name)
        if proc.returncode == 0:
            self.toast(_("{}: {}").format(name, cmd))
        else:
            self.toast(proc.stderr.strip().splitlines()[-1] if proc.stderr else _("failed"))
        if label:
            self._refresh_drive_state(name, label)

    def _drive_remove(self, name: str):
        dialog = Adw.MessageDialog(
            transient_for=self, modal=True,
            heading=_("Remove {}?").format(name),
            body=_("The drive is disconnected and its entry disappears from the "
                   "file manager. Nothing in the cloud or on the server is deleted."))
        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("remove", _("Remove"))
        dialog.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)

        def done(_d, response):
            if response == "remove":
                self._drives_script("remove", name)
                self.s.data = S.read()
                self._rebuild_drives()
        dialog.connect("response", done)
        dialog.present()

    def _drive_add_cloud(self, provider: str):
        self.toast(_("Sign in in the browser window that opens"))
        # rclone drives the OAuth flow itself and opens the browser; running it
        # in a terminal keeps its prompts visible instead of swallowing them.
        term = self.s.get("programs.terminal", "kitty").split()[0]
        subprocess.Popen([term, "-e", sys.executable,
                          str(REPO / "scripts" / "drives.py"),
                          "add-cloud", "--provider", provider])

    def _drive_add_network_dialog(self):
        dialog = Adw.MessageDialog(transient_for=self, modal=True,
                                   heading=_("Add a network drive"))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        kind = Adw.ComboRow(title=_("Type"),
                            model=Gtk.StringList.new(["smb", "nfs", "dav", "sftp"]))
        host = Adw.EntryRow(title=_("Server"))
        share = Adw.EntryRow(title=_("Share"))
        user = Adw.EntryRow(title=_("User"))
        password = Adw.PasswordEntryRow(title=_("Password"))
        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listbox.add_css_class("boxed-list")
        for w in (kind, host, share, user, password):
            listbox.append(w)
        box.append(listbox)
        dialog.set_extra_child(box)

        dialog.add_response("cancel", _("Cancel"))
        dialog.add_response("add", _("Add"))
        dialog.set_response_appearance("add", Adw.ResponseAppearance.SUGGESTED)

        def done(_d, response):
            if response != "add" or not host.get_text().strip():
                return
            args = ["add-network",
                    "--type", ["smb", "nfs", "dav", "sftp"][kind.get_selected()],
                    "--host", host.get_text().strip(),
                    "--share", share.get_text().strip(),
                    "--user", user.get_text().strip()]
            proc = subprocess.run(
                [sys.executable, str(REPO / "scripts" / "drives.py"), *args],
                input=password.get_text(), text=True, capture_output=True, check=False)
            self.s.data = S.read()
            self._rebuild_drives()
            self.toast(_("Added") if proc.returncode == 0
                       else (proc.stderr.strip().splitlines()[-1] if proc.stderr
                             else _("failed")))
        dialog.connect("response", done)
        dialog.present()

    # -- accounts -------------------------------------------------------------

    def _set_lang(self, value: str):
        STATE.mkdir(parents=True, exist_ok=True)
        (STATE / "lang").write_text(value + "\n")
        self.toast(_("Takes effect the next time this window is opened"))
