# Teams, Outlook and Exchange

The short version: **Teams as a web app, mail natively.** And never the
unofficial wrappers.

## Teams

Microsoft discontinued the native Linux Teams client at the end of 2022. The
web version is not a workaround — it is the supported path.

`scripts/webapp.sh` turns it into a real application: its own window with no
browser chrome, its own icon, its own launcher entry, its own window rule.

```bash
scripts/webapp.sh add Teams https://teams.microsoft.com teams
```

Installed by default, together with Outlook Web, Microsoft 365 and WhatsApp.

### Why not `teams-for-linux`

The well-known Flatpak wrapper is a community Electron shell around the same
web app. That means a second Electron runtime in memory, a lag behind
Microsoft's changes, and a project that can go quiet. Running the page in the
browser you already have avoids all three.

### Screen sharing

This is the part that actually breaks on Wayland, so check it deliberately.

Sharing goes through PipeWire and `xdg-desktop-portal`. Both
`xdg-desktop-portal-hyprland` (the screen-capture backend) and
`xdg-desktop-portal-gtk` (the file and app-chooser dialogs) are installed for
exactly this reason.

If the share button does nothing:

```bash
systemctl --user status xdg-desktop-portal xdg-desktop-portal-hyprland
```

Chromium-based browsers have historically needed a flag for the PipeWire
capturer. Whether Brave still does is a question to answer by trying it, not by
copying a flag from a five-year-old forum post:

```bash
brave-origin --enable-features=WebRTCPipeWireCapturer
```

If that fixes it, add the flag to the web app's `.desktop` file. If it changes
nothing, leave it out.

## Outlook

Here a native client is worth it, and both options are packaged in Fedora 44.

### Evolution + `evolution-ews` — recommended

The most complete Exchange support on Linux: mail, calendar, contacts and tasks
in one application, available offline. It is GTK, so it picks up the Catppuccin
colours with everything else, and its calendar shows up in the Waybar clock
through GNOME Online Accounts.

Account → *Exchange Web Services*, server usually
`https://outlook.office365.com/EWS/Exchange.asmx`.

### Thunderbird

Lighter and prettier, and its EWS support is newer — mail is solid, calendar and
contacts are less complete. A good choice if your mailbox is reachable over
plain IMAP.

### If EWS has been switched off

Microsoft is retiring EWS in favour of Graph, and many organisations have
already disabled it. Then Outlook Web as a PWA is the honest answer — same
treatment as Teams, same window rules, same icon, and it sits in the launcher
next to everything else.
