# Changelog

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
