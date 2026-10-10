# When it goes wrong
<!-- checked: v0.80.10 -->

Every entry here is something that happened to a real tester, not something we imagined. They are
ordered by **what is on your screen**, because that is what you have.

**Most of these were our bugs and are fixed.** If you hit one, your node is from before the fix. The
first thing to try is almost always to get the current version — and the line below works even when the
node itself is broken, because it fetches a fresh installer rather than running the one on disk:

```bash
curl -fsSL planetai.fab.city/install | bash
```

If you are stuck after reading this, send us three things: the last screen, the log
(`~/planetai/.planetai-setup.log`), and the output of `planetai doctor`. Write to **info@fab.city**.

---

## The install stops

### `FAILED: downloading the database image` … `failed commit on ref "layer-sha256:…"`

**This is the disk.** The download arrived and could not be written. Nothing about your network,
your Docker, or the installer will change it.

The installer prints the kernel's own words underneath, and they settle it — lines like
`EXT4-fs … I/O error … writing to inode`, or `ata1.00: failed command: WRITE FPDMA QUEUED`.

Two things to do, in order:

1. **Clear Docker's image store.** An earlier failure can leave it inconsistent, and it holds nothing
   of yours before a first install. Stop the socket as well as the service, or the daemon wakes up
   again while the folder is being deleted:

   ```bash
   sudo systemctl stop docker.socket docker.service && sudo rm -rf /var/lib/docker && sudo systemctl start docker
   ```

2. **If it fails again, it is the storage path** — the drive, its cable, or the controller.

> **A clean SMART report does not clear the drive.** We learned this the expensive way. A tester's SSD
> reported `overall-health PASSED`, `Reallocated_Sector_Ct 0`, `Current_Pending_Sector 0`,
> `UDMA_CRC_Error_Count 0` and an empty error log — and it was the SSD. Those counters measure dead
> cells and corruption on the cable. A controller that stops answering during a long sustained write
> trips none of them. On the host it appears as `exception Emask 0x20` with `SErr 0x0` and repeated
> `hard resetting link`, which reads like a host-side fault and is not. Small writes keep working
> throughout, so `apt` looks fine while a 162 MB image pull dies.

The honest test is a sustained write, not a health summary:

```bash
dd if=/dev/zero of=~/writetest bs=1M count=3000 conv=fsync status=progress; rm -f ~/writetest; sudo dmesg | tail -20
```

If that produces `I/O error` or `hard resetting link`, replace the drive. Nothing else will help.

### It has printed nothing for a long time

A current node prints a named step, an elapsed time, and a heartbeat at least every ten seconds. Twenty
minutes of silence was a real bug and is fixed — if you are seeing it, you are on an old installer;
fetch a fresh one with the line at the top of this page.

Docker itself is a large download on a fresh Linux machine. Up to twenty minutes at the runtime step is
normal; twenty minutes with *no output at all* is not.

### It asked for your password and then nothing happened

`sudo` cannot ask for a password from a background job — it gets stopped, and the prompt lands in the
log where nobody sees it. Fixed: the installer now asks once, in the foreground, before any step that
needs it. If you are being asked invisibly, update.

### On Linux Mint: `apt` errors about `trixie`, or held broken packages

Mint identifies itself in a way that made Docker's own installer read it as Debian and add a repository
for a release that does not match. Fixed — the installer now reads `UBUNTU_CODENAME` and takes Docker's
documented Ubuntu path. To clear a mismatched repository left by an earlier attempt:

```bash
sudo rm -f /etc/apt/sources.list.d/docker.list && sudo apt update
```

### `the Docker service did not come up`, but `systemctl status docker` says it is active

Three different things look the same from outside, and the installer now tells them apart: the daemon
is down, the socket is there but you are not in the `docker` group, or the daemon is genuinely
crash-looping. If it is the group, the fix is to start a new session — group membership does not apply
to the shell you are already in:

```bash
newgrp docker
```

A node was once called dead for thirty-seven minutes while it was running perfectly. That was ours.

---

## Removing a node

### `planetai remove` prints the logo and then nothing

Your node is from before the fix. `remove` counted the readings first, and on any node whose database
container was not running that command failed, which ended the script before it asked you anything.
**Nothing was removed** — not the folder, not the volumes, not the `.env`.

Use the released remover instead of the one on your disk:

```bash
curl -fsSL planetai.fab.city/remove | bash
```

### `there is no planetai remove in this node`

Your copy predates the command. Same answer — the line above fetches a remover that has it.

### The remover listed everything, then said `no terminal here, so nothing was removed`

Fixed. It was testing the wrong thing: piping into `bash` makes stdin a pipe, while every question it
asks reads `/dev/tty`, which was available the whole time. Fetch it again; the current one works when
piped, which is the only way a broken node can reach it.

### You removed the node, installed again, and the old node came back

Same name, old readings, same place. This is the one that cost the most time.

The Docker volume outlives the folder. The compose project is pinned to `planetai` in docker-compose.yml
whatever the folder is called, so a fresh install — in the same folder or a new one — **re-attaches the
old database**. It is not bad luck; it is the default. Since v0.80.2 the installer refuses at that point
and names the two ways out; before it, the new install generated a password the old volume did not know
and the app was locked out while every check said the database was fine.

The current remover deletes volumes by name and then checks. If you are cleaning up after an old one:

```bash
curl -fsSL planetai.fab.city/remove | bash -s -- --purge
```

`--purge` runs none of the node's own code — it finds the containers, the four volumes, the folder, the
symlink and the crontab line itself, asks once, and then reports what is *actually* left rather than
what it meant to do. Use it when the folder is damaged or the node will not start.

By hand, if you prefer to see every step:

```bash
docker ps -aq --filter label=com.docker.compose.project=planetai | xargs -r docker rm -f; docker volume ls -q | grep '^planetai_' | xargs -r docker volume rm; rm -rf ~/planetai ~/.local/bin/planetai; crontab -l 2>/dev/null | grep -v planetai-backup | crontab -; hash -r
```

Then this should print nothing at all:

```bash
ls -d ~/planetai ~/.local/bin/planetai 2>/dev/null; docker volume ls -q | grep planetai_; docker ps -a --filter label=com.docker.compose.project=planetai --format '{{.Names}}'
```

### `planetai status` still answers after you removed it

Two causes. Either the removal did not happen (see the two entries above), or your shell has cached the
path to a command that is gone — `hash -r` clears that.

### `Stopping 'docker.service', but its triggering units are still active: docker.socket`

A **warning, not a failure**. Your command worked. It means `docker.socket` stayed armed, so anything
touching the socket can wake the daemon again — which matters if you are deleting `/var/lib/docker` at
the time. Stop both together, as the command in this page's first section does.

---

## Running

### `This machine already runs a node` when you did not expect it

`~/planetai` exists and contains a `VERSION` file or a git checkout, so the installer treats a re-run as
an update and keeps your `.env` on purpose — that is how your node keeps its name and place across
updates. `planetai setup` then offers to update it, reconfigure it, leave it running or remove it. If you
wanted a genuinely new node, remove the old one first (that choice, or above). To run a second node
somewhere else instead:

```bash
PLANETAI_HOME=~/somewhere bash -c "$(curl -fsSL planetai.fab.city/node0/install)"
```

### The port is busy

Set `APP_PORT` to something free in `~/planetai/.env` and run the install again. The installer refuses
rather than starting a node you cannot reach.

### A command exists in the docs but not on your node

The node tells you which version it is and what to do:

```
there is no `planetai <word>` in this node.
   this node is v0.41.2-xx. If somebody told you to run it, it arrived in a later release:
     planetai update
```

That is the expected answer, not a fault. Commands arrive in releases.

---

## For maintainers

### The site serves an older version than `main`

**A merge is not a release.** `/install`, `/preflight` and `/remove` read the published
`node0/get/VERSION`, take the commit it names, and fetch from exactly that commit — so a tester always
gets one self-consistent version, and an installer fix is live when somebody ships it, not when it
merges.

```bash
make released   # says whether the site is behind main
make ship       # rebuild the tarball, commit it, deploy
```

`make ship` refuses a commit CI has not vouched for, and fast-forwards a checkout that is merely behind.

### A release check that says the site is behind right after a deploy

`VERSION` is served with `max-age=300`, so for a few minutes some edges still answer from the old entry.
`make released` re-reads before declaring anything; a single `curl` may not.
