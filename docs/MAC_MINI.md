# A Mac mini as an always-on node
<!-- checked: v0.80.10 -->

The laptop is for trying it. The mini is for leaving it. An hour, once, with a monitor plugged in for the permission
dialogs. Any Apple Silicon mini; an 8 GB base model idles under 10%. A 2018 Intel mini on macOS 14+ also works
(on 13.5 to 13.7, Colima is the only runtime that installs; see `PLATFORMS.md`).

## Physical

**Ethernet, not WiFi.** WiFi drops are the main cause of "silent sensor" alerts that are really a silent node.

**A small UPS**, for the mini and the router. In Bali the grid flickers; that kills nodes, not long outages. A 600 VA
unit smooths the dips. In a city with steady power, skip it.

Indoors, off the floor, out of the sun. Not above the wok: the sensor near it will report dinner.

## macOS settings

- **General → About → Name**: the node's name. It becomes `<name>.local` on your network.
- **Date & Time**: the right zone, automatic.
- **Energy**: prevent sleep when display is off, disks never sleep, wake for network, **start after power failure**.
- **Lock Screen**: screen saver never; display off after 2 minutes is fine.
- **Users & Groups → Automatic login**: your user. Required. Docker only runs in a logged-in session; after a power cut the
  mini would sit at the login screen with the node down. Automatic login is greyed out while FileVault is on; turn
  FileVault off first. The disk is then unencrypted at rest. For air readings and a bot token in a locked house, that is
  the right trade. If the mini holds anything personal, give the node its own user.
- **Sharing**: Remote Login on (that is how you work from the sofa), Screen Sharing on, everything else off.
- **Software Update**: download automatically, **do not install macOS updates automatically**. An unattended reboot
  mid-update is how a node stays down for a week.
- **Privacy & Security → Full Disk Access**: add Terminal and `/usr/sbin/cron` (⌘-Shift-G in the picker). Without it the
  nightly backup fails silently.

## Docker

OrbStack (lighter) or Docker Desktop. **Start at login: on.** Then power returns → boot → auto-login → Docker → containers
(`restart: unless-stopped`) → polling within two minutes. No human involved.

## Install

`curl -fsSL planetai.fab.city/install | bash`, monitor still attached. Then `planetai mesh` so the mini is reachable
from anywhere as `<name>.<tailnet>.ts.net` with no open ports.

## From your laptop

```bash
ssh you@bayu-ungasan.local    # or bayu-ungasan.<tailnet>.ts.net over Tailscale
planetai status
```

Tailscale SSH is Linux-only; on a Mac this is ordinary `ssh` over the tailnet, so Remote Login must be on.

## Backups

The mini keeps the database; a NAS pulls the dumps hourly. See `STORAGE.md`. Never put the database on the NAS.

## What can still take it down

A macOS update you approved and forgot. The router. The Docker app itself needing a click after a major update. A
kitten and the power button. `planetai doctor` after any of them.

## Moving from a laptop

`planetai backup` on the laptop, copy the dump to the mini, install there, `planetai restore <dump>`. Ten minutes, no
readings lost.
