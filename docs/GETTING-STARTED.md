# Getting started

The first ten minutes, in the order they actually matter.

## The six keys that do most of the work

| Keys | |
|---|---|
| `SUPER + Return` | Terminal |
| `SUPER + B` | Browser |
| `SUPER + E` | Files |
| `SUPER + Q` | Close the window |
| `ALT + Space` | **Search everything** — programs, open windows, files, and sums |
| `SUPER + /` | Every shortcut, searchable, built from your own configuration |

If you remember one, make it `SUPER + /`. It is generated from what is actually
bound, so it is right even after you have changed things.

## Moving windows around

Arrow keys move the focused window. Hold `CTRL` as well and it snaps to a half
or maximizes, the way dragging to a screen edge does on Windows. `SUPER + 1…9`
switches workspace; add `ALT` to send the window there with you.

Resize with `SUPER + right mouse` anywhere in the window — no aiming at edges,
which is why edge-dragging is switched off by default.

## Where the settings are

There is a gear in the top bar, and `SUPER + I`. Everything the desktop can do
is in there: borders and gaps, the theme, every key binding, wallpapers,
drives, sound, network, displays and which programs the launcher shows.

Nothing needs a text editor. If you prefer one anyway, it is all in
`~/.config/hypr/settings.lua` and the app will keep your edits.

## Taking it with you

    bhctl backup            writes buchhwin-settings-<date>.tar.gz
    bhctl restore <file>    puts it back, on this or any fresh install

That archive holds your settings, not generated files — restoring it on a new
machine regenerates the rest. Paths inside are relative to your home directory,
so it restores under a different username without editing.

## When something looks wrong

    bhctl doctor

It checks the packages, the configuration links, the generated theme files, the
user services and the fonts, and says which of them is unhappy.
`docs/TROUBLESHOOTING.md` covers the specific cases.

## Two things that surprise people

**The bar's right-hand side is clickable.** Sound, network and the clock each
open a small panel; clicking elsewhere closes it. That is where the volume
slider, the Wi-Fi list and the month view live.

**A single window keeps a small gap and its rounded corners.** Press
`SUPER + F` for true edge-to-edge — that is what fullscreen is for.
