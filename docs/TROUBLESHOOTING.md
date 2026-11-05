# When it goes wrong
<!-- checked: v0.91.0 -->

Each entry starts from what is on your screen, then says how to check it and how to fix it. Many of the faults
people met early on are fixed in the current release, so the first thing to try is almost always the install line.
It fetches a fresh installer rather than running the one on your disk, so it works even when the node is broken,
and on an existing node it updates in place and keeps your `.env`:

```bash
curl -fsSL https://planetai.fab.city/install | bash
```

If you are still stuck, send us three things at info@fab.city: the last screen, the log
(`~/planetai/.planetai-setup.log`), and the output of `planetai doctor`.

## During the install

### `FAILED: downloading the database image` with `failed commit on ref "layer-sha256:…"`

The download arrived and could not be written, so this is the disk. Nothing about your network, Docker or the
installer will change it.

**Check.** The installer prints the kernel's own words under the failure. Lines like
`EXT4-fs … I/O error … writing to inode` or `ata1.00: failed command: WRITE FPDMA QUEUED` settle it. To test the
drive yourself, write 3 GB and read the kernel log:

```bash
dd if=/dev/zero of=~/writetest bs=1M count=3000 conv=fsync status=progress; rm -f ~/writetest; sudo dmesg | tail -20
```

**Fix.** Only on a first install, on a machine where Docker runs nothing else: clear Docker's image store, which an
earlier failure can leave inconsistent. `/var/lib/docker` holds every image, container and volume on the machine,
the node's database included once it exists, so never run this on a node that has recorded anything; back up first
and remove only the failed image (`docker image rm <image>`) instead. Stop the socket as well as the service, or the
daemon wakes up while the folder is being deleted:

```bash
sudo systemctl stop docker.socket docker.service && sudo rm -rf /var/lib/docker && sudo systemctl start docker
```

If it fails again, or the write test shows `I/O error` or `hard resetting link`, replace the drive.

> **Careful.** A clean SMART report does not clear the drive. One tester's SSD reported `overall-health PASSED`,
> `Reallocated_Sector_Ct 0`, `Current_Pending_Sector 0`, `UDMA_CRC_Error_Count 0` and an empty error log, and it was
> the SSD. Those counters measure dead cells and cable corruption. A controller that stops answering during a long
> write trips none of them; it shows as `exception Emask 0x20` with `SErr 0x0` and repeated `hard resetting link`,
> which reads like a host-side fault and is not.

### Nothing new on the screen for a long time

**Check.** The installer prints a named step, its elapsed time, and a heartbeat at least every ten seconds. On a
fresh Linux machine the container runtime step installs Docker, a download of several hundred MB, and up to twenty
minutes there is normal.

**Fix.** If there is no output at all for minutes, you are running an old installer. Stop it and run the install
line at the top of this page.

### `apt` errors about `trixie`, or held broken packages, on Linux Mint or another Ubuntu derivative

Docker's own installer reads these as Debian and adds a repository for a release that does not match.

**Fix.** Run the install line again. The current installer removes a mismatched Docker repository and uses
Docker's Ubuntu repository instead. To clear it by hand:

```bash
sudo rm -f /etc/apt/sources.list.d/docker.list && sudo apt update
```

### `permission denied` on `docker.sock`, or `Docker is installed but this user cannot reach it`

The daemon is running, and your shell is not in the `docker` group yet. A group you were just added to does not
apply to a shell that was already open.

**Check.** `systemctl status docker` says `active`, and `id -nG` does not list `docker`.

**Fix.** The installer carries on under the new group by itself. If it stops here anyway, start a new session,
then run the same line again:

```bash
newgrp docker
```

### `port 8080 is already in use on this machine`

**Check.** The installer names the program holding the port.

**Fix.** Set `APP_PORT` to a free port (`8081`, for example) in `~/planetai/.env` and run the install again.

### `a database from an earlier node is still on this machine`

You removed a node, or deleted its folder, and installed again. The Docker volume outlives the folder, and every
node's compose project is `planetai` whatever the folder is called, so the new install would re-attach the old
database with a password it does not know. The installer refuses and names the two ways out.

**Fix.** To keep that data, put the earlier `.env` back in the folder and run the install again. To start clean,
`docker volume rm planetai_db` (this deletes the old node's readings), then run it again.

If the doctor on an installed node shows `app logs in to the database` with a cross, it is the same mismatch;
`planetai logs` then says `password authentication failed`.

### `No container runtime can be installed on <OS>`

The OS is below every runtime's floor. The preflight prints what this hardware is and two routes, Linux in a
virtual machine or Linux on the metal. See [Platforms](PLATFORMS.md) and [Revive a laptop](REVIVE_A_LAPTOP.md).

### `this download is not signed by the PLANETAI release key`

Nothing was installed. Try once more on a network you trust, and if it says it twice, stop and tell us. Every
refusal and what it means is on [Updating](UPDATING.md#updates-are-signed).

## After the install

### `planetai: command not found`

**Fix.** Open a new terminal. The installer adds `~/.local/bin` to the PATH of new terminals, not of the one it
ran in.

### `This machine already runs a node` when you did not expect it

`~/planetai` holds a `VERSION` file or a git checkout, so the installer treats a re-run as an update and keeps your
`.env`. That is how a node keeps its name and place across updates.

**Fix.** `planetai setup` offers to update it, reconfigure it, make sure it is running, or remove it. For a new
node in the same place, remove the old one first. To run a second node somewhere else instead:

```bash
PLANETAI_HOME=~/somewhere bash -c "$(curl -fsSL https://planetai.fab.city/node0/install)"
```

### `there is no planetai <word> in this node`

The command arrived in a later release than this node runs. The message names the node's version.

**Fix.** `planetai update`.

### `mesh packets arriving` with a cross, or the radios went quiet

The gateway radio is not passing the mesh to the node.

**Check.** `planetai radio doctor` looks at the radio side, and `out/radio.log` is the gateway's own log. If the
radio was unplugged, the log says `the radio on <port> went away; exiting so the service starts the gateway again`.

**Fix.** The gateway runs as a service, and when its radio is unplugged it exits so the service starts it again.
Plug the radio back in and the mesh returns on its own within about half a minute. If the gateway was never
installed as a service, `planetai radio gateway --port <port> --install` makes it one, and `planetai meshtastic`
prints the settings for the gateway radio. The rest is on [Radios](MESHTASTIC.md).

## Removing a node

### `planetai remove` does nothing, or says there is no `planetai remove`

Your copy is older than the current remover, or the folder is damaged. Nothing was removed.

**Fix.** Use the released remover instead of the one on your disk. It works when piped, which is how a broken node
can reach it:

```bash
curl -fsSL https://planetai.fab.city/remove | bash
```

If the node will not start at all, add `--purge`. It runs none of the node's own code, finds the containers, the
four volumes, the folder, the symlink and the crontab line itself, asks once, and then reports what is actually
left:

```bash
curl -fsSL https://planetai.fab.city/remove | bash -s -- --purge
```

To do it by hand, step by step:

```bash
docker ps -aq --filter label=com.docker.compose.project=planetai | xargs -r docker rm -f; docker volume ls -q | grep '^planetai_' | xargs -r docker volume rm; rm -rf ~/planetai ~/.local/bin/planetai; crontab -l 2>/dev/null | grep -vE 'planetai-(backup|packs)' | crontab -; hash -r
```

Then this prints nothing at all:

```bash
ls -d ~/planetai ~/.local/bin/planetai 2>/dev/null; docker volume ls -q | grep planetai_; docker ps -a --filter label=com.docker.compose.project=planetai --format '{{.Names}}'
```

### `planetai status` still answers after you removed it

Either the removal did not happen (see above), or your shell still remembers the path to a command that is gone.

**Fix.** `hash -r`.

### `Stopping 'docker.service', but its triggering units are still active: docker.socket`

A warning, and your command worked. `docker.socket` stayed armed, so anything touching the socket can wake the
daemon again, which matters only if you are deleting `/var/lib/docker` at the time. Stop both together, as the
first entry on this page does.
