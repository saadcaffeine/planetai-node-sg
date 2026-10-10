# Turn an old laptop into a node
<!-- checked: v0.80.10 -->

> **Partly rehearsed, and the part that was rehearsed is not the part this page recommends.**
> On 10 September 2026 a 2015 MacBook Pro became a live node this way — on **Linux Mint 22.3**, which is
> neither of the two distributions below, and only after its SSD was replaced. So: the Mint route is
> walked, and §0.5 exists because of what that machine cost before anybody thought to test its disk.
> The Ubuntu Server and Omarchy routes are still written from the vendors' own documentation and from
> what `planetai preflight` knows about the machine; nobody has walked either end to end. Treat those
> two as a plan and not a recipe, and tell **info@fab.city** where they were wrong.

A node's home is a box that stays on. A laptop is designed to go to sleep, which makes it a poor node
under macOS or Windows and a good one under Linux, where you can simply tell it not to.

This is the route for a Mac that no container runtime supports any more — and for any x86_64 laptop from
about 2015 onwards. It is not a downgrade. A 2015 quad-core with 16 GB outruns the mini PC you would
otherwise buy (see `PLATFORMS.md`), and once Linux is on the metal the floor stops moving underneath you.

**What it costs you:** a USB stick of 4 GB or more, an hour, and everything currently on that laptop.

---

## 0. Before you wipe anything

The disk gets erased. Copy what you want off it first — this is the step people skip.

Check the machine is worth it:

```bash
curl -fsSL planetai.fab.city/preflight | bash
```

If it prints *"This hardware is a capable node"*, the CPU and the memory are settled and the OS, which Linux replaces, is the only blocker. It checks
that the disk has room and can be written to, not that it survives a long write, which is the next
section and the one that matters most on a machine this old.

## 0.5. Test the disk before you trust the machine

The processor in a 2015 laptop is fine. Its SSD has been powered for ten years, and **an old SSD is the
most likely thing to fail in an old laptop** — not the CPU, not the memory.

It fails in a specific way that is easy to miss: small writes keep working, so the machine feels
healthy, browses, updates, and only falls over on a long sustained write. Installing a node happens to
be a long sustained write — a 162 MB database image — so the node install is often the first thing to
find the fault, and it looks like the installer's fault. It is not.

Five minutes, after Linux is on it and before you rely on it:

```bash
dd if=/dev/zero of=~/writetest bs=1M count=3000 conv=fsync status=progress; rm -f ~/writetest; sudo dmesg | tail -20
```

Clean output means it wrote 3 GB without complaint. **`I/O error`, `hard resetting link`, or
`failed command: WRITE FPDMA QUEUED` means replace the drive** before you go further. A 2.5" SATA SSD
is the cheapest part of this project and the only one that ends the machine when it goes.

> **`smartctl` saying `PASSED` does not clear the drive.** The tester whose machine taught us this had
> `overall-health PASSED`, `Reallocated_Sector_Ct 0`, `Current_Pending_Sector 0`,
> `UDMA_CRC_Error_Count 0` and an empty SMART error log — and it was still the SSD. Those counters
> measure dead cells and cable corruption; a controller that stops answering under load trips none of
> them. Trust the write test, not the health summary.

## 1. Choose which Linux, then make the USB stick

One question decides it: **is anybody still going to use this machine?**

**No — it sits on a shelf and runs.** Ubuntu Server. No desktop, ssh in, the lowest upkeep of anything
here, and a support window measured in years.

```bash
curl -fL -o ~/Downloads/ubuntu-server.iso https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso
```

**Yes — somebody uses it, and it is also a node.** [Omarchy](https://omarchy.org): Arch underneath,
a finished desktop on top, five questions from stick to working machine. Its own page says a 2011
ThinkPad X220 with 2 GB runs it. Everything below applies, except that you get a desktop at the end and
the installer takes Arch's `pacman` branch instead of `apt`.

```bash
curl -fL -o ~/Downloads/omarchy.iso https://iso.omarchy.org/omarchy-4.0.3.iso
curl -fL -o ~/Downloads/omarchy.iso.sha256 https://iso.omarchy.org/omarchy-4.0.3.iso.sha256
shasum -a 256 -c ~/Downloads/omarchy.iso.sha256      # must say: OK
```

**Yes, and you want the ordinary answer.** [Linux Mint](https://linuxmint.com) — Cinnamon, a desktop
that behaves the way people expect, and the only route on this page anybody has actually walked. It is
what the 2015 MacBook in the banner runs.

```bash
curl -fL -o ~/Downloads/linuxmint.iso https://mirrors.kernel.org/linuxmint/stable/22.3/linuxmint-22.3-cinnamon-64bit.iso
```

Mint used to break the node install: it identifies itself in a way that made Docker's own installer read
it as Debian and add a repository for a release that did not match, which ended in held broken packages.
That is fixed — the installer reads `UBUNTU_CODENAME` and takes Docker's documented Ubuntu path. If you
are cleaning up after an older attempt, `docs/TROUBLESHOOTING.md` has the one line that clears it.

The rest of this page is written for Ubuntu Server, because that is the one a node usually wants. Where
Omarchy differs, it says so. Mint follows the Ubuntu Server steps except that it installs a desktop, so
you can skip the ethernet advice in §3 if its live session already sees your Wi-Fi.

Write it to the stick with [balenaEtcher](https://etcher.balena.io) — it is the same on macOS, Windows and
Linux, it refuses to write to your system disk by accident, and it verifies afterwards. Open it, pick the
`.iso`, pick the stick, click Flash.

*If you would rather not install anything: on macOS, `diskutil list` to find the stick, then*
*`sudo dd if=~/Downloads/ubuntu-server.iso of=/dev/rdiskN bs=1m` — where N is the stick and getting it*
*wrong erases the wrong disk. Etcher exists because of that sentence.*

## 2. Boot from it

| Machine | Key, held from the moment you press power |
|---|---|
| Mac (Intel) | **⌥ Option**, then choose the orange "EFI Boot" |
| Dell, Lenovo | **F12** |
| HP | **F9** |
| Most others | **F12**, else **Esc** or **F2** into the firmware and set the boot order |

If the machine boots into its old system instead, you held the key too late. Power off fully, hold the
key, then press power.

## 3. Plug in an ethernet cable for the install

Wi-Fi during a server install is the single most common way this goes wrong, and on Macs it is worse than
usual — see the next section. A cable for twenty minutes saves an hour. If the laptop has no ethernet
port, a USB gigabit adapter is about the cheapest useful thing you can own.

## 4. Install it

**Omarchy:** answer its five questions and skip to step 6 — it hands back a finished desktop, and it
brings its own Wi-Fi handling. Then come back for the lid and the install line.

**Ubuntu Server:**

Take every default except these:

- **Erase disk** — the whole disk, not "install alongside". You are not keeping the old system.
- **Your name / server name / username** — the server name becomes the node's hostname; something like
  `node-kitchen` is easier to live with than `ubuntu`.
- **Install OpenSSH server** — tick it. This is how you reach the machine once the lid is shut. Skipping
  it means carrying a monitor to it later.
- Skip every "featured server snap".

It reboots. Pull the stick out when it asks.

## 5. The Wi-Fi chip, if you need Wi-Fi

Apple laptops of this era use Broadcom cards, and which one decides how much work this is. On the
installed machine:

```bash
lspci -nn | grep -i network
```

- **BCM43602** — works with the in-kernel driver. Nothing to do.
- **BCM4360** — needs Broadcom's proprietary driver, and it is not on the install media. With the
  ethernet cable still plugged in:
  ```bash
  sudo apt update && sudo apt install -y bcmwl-kernel-source
  sudo modprobe wl
  ```
  This is why step 3 says to use a cable: without one you cannot download the driver that gives you
  Wi-Fi. Wired is better for a node anyway.

## 6. Tell it not to sleep when the lid closes

The one thing that separates a laptop-shaped node from a laptop:

```bash
sudo sed -i 's/^#\?HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf
sudo sed -i 's/^#\?HandleLidSwitchExternalPower=.*/HandleLidSwitchExternalPower=ignore/' /etc/systemd/logind.conf
sudo systemctl restart systemd-logind
```

Close the lid. `ssh` in from another machine. If you get a prompt, it is done.

## 7. Install the node

Same line on either, and on Omarchy the installer uses `pacman` instead of `apt` without being told.

The same line as everywhere else, now on a machine that can run it:

```bash
curl -fsSL planetai.fab.city/install | bash
```

Preflight runs first, the installer adds Docker itself on Linux, and it asks four questions.

---

## Two things worth knowing

**A headless node does not care about the graphics card.** The MacBook Pro (Retina, 15-inch, Mid 2015)
has two GPUs — a Radeon R9 M370X and Intel Iris Pro, switched by Apple's gmux — and that pair is a
known source of trouble for a Linux *desktop* install. A node has no desktop: nothing renders, nothing
switches, and the problem does not arise. If you install a desktop environment on one of these, it can.

**The battery.** A laptop that has sat plugged in for years may have a swollen or dead battery. It will
still run as a node on mains power, but check it before you put it somewhere you cannot see it:

```bash
cat /sys/class/power_supply/BAT0/health /sys/class/power_supply/BAT0/cycle_count
```

## If the install fails

Read what it says: the installer names the step, the reason, the log and the way back, and on a disk
failure it prints the kernel's own words rather than asking you to go and find them. Then
[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md), which is organised by what is on your screen.

The one worth knowing before you start: **`FAILED: downloading the database image` with
`failed commit on ref "layer-sha256:…"` is the disk**, not your network. Go back to §0.5.

## When you are done

`planetai status` on the machine, or from your laptop over SSH. The node is now a box that stays on,
which is what it always wanted to be.

---

*Second node on record: `mahon1`, Menorca — a 2015 MacBook Pro, Linux Mint 22.3, live 10 September 2026.
It took several evenings, six of which were our bugs and one of which was its SSD. Every one of those
six is fixed and has a test; the seventh is why §0.5 is where it is.*
