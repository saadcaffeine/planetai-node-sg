# A Mac mini as an always-on node
<!-- checked: v0.91.0 -->

A laptop is for trying a node, a Mac mini is for leaving one running. It takes an hour, once, with a monitor
plugged in for the permission dialogs. Any Apple Silicon mini works, the 8 GB base model included. A 2018 Intel
mini works on macOS 14 or newer; on 13.5 to 13.7 only Colima installs ([Platforms](PLATFORMS.md)).

## Where it sits

Use ethernet. WiFi drops cause most "silent sensor" alerts that are really a silent node. Where the grid
flickers, as in Bali, a small UPS (about 600 VA) on the mini and the router smooths the dips, which kill nodes more
often than long outages do. Indoors, off the floor, out of the sun, and away from the stove, or the sensor near it
reports dinner.

## macOS settings

| setting | value |
|---|---|
| General › About › Name | the node's name; it becomes `<name>.local` on your network |
| Date & Time | the right zone, automatic |
| Energy | prevent sleep when the display is off, wake for network access, **start up after a power failure** |
| Lock Screen | screen saver never; display off after 2 minutes is fine |
| Users & Groups › Automatic login | your user (required, below) |
| Sharing | Remote Login and Screen Sharing on, everything else off |
| Software Update | download automatically, do **not** install macOS updates automatically: an unattended reboot mid-update can keep a node down for a week |
| Privacy & Security › Full Disk Access | Terminal and `/usr/sbin/cron` (⌘-Shift-G in the picker), or the nightly backup fails without a word |

Docker only runs in a logged-in session, so without automatic login the mini sits at the login screen after a power
cut with the node down. macOS greys automatic login out while FileVault is on: turn FileVault off first, and the
disk is unencrypted at rest. For air readings and a bot token in a locked house that is a fair trade; if the mini
holds anything personal, give the node its own user.

## Docker and the install

Install OrbStack (lighter) or Docker Desktop with **Start at login** on. After a power cut the mini then boots, logs
in, starts Docker, Docker starts the containers (`restart: unless-stopped`), and the node polls again within two
minutes with nobody there.

With the monitor still attached:

```bash
curl -fsSL https://planetai.fab.city/install | bash
planetai mesh      # reachable as <name>.<tailnet>.ts.net from anywhere, no open ports; needs Homebrew
```

From your laptop, over ordinary `ssh` (Remote Login on):

```bash
ssh you@bayu-ungasan.local    # or bayu-ungasan.<tailnet>.ts.net over Tailscale
planetai status
```

The database stays on the mini; a NAS can pull the dumps every hour ([Storage](STORAGE.md)).

## What can still take it down

A macOS update you approved and forgot, the router, or Docker wanting a click after a major update. Run
`planetai doctor` after any of them.

## Moving from a laptop

`planetai backup` on the laptop, copy the dump to the mini, install there, then `planetai restore <dump>`. About ten
minutes, and every reading, alert and answer the laptop recorded comes across. Two things are not in the dump: the
settings saved from Set up (write them down, or set them again on the mini) and the pictures in `CAPTURES_DIR`
(copy that folder across with the dump).
