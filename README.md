<div align="center">

# fedora-buchhwin-hyprland

**A Catppuccin Hyprland desktop for Fedora, in one command.**

Built to be looked at *and* worked in — a sysadmin's daily driver that happens
to be worth posting.

[![Fedora 44](https://img.shields.io/badge/Fedora-44-51A2DA?style=for-the-badge&logo=fedora&logoColor=white&labelColor=313244)](https://fedoraproject.org/)
[![Hyprland 0.56](https://img.shields.io/badge/Hyprland-0.56-58E1FF?style=for-the-badge&labelColor=313244)](https://hypr.land/)
[![Catppuccin](https://img.shields.io/badge/Catppuccin-Mocha-CBA6F7?style=for-the-badge&labelColor=313244)](https://catppuccin.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-A6E3A1?style=for-the-badge&labelColor=313244)](LICENSE)

</div>

---

```bash
curl -fsSLO https://buchhwin.github.io/fedora-buchhwin-hyprland/bootstrap.sh && bash bootstrap.sh
```

One line, and it does **not** pipe into a shell. `-O` writes the script to a
file and `-f` makes curl fail on any HTTP error, so `bash` only ever runs a file
that arrived complete.

That distinction is not pedantry. `curl … | bash` starts executing while the
download is still arriving, so a connection that drops halfway leaves a
**truncated** script running — and a truncated line can mean something very
different from the whole one. Downloading first costs you nothing and removes
that failure mode entirely.

<details>
<summary>Read it before you run it</summary>

```bash
curl -fsSLO https://buchhwin.github.io/fedora-buchhwin-hyprland/bootstrap.sh
less bootstrap.sh      # read it
bash bootstrap.sh      # then run it
```

Three separate commands, because `less file && bash file` looks like a
confirmation step and is not one — `less` exits 0 even when you quit with `q`,
so the script would run regardless of what you thought of it.

`bootstrap.sh` is deliberately about 30 lines: it checks you are on Fedora and
not root, installs git if it is missing, clones this repository to
`~/.local/share/fedora-buchhwin-hyprland`, and hands over to `install.sh` with
whatever arguments you passed.

</details>

Arguments are passed straight through:

```bash
bash bootstrap.sh --dry-run          # print everything, change nothing
```

Start from a plain **Fedora Server** install (or any Fedora with no desktop).
The script adds everything else.

---

## What you get

| | |
|---|---|
| **Compositor** | Hyprland 0.56 — **Lua** config, the format since 0.55 |
| **Bar** | Waybar, floating island, module pills |
| **Menus** | rofi 2.0 — launcher, windows, clipboard, emoji, wallpaper, shortcuts |
| **Notifications** | SwayNC with a control centre panel |
| **Terminal** | kitty |
| **Files** | Nemo |
| **Login** | SDDM, Catppuccin greeter |
| **Lock / idle** | hyprlock + hypridle |
| **Wallpaper** | swww, with transitions |
| **Shell** | zsh + starship + atuin |
| **Settings** | a GTK4 app — keys, borders, theme, wallpaper, drives, autostart |
| **Drives** | Google Drive / OneDrive via rclone, SMB/NFS via gvfs — in the file manager sidebar like a mapped drive |
| **Calendar** | GOA + evolution-data-server → GNOME Calendar, Evolution **and** the bar |
| **Firewall** | ufw, on by default |

Everything is Catppuccin, and that is not a figure of speech: GTK3, GTK4,
Qt, SDDM, the lock screen, the power menu, notifications, the terminal, the
file manager, icons, **the cursor**, `btop` and `fastfetch` all come from the
same palette file.

## Switching the whole desktop in one command

```bash
bhctl theme latte blue      # light
bhctl theme mocha mauve     # dark
bhctl theme toggle          # back and forth
```

There is no list of themed applications to maintain. `theme/apply-theme.py`
renders every config from `theme/palettes/<flavour>.json` through a template,
then reloads whatever is running. Adding an application means adding one
template, not editing fifteen colour schemes.

## Tiling, and also not

Tiling is the default. `SUPER + SHIFT + Space` turns the current workspace
floating, where windows drag freely and snap magnetically to edges and to each
other — and the arrow keys snap them to halves, quarters and full screen the way
Windows does.

The arrow keys do double duty on purpose: **focus while tiled, snap while
floating.** Same keys, nothing to remember, and `SUPER + h/j/k/l` is always
focus. No plugin is involved — plugins have to be rebuilt for every Hyprland
release and break until someone does.

## Keyboard

`SUPER + /` shows all of them, searchable, generated from your actual config.

| | |
|---|---|
| `SUPER + Return` | Terminal |
| `SUPER + Q` | Close window |
| `SUPER + S` | Screenshot (region → annotate) |
| `SUPER + V` | Clipboard history |
| `SUPER + B` | Browser |
| `SUPER + E` | Files |
| `SUPER + Space` | Launcher |
| `SUPER + W` | Wallpaper picker |
| `SUPER + I` | Settings |
| `SUPER + L` | Lock |

Full list: [docs/KEYBINDS.md](docs/KEYBINDS.md).

## After the install

```bash
bhctl update        # pull, install what is new, re-render the theme
bhctl doctor        # check packages, links, services, fonts
bhctl keys          # searchable shortcuts
bhctl wallpaper     # thumbnail picker
bhctl backup        # save your settings
```

## Options

```bash
./install.sh --dry-run        # print everything, change nothing
./install.sh --minimal        # desktop only, no applications
./install.sh --no-flatpak     # nothing from Flathub
./install.sh --gpu nvidia     # amd | nvidia | intel | none | auto
./install.sh --flavour latte --accent blue
./install.sh --lang de        # installer language; English is the default
./install.sh --with k8s       # optional extras: k8s iac db analysis virt backup
./install.sh --no-tweaks      # leave system settings (journal, mDNS, oomd) alone
./install.sh --no-firewall    # do not install or enable ufw
```

## Configuration

```
~/.config/hypr/
├── hyprland.lua       symlink → repo   structure
├── binds.lua          symlink → repo   key bindings
├── rules.lua          symlink → repo   window rules
├── settings.lua       yours            everything the GUI owns
└── theme.lua          generated        colours
```

`settings.lua` is plain data. The settings GUI reads and rewrites it, so it
never has to parse hand-written Lua — and your hand edits survive, because the
file is read, changed and written back whole. `bhctl update` never touches it.

## Documentation

- [KEYBINDS.md](docs/KEYBINDS.md) — every shortcut
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — how the pieces fit, and why
- [MICROSOFT.md](docs/MICROSOFT.md) — Teams, Outlook and Exchange on Linux
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) — when something is wrong
- [DRIVES.md](docs/DRIVES.md) — cloud and network drives, and why Google Drive
  no longer comes from GNOME Online Accounts
- [SECURITY.md](docs/SECURITY.md) — the firewall choice, secrets, and every
  file outside `$HOME` this installer touches
- [CREDITS.md](docs/CREDITS.md) — upstream projects and licences

Deutsch: [docs/de/](docs/de/)

## Notes worth knowing before you start

- **Hyprland's config is Lua now.** Since 0.55 hyprlang is deprecated. Almost
  every dotfile collection you will find is still the old format and will not
  load. That is why this one is written from scratch rather than forked.
- **Hyprland is orphaned in Fedora** — the last official build is 0.45.2 on
  F42, and it is absent from F43 and F44. Packages come from the
  **`sachesi/hyprland`** COPR (0.56.1 for F44). Not `solopasha/hyprland`, the
  better-known one: its newest F44 build is 0.51.1 — *before* the Lua switch,
  so these configs would not load — and it does not install anyway, because its
  aquamarine wants `libdisplay-info.so.2` while F44 ships `.so.3`. solopasha
  stays enabled at a lower priority for `uwsm`, `swww` and `satty`, which
  sachesi does not carry.
- **`hyprctl keyword` does not work with a Lua config.** Runtime changes go
  through `hyprctl eval` or a plain reload; the settings GUI does the latter.
- **No Snaps.** Native packages first, Flatpak where Fedora has none.

## Licence

MIT — see [LICENSE](LICENSE). Catppuccin, Hyprland, Waybar, rofi and everything
else keep their own licences; see [docs/CREDITS.md](docs/CREDITS.md).
