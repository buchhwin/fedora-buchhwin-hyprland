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
curl -fsSL https://buchhwin.github.io/fedora-buchhwin-hyprland/install | bash
```

### Or read it first — and you should

```bash
curl -fsSLO https://raw.githubusercontent.com/buchhwin/fedora-buchhwin-hyprland/main/bootstrap.sh
less bootstrap.sh      # read it
bash bootstrap.sh      # then run it, if you are happy
```

Three separate commands on purpose. `less file && bash file` looks like a
confirmation step and is not one: `less` exits 0 even when you quit with `q`,
so the script would run regardless of what you thought of it.

Both routes install exactly the same thing. The difference is whether you ever
see what you are running. Piping straight to a shell has a concrete failure
mode beyond trust: **bash executes while the download is still arriving**, so a
connection that drops halfway leaves a truncated script running — and a
truncated line can mean something very different from the whole one.

`bootstrap.sh` is deliberately 30 lines so that reading it is a minute, not an
afternoon. It checks you are on Fedora and not root, installs git if missing,
clones the repository, and hands over to `install.sh` with your arguments.

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
| **Settings** | a GTK4 app — keys, borders, theme, wallpaper, autostart |

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
- [CREDITS.md](docs/CREDITS.md) — upstream projects and licences

Deutsch: [docs/de/](docs/de/)

## Notes worth knowing before you start

- **Hyprland's config is Lua now.** Since 0.55 hyprlang is deprecated. Almost
  every dotfile collection you will find is still the old format and will not
  load. That is why this one is written from scratch rather than forked.
- **Hyprland is orphaned in Fedora** — the last official build is 0.45.2 on
  F42, and it is absent from F43 and F44. The packages come from the
  `solopasha/hyprland` COPR, which is the only maintained source for the
  current release.
- **`hyprctl keyword` does not work with a Lua config.** Runtime changes go
  through `hyprctl eval` or a plain reload; the settings GUI does the latter.
- **No Snaps.** Native packages first, Flatpak where Fedora has none.

## Licence

MIT — see [LICENSE](LICENSE). Catppuccin, Hyprland, Waybar, rofi and everything
else keep their own licences; see [docs/CREDITS.md](docs/CREDITS.md).
