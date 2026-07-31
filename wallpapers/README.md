# Wallpapers

The `catppuccin-*.png` files here are **generated** from the palettes by
`scripts/gen-wallpapers.py` — three styles per flavour, 556 KB for all twelve.

They are generated rather than downloaded on purpose: no third-party licence
enters a public repository, there are no megabytes of binaries in git history,
and the colours are exactly the ones the rest of the desktop uses, so switching
flavour never leaves the background slightly off.

## Your own wallpapers

Put them in **`~/Pictures/Wallpapers`**. Both the picker (`SUPER+W`) and the
slideshow search that folder, and nothing there is ever touched by an update.

Anything you drop into *this* folder is ignored by git (see `.gitignore`), so
licensed or purchased images cannot end up published by accident — but
`~/Pictures/Wallpapers` is the cleaner place for them.

## Regenerating

```bash
scripts/gen-wallpapers.py                      # all flavours, all styles
scripts/gen-wallpapers.py --size 3840x2160     # 4K
```
