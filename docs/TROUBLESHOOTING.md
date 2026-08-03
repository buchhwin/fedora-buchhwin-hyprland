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

## I cannot resize a window by dragging its edge

That is switched off on purpose. Hyprland's edge-resize comes with a grab area
that extends fifteen pixels past the visible border, which puts it directly
over the close and maximize buttons of most windows — aiming for the X then
drags the window instead of closing it.

Resize with `SUPER + right mouse` (anywhere in the window, no aiming needed),
with `SUPER + CTRL + h j k l`, or snap with `SUPER + arrows`. If you want the
edges back anyway:

```bash
bhctl set layout.resize_on_border=true
```

## Clicking the clock or the speaker does nothing

The popups need `gtk4-layer-shell`, and it has to be loaded before libwayland —
`buchhwin-panel` arranges that itself by re-executing with `LD_PRELOAD` set. To
see what went wrong, run it in a terminal where you can read the error:

```bash
~/.local/share/fedora-buchhwin-hyprland/panel/buchhwin-panel calendar
```

`GtkWindow is not a layer surface` means the preload did not take: the popup
still opens, but as an ordinary window rather than anchored under the bar.

## The session starts to a black screen in a virtual machine

Run the installer again with `--software-render`, then log in again:

```bash
./install.sh --software-render
```

The installer decides for itself whether a VM can render in hardware, and there
is one case it cannot decide: it recognises **virtio-gpu** and reads the VirGL
feature bit off it, but a hypervisor that presents something else — VirtualBox
presents VMSVGA — is treated as real hardware, because from sysfs that is also
what real hardware looks like. There is no way to ask Mesa before a compositor
exists, so this is a switch rather than a guess. The phase prints which branch
it took and points at the flag.

`--software-render` writes `~/.config/uwsm/env-hyprland`, which pins Mesa to
llvmpipe, and switches blur, shadows, animations and transparency off — the
same thing that happens automatically in a VM without VirGL. To undo it, run
the installer once without the flag.

## Everything is slow, animations stutter

In a virtual machine **without** VirGL that is expected: rendering happens on
the CPU, and the installer switches blur, shadows and animations off there. A
VM with VirGL (`vga: virtio-gl` under Proxmox, plus `libgl1`/`libegl1` on the
host) is treated as real hardware and keeps the full look.

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
