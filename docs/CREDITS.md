# Credits

This project is configuration and glue. Everything it configures is somebody
else's work.

## Downloaded at install time

| Project | Used for | Licence |
|---|---|---|
| [Catppuccin](https://catppuccin.com/) | the palette, and the cursor, SDDM and Kvantum themes | MIT |
| [Nerd Fonts](https://www.nerdfonts.com/) | JetBrainsMono Nerd Font | MIT / OFL, per font |
| [papirus-folders](https://github.com/catppuccin/papirus-folders) | recolouring the folder icons | GPL-3.0 |

Colours for everything else are rendered from `theme/palettes/*.json` rather
than cloned, so there are no vendored theme repositories to keep in sync.

## Packaged software

Fedora, RPM Fusion, and these third-party sources:

| Source | Why |
|---|---|
| [`solopasha/hyprland`](https://copr.fedorainfracloud.org/coprs/solopasha/hyprland/) | Hyprland is orphaned in Fedora — last official build 0.45.2 on F42, absent from F43/F44 |
| [`erikreider/SwayNotificationCenter`](https://copr.fedorainfracloud.org/coprs/erikreider/SwayNotificationCenter/) | swaync is not packaged in Fedora |
| [`varlad/zellij`](https://copr.fedorainfracloud.org/coprs/varlad/zellij/) | zellij is not packaged in Fedora |
| [`atim/lazygit`](https://copr.fedorainfracloud.org/coprs/atim/lazygit/), [`atim/starship`](https://copr.fedorainfracloud.org/coprs/atim/starship/) | neither is packaged in Fedora |
| Brave, Microsoft | their own RPM repositories |
| Flathub | Spotify, Discord, Obsidian, ONLYOFFICE |

## A note on GTK

There is no Catppuccin GTK theme here. The upstream one was
[archived by its authors](https://github.com/catppuccin/gtk) — "a nightmare to
consistently theme and maintain" — and libadwaita does not accept full themes
anyway. Instead: `adw-gtk3-theme` from Fedora for the widget shapes, and
generated colour overrides for GTK3 and GTK4. One less unmaintained
dependency, and light/dark switching keeps working.

## Not used, and why

- **teams-for-linux** — the Teams web app installed as a PWA is the path
  Microsoft actually supports, without a second Electron stack.
- **hyprshot** — a wrapper around grim and slurp; `scripts/screenshot.sh` does
  the same and removes a dependency.
- **hyprpaper** — no transitions. swww has them, and they are worth it.
- **powerlevel10k** — limited support since 2024, and its config cannot be
  templated. starship's single toml file can.
