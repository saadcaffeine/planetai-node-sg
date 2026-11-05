# Turn an old laptop into a node
<!-- checked: v0.91.0 -->

This page puts Linux on an old laptop so it can run a node. It is the route for a Mac that no container runtime
supports any more, and for any x86_64 laptop from about 2015 on. A 2015 quad-core with 16 GB outruns the mini PC
you would otherwise buy (see [Platforms](PLATFORMS.md)), and with Linux on the metal the OS floor stops moving.
Under Linux you can also tell a laptop not to sleep, which is most of what makes it a node.

You need a USB stick of 8 GB or more (the Omarchy image is nearly 6 GB) and about an hour, and everything on the
laptop will be erased.

> **Note.** One of the three routes here has carried a node: Linux Mint, on a 2015 MacBook Pro whose SSD had to be
> replaced first (step 6 is there because of it). The Ubuntu Server and Omarchy routes are written from the vendors'
> documentation and from what `planetai preflight` knows; nobody has walked them end to end yet. Treat them as a
> plan, and tell us at info@fab.city where they were wrong.

## 1. Before you wipe anything

Copy what you want off the disk first. This is the step people skip.

Then check the machine is worth it:

```bash
curl -fsSL https://planetai.fab.city/preflight | bash
```

If it prints *This hardware is a capable node*, the processor and the memory are settled, and the OS, which Linux
replaces, is the only blocker. The preflight checks that the disk has room and can be written; whether it survives
a long write is step 6.

## 2. Choose a Linux and make the USB stick

One question decides it: is anybody still going to use this machine?

**Nobody, it sits on a shelf and runs: Ubuntu Server.** No desktop, you reach it over ssh, it needs the least
upkeep, and its support window is measured in years.

```bash
curl -fL -o ~/Downloads/ubuntu-server.iso https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso
```

**Somebody uses it, and it is a node too: [Omarchy](https://omarchy.org).** Arch underneath and a finished desktop
on top, five questions from stick to working machine. Its own page says a 2011 ThinkPad X220 with 2 GB runs it.
The node installer takes Arch's `pacman` branch without being told.

```bash
cd ~/Downloads
curl -fLO https://iso.omarchy.org/omarchy-4.0.3.iso
curl -fLO https://iso.omarchy.org/omarchy-4.0.3.iso.sha256
shasum -a 256 -c omarchy-4.0.3.iso.sha256      # must say: omarchy-4.0.3.iso: OK
```

**Somebody uses it, and you want the ordinary desktop: [Linux Mint](https://linuxmint.com)** with Cinnamon. This is
the route that has run a node.

```bash
curl -fL -o ~/Downloads/linuxmint.iso https://mirrors.kernel.org/linuxmint/stable/22.3/linuxmint-22.3-cinnamon-64bit.iso
```

Docker's own installer reads Mint as Debian and adds the wrong repository, so the node installer reads Mint's
`UBUNTU_CODENAME` and uses Docker's Ubuntu repository instead.

The steps below are written for Ubuntu Server. Mint follows them too, except that it installs a desktop, and if its
live session already sees your WiFi you can skip the cable in step 4. Where Omarchy differs, the step says so.

Write the `.iso` to the stick with [balenaEtcher](https://etcher.balena.io). It works the same on macOS, Windows and
Linux, refuses to write to your system disk by accident, and verifies afterwards: open it, pick the `.iso`, pick the
stick, click Flash. Without it, on macOS, `diskutil list` finds the stick and
`sudo dd if=~/Downloads/ubuntu-server.iso of=/dev/rdiskN bs=1m` writes it, where N is the stick; a wrong N erases
the wrong disk.

## 3. Boot from it

| Machine | Key, held from the moment you press power |
|---|---|
| Mac (Intel) | **⌥ Option**, then choose the orange "EFI Boot" |
| Dell, Lenovo | **F12** |
| HP | **F9** |
| Most others | **F12**, else **Esc** or **F2** into the firmware to set the boot order |

If it boots into the old system, you held the key too late. Power off fully, hold the key, then press power.

## 4. Plug in an ethernet cable for the install

WiFi during a server install is the most common way this goes wrong, and on a Mac it is worse (step 7). A cable for
twenty minutes saves an hour. If the laptop has no ethernet port, a USB gigabit adapter does the job, and wired is
better for a node anyway.

## 5. Install it

**Omarchy:** answer its five questions and go on to step 6. It hands back a finished desktop and handles WiFi
itself.

**Ubuntu Server:** take every default except these:

- **Erase disk**, the whole disk, not "install alongside". You are not keeping the old system.
- **Your name, server name, username.** The server name becomes the node's hostname; `node-kitchen` is easier to
  live with than `ubuntu`.
- **Install OpenSSH server**: tick it. It is how you reach the machine once the lid is shut.
- Skip every featured server snap.

It reboots. Pull the stick out when it asks.

## 6. Test the disk

The processor in a 2015 laptop is fine. Its SSD has been powered for ten years, and an old SSD is the part most
likely to fail. It fails in a way that is easy to miss: small writes keep working, so the machine browses and
updates normally, and it only falls over on a long sustained write. Installing a node is one (a 162 MB database
image), so the install is often what finds the fault, and it looks like the installer's.

Five minutes, before you rely on the machine:

```bash
dd if=/dev/zero of=~/writetest bs=1M count=3000 conv=fsync status=progress; rm -f ~/writetest; sudo dmesg | tail -20
```

Clean output means it wrote 3 GB without complaint. `I/O error`, `hard resetting link` or
`failed command: WRITE FPDMA QUEUED` means replace the drive before you go further. A 2.5" SATA SSD is cheap, and
it is the one part that ends the machine when it goes.

> **Careful.** `smartctl` reporting `PASSED` does not clear the drive. The SSD that taught us this showed
> `overall-health PASSED`, `Reallocated_Sector_Ct 0`, `Current_Pending_Sector 0`, `UDMA_CRC_Error_Count 0` and an
> empty error log. Those counters measure dead cells and cable corruption; a controller that stops answering under
> load trips none of them. Trust the write test.

## 7. The WiFi chip, if you need WiFi

Apple laptops of this age use Broadcom cards, and which one decides how much work this is:

```bash
lspci -nn | grep -i network
```

A **BCM43602** works with the driver in the kernel. A **BCM4360** needs Broadcom's proprietary driver, which is not
on the install media, so install it with the ethernet cable still plugged in:

```bash
sudo apt update && sudo apt install -y bcmwl-kernel-source
sudo modprobe wl
```

## 8. Tell it not to sleep when the lid closes

```bash
sudo sed -i 's/^#\?HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf
sudo sed -i 's/^#\?HandleLidSwitchExternalPower=.*/HandleLidSwitchExternalPower=ignore/' /etc/systemd/logind.conf
sudo systemctl restart systemd-logind
```

Close the lid and `ssh` in from another machine. If you get a prompt, it worked.

## 9. Install the node

The same line as everywhere else, now on a machine that can run it:

```bash
curl -fsSL https://planetai.fab.city/install | bash
```

The preflight runs first, the installer adds Docker itself, and then it asks its four questions; [Install](site/install.md)
walks through them. When it is done, `planetai status` on the machine, or over ssh from your laptop, shows what it
has read.

## If the install fails

The installer names the step, the reason, the log and the way back, and on a disk failure it prints the kernel's
own words. [Troubleshooting](TROUBLESHOOTING.md) is organised by what is on your screen. One to know before you
start: `FAILED: downloading the database image` together with `failed commit on ref "layer-sha256:…"` is the disk,
not your network. Go back to step 6.

## Two more things about old laptops

A headless node does not care about the graphics card. The 15-inch MacBook Pro of mid 2015 has two GPUs switched by
Apple's gmux, a known source of trouble for a Linux desktop. A node draws nothing, so the problem does not arise,
unless you install a desktop on it.

A laptop that sat plugged in for years may have a swollen or dead battery. It still runs on mains power, but check
it before you put the machine somewhere you cannot see it:

```bash
cat /sys/class/power_supply/BAT0/health /sys/class/power_supply/BAT0/cycle_count
```
