# Cloud and network drives

The goal is the one thing Windows gets right here: your drives are in the file
manager's sidebar, they are there after a reboot, and you type the password
once.

Set them up in **Settings → Drives**. This page explains what happens
underneath, and what to do when it does not.

## What a drive actually is here

| Kind | Backed by | Good for |
|---|---|---|
| Cloud | `rclone` | Google Drive, OneDrive, Dropbox, S3, WebDAV |
| Network | `gvfs` | SMB shares, NFS exports, anything on the LAN |

Each entry in `settings.lua` becomes a systemd user unit and a bookmark in
`~/.config/gtk-3.0/bookmarks`, which is the file Nemo reads. That is the whole
trick behind "it looks like Windows Explorer": Nemo understands remote URIs in
that file, so a share appears in the sidebar without anything being mounted
until you click it.

**Passwords are never in `settings.lua`.** They go into the keyring, and gvfs
looks them up by the same attributes it would use for an interactive prompt —
which is why it stops asking after the first time.

## Google Drive needs rclone, not GNOME Online Accounts

GNOME 50 removed file access from Online Accounts: `libgdata` was unmaintained
and was the last thing keeping libsoup2 alive. Calendar, contacts and mail
still work through Online Accounts. **Files do not.**

So a cloud drive is an rclone remote. `rclone config` once per account, then
name that remote in the settings.

## When it does not mount

Ask systemd first — every drive is a unit, so the failure is in the journal
rather than nowhere:

    systemctl --user list-units 'buchhwin-drive-*'
    journalctl --user -u buchhwin-drive-<name>

Common answers:

* **"Permission denied" on an SMB share.** The keyring entry is missing or
  wrong. Delete it in Settings → Drives and add the share again.
* **The unit is active but the folder is empty.** rclone mounted before the
  network was up. The unit already retries; if it keeps happening, the share is
  reachable later than the desktop starts.
* **Nothing in the sidebar.** Nemo caches bookmarks per session — log out and
  in. The file to check is `~/.config/gtk-3.0/bookmarks`; only the block
  between the buchhwin markers is ours, anything you bookmarked yourself is
  left alone.

## USB sticks

Nothing to configure. `udiskie` mounts them when they are plugged in and sends
a notification; the file manager opens from there.
