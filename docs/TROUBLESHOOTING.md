# Troubleshooting

Start here:

```bash
bhctl doctor
```

It checks packages, symlinks, generated theme files, `settings.lua`, the user
services and — importantly — whether the Nerd Font is really installed rather
than silently substituted.

## The session does not start

Pick **Hyprland (Buchhwin)** at the login screen; the entry is
`/usr/share/wayland-sessions/hyprland-buchhwin.desktop`.

```bash
journalctl --user -b -u 'buchhwin-*' --no-pager
journalctl --user -b | grep -i hyprland
```

A broken `settings.lua` does not prevent a session: `hyprland.lua` falls back to
the shipped example. Check it explicitly:

```bash
lua -e 'dofile(os.getenv("HOME") .. "/.config/hypr/settings.lua")'
```

The last good version is kept next to it as `settings.lua.bak`.

## Icons are boxes, the bar looks wrong

The Nerd Font is missing. fontconfig substitutes silently, so the config looks
correct and the glyphs do not render — this is exactly how the old Alacritty
setup asked for Consolas on a system that has never had it.

```bash
fc-match "JetBrainsMono Nerd Font"     # must not name a different family
./install.sh --only theme
```

## Colours did not change everywhere

```bash
bhctl theme                 # what is actually active
bhctl theme mocha mauve     # re-render everything
```

GTK4 and Qt applications only read their colours at startup, so anything
already open keeps the old ones until it is restarted.

## The bar or notifications are missing

```bash
systemctl --user status buchhwin-bar buchhwin-notifications
systemctl --user restart buchhwin-bar
```

`inactive` outside a graphical session is normal — the units are bound to
`graphical-session.target`.

## Screen sharing does not work

See [MICROSOFT.md](MICROSOFT.md#screen-sharing).

## NVIDIA: black screen after reboot

The kernel module was not built, or Secure Boot is rejecting it.

```bash
sudo akmods --force && sudo dracut --force
mokutil --sb-state
```

With Secure Boot enabled the module has to be signed and its key enrolled.
The installer warns about this; it cannot do it for you.

## Everything is slow, animations stutter

In a virtual machine that is expected: without a GPU, rendering happens on the
CPU. The installer switches blur, shadows and animations off there.

On real hardware:

```bash
bhctl set look.blur=false look.shadow=false
```

## Starting over

```bash
bhctl backup                 # keep your settings first
./install.sh --only dotfiles # relink the configs
```

Your originals were never deleted — anything that was in the way was moved to
`<name>.bak-<timestamp>` next to it.
