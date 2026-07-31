# Palette schema

One JSON file per palette in this directory. Drop a file in and it appears in
the settings window, in `bhctl theme` and in `install.sh --flavour` — none of
those keep a list of their own any more.

```json
{
  "name":         "nord",          // must equal the file name without .json
  "family":       "Nord",          // grouping in the settings window
  "display_name": "Nord",          // what the settings window shows
  "dark":         true,            // drives light/dark GTK, Qt and icons
  "accents":      ["blue", "..."], // which of the colours below may be an accent
  "colors":       { ... }          // all 26 keys, "rrggbb" without '#'
}
```

## The 26 colour keys

`rosewater flamingo pink mauve red maroon peach yellow green teal sky sapphire
blue lavender text subtext1 subtext0 overlay2 overlay1 overlay0 surface2
surface1 surface0 base mantle crust`

They come from Catppuccin, which is where this started, but they are **semantic**
here: `mauve` means "this palette's purple accent", not "Catppuccin's mauve".
A family with fewer colours maps several keys onto the same value — Gruvbox has
one purple, so `pink`, `mauve` and `lavender` share it. That is what keeps all
17 templates working for every palette without a single conditional.

Roughly, darkest to lightest on a dark palette:
`crust` < `mantle` < `base` < `surface0..2` < `overlay0..2` < `subtext0..1` < `text`.
On a light palette the order reverses — `base` is the page, `text` is the ink.

## Accents

`accents` exists because they differ per family: Gruvbox has no `mauve`, and
`apply-theme.py` exits on an accent its palette does not define. The settings
window offers exactly this list, so it cannot write one that will not render.

## Extras that are Catppuccin-only

Cursor themes, recoloured Papirus folders, the Kvantum widget theme and the
SDDM greeter are downloaded from the Catppuccin project. For any other family
`lib/50-fonts-theme.sh` skips them and says so. Everything the theme engine
renders — all 17 files — works for every palette.
