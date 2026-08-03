# Changelog

## v1.2.1

The dock is built before the popups, not after them.

Found by measuring rather than by looking: six seconds after login on a freshly
installed machine the nine popup windows were up and the dock's layer surface
did not exist yet. The dock is the only window in that process that is visible
from the start, so it was the one thing arriving late — which reads as
"something went wrong" rather than "still starting". It is up in about half a
second now.


## v1.2.0

The dock became an application, and the graphics assumptions got sorted out for
the machine this is actually for — a laptop, not a virtual machine.

### The dock is one row of icons, not two features pretending to be one

waybar's `wlr/taskbar` lists running windows and a separate module launches a
pinned one, and the two know nothing about each other. So a pinned Brave that
was running appeared twice; pinning from the dock was impossible, because waybar
has no context menu; and the two module groups carry separate backgrounds, which
is why a newly opened window's icon floated outside the dock's rounded island.

None of that is a bug in waybar. A dock is an application, so it is one now —
`panel/dock_window.py`, inside the panel daemon that was already paying GTK4's
half-second startup once per session.

- **one icon per application**, pinned or running or both, with dots underneath
  for how many windows it has
- left click focuses the most recently used window, or launches it
- **right click** pins, unpins, closes everything, or picks a window by title
- windows on other workspaces are listed too — a window you cannot see is
  exactly the one the dock is for
- the island does not grow: measured at 204x58 with no windows open and 204x58
  with two

Matching a window to an application is the part that needed care: a window's
class is not its desktop id (`brave-browser` against `brave-origin`), so
`initial_class` and `class` are both tried, normalised, and put through an alias
table. Anything still unmatched gets an icon of its own rather than being
silently dropped.

`settings.py set` could not parse a list, so `dock.pinned=["kitty"]` used to
store the *text*. Pinning would have been broken in a way that looked like it
worked.

### Graphics: what was measured and what was guessed

- **Hybrid laptops were detected as Intel.** `detect_gpu` took the first
  `lspci` line, and on an Intel+NVIDIA machine that is the iGPU — so the NVIDIA
  branch never ran and the akmod that machine needs was never built. The
  discrete card now wins whenever both are present.
- **The brightness keys aimed at the wrong device.** `brightnessctl` without
  `-c backlight` acts on whatever it considers current, which on a machine with
  no screen backlight is an LED. The popup had always passed the class; the
  keybinds had not.
- **A VM's scale is now pinned to 1.** Inside a VM the EDID physical size comes
  from the hypervisor rather than from a panel, so Hyprland's `auto` derives a
  scale from fiction. Reproduced on demand with a headless output: it came up at
  **scale 2**, which is exactly "everything is twice as big". `monitor_scale` is
  a setting, so the Displays page overrides it either way.
- **A VM whose 3D cannot be verified gets GTK4 on software rendering, and
  nothing else.** VirtualBox presents VMSVGA, so there is no VirGL bit to read
  and "accelerated" really means "no idea". GTK4 does not fall back by itself,
  and everything here that is not the bar is GTK4 — including the daemon that
  draws the dock and every popup in the bar. In software that costs a few small
  windows; switching Mesa off wholesale would cost a working compositor.

⚠️ All of this stays behind `IS_VM`. On real hardware the phase returns in its
first line.

### A stylesheet rule that applies to nothing now fails the build

The dock's first stylesheet asked for `@barbg`, `@pillhover` and `@overlay1` —
waybar's colour names. The panel's are `@popupbg`, `@surface1` and `@overlay0`.
GTK drops a declaration whose colour is undefined without a word, so the dock
had no background, no hover and invisible dots while every rule looked correct.
`tests/test_css_colors.py` checks each stylesheet against the template that
generates its colours, and runs in CI.

### Also

- The Displays page was verified against **two** screens for the first time,
  using `hyprctl output create headless`. The "Active" switch appears only with
  a second screen, as intended.
- `settings.py get` on a key that does not exist printed a Python traceback.
  A setting nobody has touched is the normal case, not a crash.


## v1.1.4

Prompted by the first install on VirtualBox, where "everything is too big" had
no answer inside the desktop at all.

### Resolution, refresh rate, scale and rotation are settable

The Displays page only ever listed the screens. Its own subtitle said so —
"change them in settings.lua under monitors" — so the one setting most likely
to be wrong on a new machine was reachable with a text editor and nowhere else.

It now offers, per screen, the resolution and refresh rate (from what the screen
reports it can do), the scale, the rotation, variable refresh rate, and — only
when a second screen exists — a switch to turn one off. `scripts/monitors.py`
grew `show` and `set` to back it; everything still goes through settings.lua and
a reload, because `hyprctl keyword monitor` does nothing under the Lua config
provider.

**Every change is followed by a countdown that puts it back unless it is
confirmed.** A mode the screen cannot show leaves a display nobody can read, and
the button to undo it would be on that display.

Two things had to be measured rather than assumed:

- Hyprland **reports** its modes as `1280x800@74.99Hz` and **accepts** them as
  `1280x800@74.99`. Handing the reported string straight back produces a line
  Hyprland silently discards, falling back to `preferred` — so picking a mode
  from a list of what the screen supports would have quietly given you a
  different one.
- The rotation is an enum, not degrees: `--transform 90` comes back as
  `transform=1`.

The monitor fields the Lua config accepts (`transform`, `vrr`, `mirror`,
`bitdepth`, …) come from Hyprland's own type stubs,
`/usr/share/hypr/stubs/hl.meta.lua`, class `HL.MonitorSpec` — which documents
the whole Lua API and is a better source than the wiki for exactly this.

### "No displays reported" was sometimes a lie

`hyprctl` does **not** find the running compositor by itself: without
`HYPRLAND_INSTANCE_SIGNATURE` it answers "is hyprland running?" and every query
came back empty. The settings window inherits that variable when it is started
from the session and not otherwise — and an empty list was then shown as "no
displays", which reads as "this machine has no screens" rather than "I could not
ask". monitors.py now finds the instance the way scripts/minimize.py already
did, and fails loudly when there really is nothing to talk to.

### bhctl doctor was blind to the two services whose absence is invisible

It checked bar, notifications, clipboard, wallpaper, idle and polkit — but not
**panel** and not **dock**. The panel daemon is what every popup in the bar
talks to through a FIFO, so when it is dead the bar still looks perfectly
correct and simply no click does anything. Inside a session that is now a
reported problem, not an "inactive (normal)".

### --software-render also switches GTK4 off GL

GTK4 draws through GSK, which picks OpenGL and does not fall back on its own.
Everything here that is not the bar is GTK4 — the settings window and the panel
daemon. `GSK_RENDERER=cairo` is now written alongside the Mesa variables; the
value is taken from `GSK_RENDERER=help` on the installed GTK, which lists
broadway, cairo, opengl, gl and vulkan and warns-and-ignores anything else.

## v1.1.3

Two guards, both for people testing this in a virtual machine before putting it
on a real one.

### It refuses to start on rpm-ostree

Fedora CoreOS, Silverblue and Kinoite have no dnf; packages are layered with
`rpm-ostree` and every change needs a reboot. The installer calls dnf fifty-one
times.

The check has to be separate from the distribution check, because that one
passes: `fedora-release.spec` builds CoreOS' os-release by *appending*
`VARIANT_ID=coreos` to the ordinary one, so `ID` stays `fedora`. Without this,
the run reported a cheerful "Fedora 44", spent three phases looking like
progress, and then died on the first dnf call. Detected via
`/run/ostree-booted`, ostree's own marker for a booted deployment.

### --software-render, for a VM whose 3D cannot be verified

The VM phase reads the VirGL feature bit off **virtio-gpu** to decide whether
hardware rendering is available. A hypervisor presenting anything else —
VirtualBox presents VMSVGA — is therefore treated as real hardware, because
from sysfs that is exactly what real hardware looks like. If its 3D does not
work, Hyprland finds no EGL device and draws nothing at all.

Mesa cannot be asked before a compositor exists, so this is a documented switch
rather than a better guess: `--software-render` writes the same
`env-hyprland` and switches off the same effects that a VM without VirGL gets
automatically, on any machine. Running the installer once without it undoes it.

The phase now also says which branch it took, and names the flag — because
"accelerated" can mean "could not be checked", and somebody looking at a black
screen needs to know which of the two happened.

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
