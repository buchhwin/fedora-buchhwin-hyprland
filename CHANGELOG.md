# Changelog

## v1.1.0

Prompted by an install that ended with two warnings and two errors. Every
finding below was measured on a running system, not reasoned about.

### It asks now

- **A short setup dialog at the start**: language, keyboard layout and variant,
  timezone, computer name, palette and accent. Everything still has a flag, and
  `--unattended` or `--skip setup` turns the dialog off entirely.
- The keyboard answer is applied in **one** place too few before: the Hyprland
  session, *and* the login screen and text console. Wayland does not make the
  X11 keymap irrelevant — libxkbcommon reads it, so the SDDM greeter does too,
  and that is where the password gets typed first.
- `settings.example.lua` no longer hard-codes a German layout. A public example
  defaults to `us`; the dialog is what makes it anything else.

### The Hyprland stack is pinned, because it stopped resolving

`dnf install hyprland hyprlock hypridle …` **fails outright** on a fresh Fedora
44 as of 2026-08-02. The repository moved most of the stack to hyprutils 0.14,
but hyprlock has no build against it and stops at 0.9.6:

    hyprland 0.56.1  needs libhyprutils.so.13
    hyprlock 0.9.6   needs libhyprutils.so.12
    -> Failed to resolve the transaction

So `packages/copr-desktop.txt` now names exact versions, and phase 30 fails
loudly if something other than the 0.55 series arrives. Additionally,
`solopasha/hyprland` is restricted to the three packages it is actually there
for: its `xdg-desktop-portal-hyprland` carries **epoch 1**, which outranks any
version number, so its older build was winning over the newer one despite the
repository priority.

### Failures say why

- **The log was not a log.** `run()` wrote only the command line into it while
  the output went to the screen — so the closing "full log" line pointed at a
  file that could not answer the question it raised. It now tees.
- `dnf update` and each Flatpak carry their actual error into the warning.
- **The free-space check is a stop, not a shrug.** It used to warn and carry on,
  which is exactly how a run with 8.6 GB free installed 109 packages and then
  died on the last two Flatpaks. Thresholds are 12 / 8 / 6 GB depending on
  `--no-flatpak` and `--minimal`, and `/var/lib/flatpak` is checked separately
  when it is its own filesystem.
- A full disk now produces **one** message instead of one per application.

### Fixed along the way

- **Every question answered itself.** `_ask_raw` returned its value through a
  caller-named variable while holding a local of the same name, so `printf -v`
  wrote into the local and it vanished on return. The prompt appeared, the
  typing echoed, the answer was discarded — and `confirm()` therefore always
  meant "no". Found by driving the helpers through a pseudo-terminal; neither
  `--dry-run` nor the CI can reach that path.
- `i18n_load` never cleared `MSG_LOCAL`, so switching de → en kept answering in
  German.
- The Hyprland version check ended on `(( … )) && info …`. Under `set -e` that
  aborted the whole install with a bare line number for anyone not on 0.55 —
  the one case the check exists for.
- The Flatpak loop's stdin was the package list itself; the install call now
  reads from `/dev/null` so a child cannot eat the remaining entries.

### Removed

- **DBeaver.** Not wanted, and one less 300 MB Flatpak.

## v1.0.0

The first release. One command turns a bare Fedora Server 44 install into a
complete Hyprland desktop.

### The desktop

- **Hyprland 0.55 with a Lua configuration.** Not hyprlang: Hyprland deprecated
  it, and every dotfile collection online is still the old syntax and will not
  load. The config is split so the settings app never parses hand-written Lua —
  it rewrites one plain-data file and the rest reads it.
- **Bar, launcher, notifications, lock screen, idle, wallpaper daemon,
  clipboard history, screenshots and recording**, all as systemd user units, so
  they restart on crash and `bhctl doctor` can ask systemd whether the desktop
  is healthy instead of grepping process lists.
- **Windows have minimize, maximize and close buttons.** Hyprland has no
  minimize, so one was built: minimized windows go to a hidden workspace the
  dock still lists, and `SUPER+SHIFT+M` shows it.
- **Windows-style snapping** on `SUPER+CTRL+arrows`, floating workspaces on
  `SUPER+SHIFT+Space`, a workspace overview on `SUPER+Tab`, a drop-down
  terminal on `SUPER+` `` ` ``.

### Its own applications

- **Settings** — sixteen pages with a search across all of them: appearance,
  keys, default applications, wallpaper, drives, online accounts, input, sound,
  network and VPN, displays and saved monitor arrangements, applications,
  power, autostart and updates.
- **Panel popups** for the calendar (with real appointments and weather),
  sound (per-application volume), network, Bluetooth, media, and quick settings
  behind the gear. An on-screen display for the media keys.
- **`bhctl`** — update, theme, wallpaper, backup, restore, doctor.

### Theming

- **Nine palettes in four families** — Catppuccin (Mocha, Macchiato, Frappé,
  Latte), Nord, Tokyo Night, Gruvbox, Dracula, Rosé Pine — and a palette
  derived from your wallpaper, optionally following every change.
- **Twenty-six generated files per palette.** Hyprland, the lock screen, the
  bar, the popups, notifications, the launcher, the terminal, the power menu,
  btop, starship, fastfetch, GTK3, GTK4, Qt, fzf, bat, eza, lazygit, zellij,
  tmux, git-delta, atuin, VS Code and Brave. One palette file drives all of it.
- Wallpapers are generated per palette, and the login screen follows the
  desktop.

### Fedora-specific

- **btrfs with zstd compression**, **ufw** enabled with SSH allowed *before* the
  firewall comes up (the order matters if you are installing over SSH),
  GPU driver branch detected at install time, and RPM Fusion, COPR and Flathub
  wired up.
- **Cloud and network drives** — Google Drive and OneDrive through rclone, SMB
  and NFS through gvfs — appear in the file manager's sidebar like a mapped
  drive.
- English and German throughout, installer included.

### Notes

- `install.sh` is idempotent: running it twice changes nothing, and `--dry-run`
  shows what it would do.
- Configuration is symlinked out of the clone, so `bhctl update` is a `git pull`
  and a re-run.
