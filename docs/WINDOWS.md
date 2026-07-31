# Coming from Windows

This is a tiling desktop that has been talked into behaving like a familiar
one. Most habits carry over; a few do not, and it is quicker to know which.

## The same

| Windows | Here |
|---|---|
| `Win + Left/Right` | `SUPER + CTRL + Left/Right` — half the screen |
| `Win + Up` | `SUPER + CTRL + Up` — maximize |
| `Alt + F4` | `Alt + F4`, or `SUPER + Q` |
| `Win + D` | `SUPER + SHIFT + Space` — everything floats on this workspace |
| Search from the Start menu | `ALT + Space` — programs, windows, files, sums |
| Clicking the clock | Clicking the clock — month and appointments |
| Volume icon | Same, with a slider and device list |
| Network icon | Same, with the Wi-Fi list |
| System tray | Same, bottom-right of the top bar |
| Taskbar | The dock, off by default — Settings → Look |

## The different

**Windows tile by default.** Open a second one and the first makes room. That
is the point of the layout, not a bug. If you want a workspace that behaves
like Windows — everything floating, drag where you like — press
`SUPER + SHIFT + Space`, or list those workspaces in the settings so they
always start that way.

**Minimize puts the window on a shelf, not into nowhere.** A tiling layout has
nothing to minimize *to*, so one was made: a hidden workspace called
`minimized`. The titlebar button and the dock both send the window there, and
the dock keeps listing it — click it there to bring it back. `SUPER + SHIFT + M`
shows the shelf, so nothing can be lost even with the dock switched off.

Workspaces are still the better tool for "put this aside for an hour":
`SUPER + 1…9` to switch, add `ALT` to take the window along.

**Arrow keys move the window, not the mouse pointer.** Focus moves on
`SUPER + h j k l`, which is one row under your right hand.

**Dragging a window edge does not resize it.** That is switched off on purpose:
the grab area extends past the visible border and sits over the close button,
so aiming for the X dragged the window instead. Resize with
`SUPER + right mouse`, anywhere in the window, no aiming.

**No registry, no scattered control panels.** Everything is one file that the
settings app owns, and `bhctl backup` puts it in an archive you can carry to
another machine.

## The bits worth learning early

* `SUPER + /` — every shortcut, searchable, generated from your own config.
* `SUPER + V` — clipboard history, including images.
* `SUPER + S` — screenshot a region; it lands in the clipboard and on disk.
* `SUPER + ö` — a terminal that drops down and goes away again.
* `SUPER + T` — light and dark, instantly, everywhere.

## Files from a Windows machine

SMB shares mount from Settings → Drives and appear in the sidebar, the way a
mapped network drive does. NTFS USB sticks mount automatically. Office
documents open in OnlyOffice, which reads and writes the same formats.
