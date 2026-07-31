# Security

## Firewall: ufw, on by default

`ufw` is installed and enabled with:

```
default deny incoming
default allow outgoing
allow 22/tcp     # SSH
allow 5353/udp   # mDNS, so nas.local resolves
```

`firewalld` is **disabled and masked**. Masked rather than merely disabled,
because a package update would otherwise start it again and two firewalls
quietly fighting each other is worse than either one alone.

### This is a deliberate choice, and it has costs

Fedora's integrated firewall is firewalld: NetworkManager, Cockpit and libvirt
talk to it directly. Choosing ufw means:

- **ufw goes through the iptables-nft compatibility layer.** It works, but it is
  the older path on a system whose native backend is nftables.
- **podman writes its own nftables rules** through netavark. It does not need
  firewalld, but it does not coordinate with ufw either: a published container
  port may not appear where `ufw status` leads you to expect it.
- **libvirt** manages its own network zones. With firewalld masked, its
  automatic firewall integration is gone; `virt-manager` networking may need
  rules of your own.

ufw was chosen because it is far simpler to reason about day to day
(`ufw allow 22`) — but you should know what you are giving up.

### Going back to firewalld

```bash
sudo ufw disable
sudo systemctl disable --now ufw
sudo systemctl unmask firewalld
sudo systemctl enable --now firewalld
```

### Skipping the firewall entirely

```bash
./install.sh --no-firewall
```

## Why the firewall phase runs last

The installer is frequently run over SSH. `ufw enable` with a default-deny
incoming policy severs the connection the moment it is applied — unless the SSH
rule is already in place.

So the order is: write the SSH rule, then enable, and do the whole thing at the
very end of the run. A mistake there costs you a reconnect instead of a
half-installed machine. The phase verifies afterwards that the SSH rule is
actually present and reports a failure if it is not.

## Passwords and tokens

Nothing is ever written to a file in this repository or to a systemd unit.

- **Network drives**: the password goes into the keyring through `secret-tool`
  (libsecret). gvfs looks it up under the same attributes when mounting.
- **Cloud storage**: rclone runs the OAuth flow in your browser and stores its
  token in `~/.config/rclone/rclone.conf`, mode 0600. This application never
  sees a password.
- **Keyring unlocking**: `pam_gnome_keyring` opens the keyring with your login
  password. Without it every drive asks again after every login — which is the
  thing that makes people write passwords into files.

## SELinux

Left enforcing. It costs nothing measurable, and this project has a concrete
example of it doing its job: the QEMU guest agent runs as root but under the
`virt_qemu_ga_t` type, and was correctly denied `useradd` and writes to
`/etc/sudoers.d`.

## What the installer changes outside your home directory

Everything, in one list, because a script that touches the system should be
able to say what it touched:

| Path | Change |
|---|---|
| `/etc/dnf/dnf.conf` | `defaultyes=True`, `max_parallel_downloads=10` |
| `/etc/yum.repos.d/` | RPM Fusion, Brave, VS Code, COPRs |
| `/etc/systemd/journald.conf.d/00-buchhwin.conf` | journal capped at 500 MB |
| `/etc/nsswitch.conf` | mDNS added to `hosts:` (backup kept) |
| `/etc/pam.d/sddm` | two `pam_gnome_keyring` lines (backup kept) |
| `/etc/sddm.conf.d/20-buchhwin-theme.conf` | greeter theme |
| `/usr/share/wayland-sessions/hyprland-buchhwin.desktop` | the session entry |
| `/usr/share/sddm/themes/` | the greeter theme |
| services enabled | `sddm`, `avahi-daemon`, `systemd-oomd`, `tuned`, `tuned-ppd`, `thermald` (Intel), `bluetooth`, `ufw` |
| services masked | `firewalld` |

`--no-tweaks` skips the journal, mDNS, oomd and power-profile changes.
`--no-firewall` skips ufw and leaves firewalld alone.
