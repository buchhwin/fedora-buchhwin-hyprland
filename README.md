<div align="center">

# fedora-buchhwin-hyprland

**A themed Hyprland desktop for Fedora, in one command.**

Built to be looked at *and* worked in — a sysadmin's daily driver that happens
to be worth posting.

[![Fedora 44](https://img.shields.io/badge/Fedora-44-51A2DA?style=for-the-badge&logo=fedora&logoColor=white&labelColor=313244)](https://fedoraproject.org/)
[![Hyprland 0.55+](https://img.shields.io/badge/Hyprland-0.55%2B-58E1FF?style=for-the-badge&labelColor=313244)](https://hypr.land/)
[![9 palettes](https://img.shields.io/badge/palettes-9-CBA6F7?style=for-the-badge&labelColor=313244)](theme/palettes/)
[![License: MIT](https://img.shields.io/badge/License-MIT-A6E3A1?style=for-the-badge&labelColor=313244)](LICENSE)

</div>

---

```bash
curl -fsSLO https://raw.githubusercontent.com/buchhwin/fedora-buchhwin-hyprland/main/bootstrap.sh && bash bootstrap.sh
```

That is the whole installation. Run it on **Fedora Server**, or on any Fedora
that has no desktop yet.

No custom ISO, no kickstart file, no boot parameters: download Fedora from
[fedoraproject.org](https://fedoraproject.org/server/download), install it the
normal way, then run the line above.

It starts by asking half a dozen questions — language, keyboard layout,
timezone, computer name, colour palette — and then does not interrupt again.
Every one of them also has a flag, and `--unattended` skips the lot.

### Disk space

Measured on a finished install, not estimated: **11 GB** on `/`, of which
5 GB is Flatpaks. The installer needs some headroom on top of that for packages
it downloads and then discards, so it checks up front and **stops** rather than
running out three quarters of the way through:

| Run | Free space needed on `/` |
|---|---|
| default | **12 GB** |
| `--no-flatpak` | 8 GB |
| `--minimal` | 6 GB |

For a machine you actually intend to use, give it 30 GB or more — 60 GB if you
keep documents on it, and considerably more if games are going on the same
disk. Note that Fedora Server's default partitioning caps `/` and gives the
rest to `/home`, so "the disk is big enough" and "`/` is big enough" are not
the same statement.

<details>
<summary>Options, and why this is not <code>curl | bash</code></summary>

Arguments are passed straight through:

```bash
bash bootstrap.sh --dry-run        # print everything, change nothing
bash bootstrap.sh --minimal        # desktop only, no applications
bash bootstrap.sh --with k8s       # optional extras
```

To read it first — three separate commands, because `less file && bash file`
looks like a confirmation step and is not one (`less` exits 0 even when you
quit with `q`):

```bash
curl -fsSLO https://raw.githubusercontent.com/buchhwin/fedora-buchhwin-hyprland/main/bootstrap.sh
less bootstrap.sh
bash bootstrap.sh
```

The command downloads before it runs rather than piping into a shell: `-O`
writes a file and `-f` makes curl fail on any HTTP error, so `bash` only ever
sees a script that arrived complete. `curl … | bash` starts executing while the
download is still in flight, and a connection that drops halfway leaves a
truncated script running — where a cut-off line can mean something very
different from the whole one.

`bootstrap.sh` is about 30 lines: it checks you are on Fedora and not root,
installs git if missing, clones this repository to
`~/.local/share/fedora-buchhwin-hyprland`, and hands over to `install.sh`.

</details>

---

## What you get

| | |
|---|---|
| **Compositor** | Hyprland 0.55+ — **Lua** config, the format since 0.55 |
| **Bar** | Waybar, floating island, module pills |
| **Menus** | rofi 2.0 — launcher, windows, clipboard, emoji, wallpaper, shortcuts |
| **Notifications** | SwayNC with a control centre panel |
| **Terminal** | kitty |
| **Files** | Nemo |
| **Login** | SDDM, themed, with the desktop's own wallpaper behind it |
| **Lock / idle** | hyprlock + hypridle |
| **Wallpaper** | swww, with transitions |
| **Shell** | zsh + starship + atuin |
| **Settings** | a GTK4 app, sixteen pages with a search across all of them |
| **Panel popups** | calendar with appointments and weather, sound with per-app volume, network, Bluetooth, media, quick settings behind the gear |
| **Window buttons** | minimize, maximize, close — and minimize really works: a hidden workspace the dock lists |
| **Overview** | `SUPER+Tab` — everything open, grouped by workspace |
| **VPN** | WireGuard through NetworkManager: import a .conf, switch it in the bar |
| **Updates** | counted in the bar, installed from the settings — packages, flatpaks and this project |
| **Drives** | Google Drive / OneDrive via rclone, SMB/NFS via gvfs — in the file manager sidebar like a mapped drive |
| **Calendar** | GOA + evolution-data-server → GNOME Calendar, Evolution **and** the bar |
| **Firewall** | ufw, on by default |

**Nine palettes in four families** — Catppuccin (Mocha, Macchiato, Frappé,
Latte), Nord, Tokyo Night, Gruvbox, Dracula, Rosé Pine — or one derived from
your wallpaper, optionally following every change.

And "everything is themed" is not a figure of speech: **twenty-six generated
files** come from the one palette file. Hyprland, the lock screen, the bar, the
popups, notifications, the launcher, the terminal, the power menu, GTK3, GTK4,
Qt, icons, **the cursor**, `btop`, `starship`, `fastfetch`, `fzf`, `bat`, `eza`,
`lazygit`, `zellij`, `tmux`, `git-delta`, `atuin`, VS Code and Brave. The
wallpaper and the login screen follow too.

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

- [GETTING-STARTED.md](docs/GETTING-STARTED.md) — the first ten minutes
- [WINDOWS.md](docs/WINDOWS.md) — coming from Windows: what carries over
- [KEYBINDS.md](docs/KEYBINDS.md) — every shortcut
- [DEFAULTS.md](docs/DEFAULTS.md) — which program opens what (generated)
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

**Which Hyprland you get.** The config is Lua, which Hyprland has used since
0.55 — every dotfile collection you find online is still the old `hyprlang`
syntax and will not load here. Everything in this repository is developed and
verified against **0.55.4**; the COPR currently also carries 0.56.1, and a fresh
install takes whatever is newest. If a Lua API changes under you, `bhctl doctor`
and `hyprctl configerrors` are the first two things to run.

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
