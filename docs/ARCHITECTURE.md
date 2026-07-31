# Architecture

How the pieces fit together, and why they are arranged this way. Most of the
decisions below exist because the obvious alternative was tried and did not
survive contact with the system.

## The three kinds of file

Everything in `~/.config` falls into exactly one of these, and knowing which is
usually enough to answer "where do I change this?".

| | Where it comes from | Who owns it | Survives `bhctl update` |
|---|---|---|---|
| **symlinked** | a symlink into the cloned repo | the repo | replaced by the update |
| **generated** | rendered by `theme/apply-theme.py` | the palette | rewritten by the update |
| **yours** | copied once at install | you and the settings GUI | never touched |

`~/.config/hypr` therefore contains all three at once:

```
hyprland.lua   symlink    structure
binds.lua      symlink    how a bind entry becomes a key binding
rules.lua      symlink    window and workspace rules
theme.lua      generated  colours
settings.lua   yours      values the GUI owns
```

Linking happens **per file, not per directory**. If `~/.config/waybar` were a
symlink into the repo, every theme switch would write `colors.css` into a public
git repository. Per-file links let generated and hand-written files share a
directory without one contaminating the other.

## Hyprland's configuration is Lua

Since Hyprland 0.55, hyprlang is deprecated: `hl.config{}`, `hl.bind()`,
`hl.window_rule{}`. Effectively every dotfile collection in circulation is still
`bind = SUPER, Q, killactive` and will not load. That is the main reason this
repository is written from scratch rather than forked from an existing rice.

Two consequences worth internalising:

- **`hyprctl keyword` does not work with a Lua config.** `hyprctl(1)` is explicit
  about it. Runtime changes go through `hyprctl eval` (evaluate a Lua expression)
  or a plain `hyprctl reload`. Anything that wants to change a setting *and* have
  it survive the next reload has to write the file — which is what the settings
  GUI and `toggle-gaps.sh` do.
- **A broken `settings.lua` must not cost you the desktop.** `hyprland.lua`
  loads it with `pcall` and falls back to the shipped example, so a typo leaves
  you with a working session in which to fix the typo.

## The settings file is data, never code

```lua
return {
  look = { border_size = 2, rounding = 12, blur = true },
  binds = { { key = "SUPER + Q", action = "dispatch", arg = "close" } },
}
```

The settings GUI **never parses hand-written Lua**. It reads `settings.lua`
through the `lua` interpreter (`scripts/settings.py`), gets a plain dictionary,
changes what it must, and writes the whole file back in a fixed layout. Your
hand edits survive because the file is round-tripped whole; your comments do
not, because comments are not data — that is what `settings.local.lua` is for.

Writes go to a temporary file, are validated by actually loading them in Lua,
and only then moved into place. A crash mid-write cannot leave a truncated
`settings.lua`.

> A bug worth remembering, found while building this: the Lua idiom
> `t[k] ~= nil and t[k] or fallback` collapses when the value is `false`. In the
> JSON encoder that reads the settings, it silently turned every *disabled*
> setting into `null`. Never use that shortcut for booleans.

## One palette, fifteen files

`theme/apply-theme.py` renders every application's colours from
`theme/palettes/<flavour>.json` through `theme/templates/*.tmpl`, guided by
`theme/manifest.json`. `bhctl theme latte blue` re-renders all of them and
reloads whatever is running.

The alternative — cloning a Catppuccin theme repository per application — was
rejected: fifteen upstreams to track, each with its own release cadence, and
`catppuccin/gtk` has already been archived by its authors. Adding an application
here means adding one template.

`manifest.json` also records a `group` per file, which decides what gets
reloaded. Changing the bar colours restarts waybar; it does not restart the
compositor.

## Background services are systemd user units

The bar, notifications, clipboard history, wallpaper daemon, idle manager,
polkit agent and night light are `~/.config/systemd/user/buchhwin-*.service`,
bound to `graphical-session.target`, not `exec-once` lines.

That buys three things: they restart when they crash, their output lands in the
journal instead of nowhere, and `bhctl doctor` can ask systemd whether the
desktop is healthy rather than grepping process lists.

The session itself starts through **uwsm**, which is what puts the session in a
proper systemd scope so `graphical-session.target` means anything.

## Idempotence

`install.sh` is safe to run twice, and the second run is a no-op. Concretely:

- packages are checked with `rpm -q` before installing;
- configs are symlinked, and an already-correct link is left alone;
- an existing real file is moved aside once, with a timestamp, and reported;
- shell blocks are written with `ensure_block`, which *replaces* a previously
  written block rather than appending a second one;
- `settings.lua` is only created when it does not exist.

`set -euo pipefail` plus an `ERR` trap means a failure stops the run and says
which line. Reporting success while half the packages failed is the one
behaviour a system-setup script must never have.

## Fallbacks that matter

- A failed group install is retried one package at a time, so a single bad name
  cannot take the whole list down — and the summary names the one that failed.
- Missing translations fall back to English, so a gap in `de.sh` can never print
  an empty message.
- `--dry-run` prints every command without running any of them; it is what CI
  and the test lab use to check the shape of a run.

## Virtual machines

`systemd-detect-virt` decides whether `lib/80-vm-tweaks.sh` runs. In a VM
without GPU passthrough everything renders on the CPU, so blur, shadows and
animations are switched off — but through the *same* `settings.lua` the GUI
writes, not a second configuration branch. One version runs everywhere, and the
effects are one click away from coming back.

## What is deliberately not here

- **A Catppuccin GTK theme.** Archived upstream; libadwaita takes colour
  overrides rather than themes. `adw-gtk3-theme` plus generated colours instead.
- **Screenshot and launcher wrappers from the Hypr ecosystem.** `hyprshot` is a
  grim/slurp wrapper, and `hyprlauncher` is weeks old and COPR-only. Fewer
  third-party sources means fewer things to fix at the next Fedora release.
- **Fish, and powerlevel10k.** See [CREDITS.md](CREDITS.md).
