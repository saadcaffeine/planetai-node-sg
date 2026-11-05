# Platforms
<!-- checked: v0.91.0 -->

This page says which machines can run a node, the oldest OS each one needs, and what to do with a machine below
that floor. Linux comes first, macOS second and Windows third. A node's home is a box that stays on, and a laptop
under macOS is designed to go to sleep. On macOS the floor also rises every year: Docker Desktop supports the
current and two previous major macOS releases, so a Mac falls off the list with nobody deciding anything, while
Docker Engine still supports Ubuntu 22.04 and Debian 11.

One installer covers all of them and detects which it is on. Before you install, the preflight says whether this
machine qualifies, and every failing row carries the command that fixes it on that machine:

```bash
curl -fsSL https://planetai.fab.city/preflight | bash        # nothing installed yet
planetai preflight                                    # on a node
planetai preflight --json                             # to paste into an issue
```

What its verdicts mean is on [Install](site/install.md).

## The floors

The container runtime is the only hard requirement the node adds; the installer brings everything else. This
table and the sources under it are generated from `data/platform_floors.yml`, the same file the preflight reads.

<!-- BEGIN GENERATED: tools/render_platforms.py from data/platform_floors.yml -->
| Machine | Minimum OS | Container runtime that installs there | RAM | Free disk |
|---|---|---|---|---|
| **Ubuntu / Debian (amd64)**, *the first choice* | Ubuntu 22.04 · Debian 11 | Docker Engine, installed by the script | 4 GB | 3 GB |
| **Arch, and Omarchy on top of it (amd64)** | rolling | Docker from Arch's own repository, installed by the script | 4 GB | 3 GB |
| **macOS, Apple Silicon (arm64)** | **13.0** | OrbStack, Docker Desktop or Colima. Colima reaches 13.0 here. The database image is native arm64. | 4 GB | 3 GB |
| **macOS, Intel (x86_64)** | **13.5** | ≥14.0: all three · 13.5 to 13.7: **Colima only** (`--vm-type vz`) · **below 13.5: none, and Linux is the route** | 4 GB | 3 GB |
| **Windows via WSL2 (amd64)** | 10 22H2 (build 19045) | Docker Desktop, WSL2 backend | 8 GB | 3 GB |
| **Raspberry Pi OS 64-bit (arm64)** | not set | Docker Engine, installed by the script. The database image is published for arm64; **no Pi has run a node yet.** 8 GB and an SSD, never an SD card: see below. | 8 GB | not measured |

### Where each number comes from

Every floor below is the vendor's own current sentence, with the date it was read. `make check-floors` fails when any of them is more than 180 days old.

| | Floor | The vendor's words | Read |
|---|---|---|---|
| [OrbStack](https://docs.orbstack.dev/faq) | 14.0 | macOS 14.0 and newer | 2026-09-08 |
| [Docker Desktop](https://docs.docker.com/desktop/setup/install/mac-install/) | 14.0 | Docker Desktop is supported on the current and two previous major macOS releases | 2026-09-08 |
| [Colima](https://github.com/abiosoft/colima/blob/main/docs/FAQ.md#are-older-macos-versions-supported) | 13.5 | Colima requires macOS 13 or newer | 2026-09-08 |
| [UTM](https://github.com/utmapp/UTM/releases/tag/v5.0.5) | 11.3 | "Reverted minimum version requirement imposed by v5.0.4: once again we support versions down to macOS 11.3 and iOS 14.0." | 2026-09-08 |
| [VMware Fusion 13.0](https://techdocs.broadcom.com/us/en/vmware-cis/desktop-hypervisors/fusion-pro/13-0/using-vmware-fusion/getting-started-with-vmware-fusion/system-requirements-for-vmware-fusion.html) | 12.0 | Any Mac that officially supports macOS 12 Monterey or later. | 2026-09-08 |
| [VMware Fusion (current line)](https://techdocs.broadcom.com/us/en/vmware-cis/desktop-hypervisors/fusion-pro/25H2/using-vmware-fusion/getting-started-with-vmware-fusion/system-requirements-for-vmware-fusion.html) | 15.0 | Any Mac that officially supports macOS 15 Sequoia or later. | 2026-09-08 |
| [VirtualBox](https://www.virtualbox.org/manual/topics/installation.html) | 13.0 | Supported macOS hosts are listed as "26 (Tahoe)", "15 (Sequoia)", "14 (Sonoma)" and "13 (Ventura)", each "with Intel x86_64 processors" and again with… | 2026-09-08 |
| [Multipass](https://canonical.com/multipass/docs/latest/how-to-guides/install-multipass/) | 14.0 | You can use any Mac (M-series or Intel based) with macOS 14 Sonoma or later installed. | 2026-09-08 |
| [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) | 22.04 | "Ubuntu Resolute 26.04 (LTS), Ubuntu Noble 24.04 (LTS), Ubuntu Jammy 22.04 (LTS)" and "compatible with x86_64 (or amd64), armhf, arm64, s390x, and ppc… | 2026-09-08 |
| [Docker Engine on Debian](https://docs.docker.com/engine/install/debian/) | 11 | "Debian Trixie 13 (stable), Debian Bookworm 12 (oldstable), Debian Bullseye 11 (oldoldstable)" and "compatible with x86_64 (or amd64), armhf (arm/v7),… | 2026-09-08 |
| [Docker Engine on Fedora](https://docs.docker.com/engine/install/fedora/) | 43 | you need a maintained version of one of the following Fedora versions: Fedora 44, Fedora 43 | 2026-09-08 |
| [Docker Engine on Raspberry Pi OS 64-bit](https://docs.docker.com/engine/install/raspberry-pi-os/) | 12 | The page lists "32-bit Raspberry Pi OS Bookworm 12 (stable)" and "32-bit Raspberry Pi OS Bullseye 11 (oldstable)" only, and tells 64-bit users to foll… | 2026-09-19 |
| [Docker on Arch](https://wiki.archlinux.org/title/Docker) | rolling | Arch has no Docker Engine page at docs.docker.com; docker is packaged in Arch's own extra repository and the installer uses pacman. Rolling release, s… | 2026-09-08 |
| [Docker Desktop with the WSL2 backend](https://docs.docker.com/desktop/setup/install/windows-install/) | 10 22H2 (build 19045) | "Windows 10 64-bit: Enterprise, Pro, or Education version 22H2 (build 19045). Windows 11 64-bit: Enterprise, Pro, or Education version 23H2 (build 226… | 2026-09-08 |

*Docker Desktop's floor moves on its own: Docker Desktop is supported on the current and two previous major macOS releases, so it drops the oldest macOS each autumn whether or not anyone edits this page.*
<!-- END GENERATED -->

RAM and disk in the table are the runtime vendors' floors. The node itself is much smaller (see
[what it costs](#what-the-node-costs)), so the runtime is what decides whether a machine qualifies.

## Two ways to put Linux on a machine

The choice depends on whether anybody still uses the machine.

**Ubuntu Server** if nobody does and it just runs. No desktop, you reach it over ssh, it needs the least upkeep,
and it has the longest support window: Docker still supports 22.04. This is the answer for a mini PC in a hallway,
or a laptop with the lid shut on a shelf.

**Omarchy** if somebody uses it and it is also a node. Arch underneath, Hyprland on top, installed from an image by
answering five questions; its own page says a 2011 ThinkPad X220 with 2 GB of RAM runs it. Arch is a rolling
release, so there is no version floor to outlive, and the installer takes its `pacman` branch.

Linux Mint also works, and it is the one of the three that has carried a node. Either way the install line is the
same, and [Revive a laptop](REVIVE_A_LAPTOP.md) walks the whole route.

## A Mac below the floor

Below the floor no container runtime installs, and on some models upgrading is not a route. A 15-inch MacBook Pro
of mid 2015 tops out at macOS 12.7.6, while a 2017 model reaches Ventura (13.7.6) and clears the Intel floor of
13.5, with Colima as its only runtime. `data/mac_ceilings.yml` holds what Apple's compatibility pages establish, and
the preflight says which case a machine is in.

Two routes work on a Mac that cannot upgrade, and the preflight prints both as commands:

- **Linux in a virtual machine on that Mac.** UTM is free, needs no account, supports macOS 11.3, and on Intel uses
  Apple's own hypervisor, so the guest runs at close to full speed. Older UTM builds stay on GitHub Releases for a
  Mac below a current build's floor. VMware Fusion 13.0 (macOS 12 or newer) is the alternative when the VM will run
  for months: bridged networking, open-vm-tools, and `vmrun start <vmx> nogui` to start it headless. The current
  Fusion line needs macOS 15.
- **Linux on the metal**, and the laptop becomes the node: [Revive a laptop](REVIVE_A_LAPTOP.md).

Multipass needs macOS 14 and VirtualBox's oldest supported host is Ventura, so neither helps on these Macs.

## Raspberry Pi and other arm64 boards

The database image runs on arm64, and no Pi has run a node yet.

The node's database is `imresamu/postgis:16-3.4-alpine`, a build of the PostGIS recipe published for both
`linux/amd64` and `linux/arm64` under one tag, on Alpine. The other images a node pulls are multi-arch too:
`python:3.12-slim` for the app, `eclipse-mosquitto:2` for the `mqtt` profile, `ipfs/kubo:v0.43.0` for the `ipfs`
profile and `grafana/grafana-oss:13.0.2` for the `grafana` profile. CI runs the real installer end to end on an arm64 runner, which proves the images resolve and the database
comes up. It proves nothing about an SD card, or a 4 GB board in a warm cupboard.

The image stays on Alpine on purpose. Alpine uses musl, which records no collation version, and every existing
node's data directory was created that way. A Debian (glibc) build opens the same data directory without a warning,
but its text ordering differs, so every text index is silently out of order and Postgres has nothing to compare
that would tell it. Keeping the same libc is what lets an existing node switch images safely.

`docs/ARM64.md` is the test plan for whoever goes first. For a Pi: 64-bit Raspberry Pi OS, 8 GB, and boot from an
NVMe hat or a USB SSD. Never an SD card: Postgres syncs to disk on every commit, and an SD card dies under that
within a year.

## Which machine to reach for first

**A repurposed x86_64 laptop.** The reference here is a 15-inch MacBook Pro of mid 2015: Core i7-4870HQ, 4 cores
and 8 threads, 16 GB. Its Geekbench 6 multi-core score is 3,664
([cpu-monkey](https://www.cpu-monkey.com/en/benchmark-intel_core_i7_4870hq-geekbench_6_multi_core)). Under macOS it
cannot run a node at all; with Linux on the metal it is a good one. Any x86_64 laptop from about 2015 with 8 GB is
in the same class.

**A small always-on x86 mini PC.** For example a Beelink MINI S12 Pro: Intel N100, 4 cores, 16 GB, 500 GB SSD,
about 6 W idle and almost silent. Its Geekbench 6 multi-core score is 2,595
([cpu-monkey](https://www.cpu-monkey.com/en/benchmark-intel_processor_n100-geekbench_6_multi_core)).

So the ten-year-old laptop is about 40% faster on multi-core than the mini PC you would otherwise buy, and that is
why we say revive first. The mini PC wins on idle power, silence and having no battery to age, and those are good
reasons to choose it. Its price moves weekly and by region, so price it where you are.

## What the node costs

Measured from the tarball, both containers built for `linux/amd64` with no sensor configured, which is how
everyone starts:

| | mean | peak |
|---|---|---|
| app container, memory | 150.0 MiB | 150.9 MiB |
| database container, memory | 79.2 MiB | 80.4 MiB |
| **both, memory** | **229 MiB** | **231 MiB** |
| app container, CPU | 2.8 % | 23 % (during a poll) |
| database container, CPU | 4.8 % | 47 % (during a poll) |

Twelve samples over two poll cycles and one report, on an amd64 build emulated on Apple Silicon, so the memory
figures hold and the CPU figures overstate real amd64 hardware. A report takes 1.5 s. On disk: 192 MB for the app
image, 453 MB for the database image, and 114 MB for the database volume after the first-start history of
4,476 rows (92 days of CAMS plus NASA POWER normals).

There is no lighter profile, because there is nothing to take out. The one heavy thing a node can run, a local
language model, is opt-in: `planetai agent local` recommends one and downloads nothing, `planetai agent local pull
<tag>` fetches it, and it runs on the host rather than in a container. Containers on macOS get the CPU only, on
Intel and Apple Silicon alike, and that matters for the local model and nothing else here.

## On any machine

The node needs about 2 GB of disk for itself, and the images are a 208 MB download (162 MB database, 46 MB Python
base, both compressed, amd64). Node #1, with four local sensors and the public references, adds about 1 MB of
readings a day, a few hundred MB a year. Use ethernet over WiFi where you can. The machine must boot and log in on
its own after a power cut, or the node is down until someone types a password; for an always-on Mac, see
[Mac mini](MAC_MINI.md).

On macOS 26, dragging firmware onto a Meshtastic radio's drive fails; serial DFU works ([Radios](MESHTASTIC.md)).
