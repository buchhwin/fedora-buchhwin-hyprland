# Changelog

## v1.1.2

Everything here was found by building a machine from nothing and looking at it:
a fresh VM, the README's own command, and then a screenshot. None of it shows up
in a log, and none of it would have been found by reading the code.

### The dock shows applications, not initials

Pinned launchers drew the first LETTER of the entry id — a dock captioned
"B K N C" — on the reasoning that "a custom module cannot draw a .desktop icon,
only wlr/taskbar can". The first half is true and the conclusion was wrong:
waybar has an `image` module (waybar-image(5)) that draws anything GdkPixbuf can
open, which includes Papirus' SVGs. It was never a limitation, only an unchecked
assumption.

Resolving the icon needed two things the obvious version gets wrong:

- **The icon name is not the application name.** Nemo's entry asks for
  `system-file-manager`, VS Code's for `vscode`. Looking up the id finds nothing
  for either, silently.
- **Papirus-Dark does not inherit from Papirus.** Fedora's copy declares
  `Inherits=breeze-dark,hicolor` while carrying only some application icons
  itself. Following the declared chain misses most of them, so the search order
  is an explicit list.

Missing icons fall back to the generic `application-x-executable` rather than to
a hole in the dock, and the letter survives only for a machine with no icon
theme at all.

### The dock had an empty capsule floating in it

`.modules-center` paints its rounded background even when the group is empty, so
with no windows open the centred taskbar drew a small dark capsule in the middle
of the screen. The dock now sets `"name": "dock"` — waybar turns that into a CSS
class — and drops the background for its own centre group. The top bar keeps
its islands.

### A red warning greeted every login

"Hyprland was started without start-hyprland. This is highly not recommended
unless you are in a debugging environment." The session is started by uwsm, which
is the supported way to run Hyprland under systemd; start-hyprland is the other
supported launcher. Running both to silence a warning would be the wrong trade,
so `misc:disable_watchdog_warning` is set — the name read off the running
compositor with `hyprctl descriptions -j`.

### Menus offered the same answer twice

On a German machine the keyboard question listed `de` as options 1 AND 3, both
labelled "(default)"; the timezone question did the same with Europe/Berlin.
Every caller passes the current value first and then a short list that often
already contains it. `ask_choice` now drops duplicates, keeping the first.

## v1.1.1

Everything that dims, locks, blanks or suspends the screen was broken, in three
independent ways that each hid the next. None of it is visible in a virtual
machine, which is why it survived to here — this release exists because the
desktop is about to be installed on real hardware.

### The screen never turned itself off

`hypridle.conf` still asked for `hyprctl dispatch dpms off`. Under the Lua
config provider that is a **syntax error**, and hyprctl reports it on stdout and
then **exits 0** — asking it for `dpms on` answers:

    error: [string "return hl.dispatch(dpms on)"]:1: ')' expected near 'on'
    $ echo $?
    0

So the fifteen-minute blank never happened, the DPMS-restore after resume never
happened, and nothing anywhere said so. The correct call is
`hyprctl dispatch 'hl.dsp.dpms({ action = "off" })'`, taken from the running
compositor and from `ConfigActions.hpp`, not from a wiki.

This was the eleventh site of a bug fixed in ten places for v1.0.0. It survived
because it lives in a `.conf` file, so every search for `.lua` and `.sh` walked
past it. `tests/test-dispatch.sh` now fails the build on any `hyprctl dispatch`
that is neither Lua nor a backticked mention in a comment — whatever the file
type.

### The Power page wrote to nobody

The settings app's four idle timings went into `settings.lua`, and the generator
that was supposed to turn them into `hypridle.conf` **had never been written**.
The file's own header named a script that did not exist, and the installed
config was a symlink to the template in the repository — so every slider moved,
saved, and changed nothing. There was no suspend listener at all, which made
"Suspend after" unreachable by construction.

`scripts/idle-config.sh` now generates the file from `settings.lua`, the way
`dock.py` generates the dock. It runs from the installer, from Apply in the
settings window, from `bhctl set`/`reload.sh` and from `bhctl restore`. Zero
means that step is left out rather than written as `timeout = 0`. Suspend gets
a listener when it is asked for.

### The idle manager had never started

On the test machine `buchhwin-idle.service` was `enabled` with an **empty
journal**, while all twelve of its neighbours were running. `systemctl enable`
starts nothing, which is right during the first install — there is no Wayland
display yet — but this phase also runs from inside a live session on every
`bhctl update`, and there a newly enabled unit waits for the next login while
looking perfectly healthy. The phase now starts enabled units that are not
running when a graphical session is active, and says which ones and why.

### Also

- The dim step used `brightnessctl -s set 10`: no device class, so on a machine
  with no screen backlight it turns down an LED — measured in a VM, the current
  device was `input1::numlock`. And no `%`, so `10` is a raw value: 10% of a
  panel whose maximum is 100, and effectively off on one whose maximum is 19200.
  Now `-c backlight -s set 10%`.

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
