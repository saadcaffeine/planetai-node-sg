# arm64: the wall is down, now somebody has to plug one in

Two sentences, and the whole of this document is about keeping them apart:

1. **Every image a node pulls now exists for `linux/arm64`, and the database comes up on it.** Measured,
   and CI runs the real installer end to end on an arm64 runner every push.
2. **No Raspberry Pi, Jetson, reComputer or Spark has ever run a node.** Nobody has one going. The list in
   `docs/PLATFORMS.md` is empty.

A green architecture check is not a week in a cupboard. This is the plan that turns (1) into (2).

## The test plan — for Lars, or Fab Lab Bali

**The machine.** Raspberry Pi 5, **8 GB**. Not 4 GB: the container runtime's own floor is 4 GB and the node
measures 229 MiB across both containers, so 4 GB works on paper and leaves nothing for the page, the model
or a bad day.

**The disk, and this is the part people get wrong.** An **NVMe hat** or a **USB SSD**. *Not an SD card.*
Postgres fsyncs on every commit, and a node commits every few minutes for years; SD cards are not built for
that write pattern and die inside a year — usually by going read-only, which the preflight will tell you
about and the database will not survive. `docs/PLATFORMS.md` says the same thing, and it is the one line in
this document worth repeating to anybody who asks.

**The OS.** 64-bit Raspberry Pi OS. As of 15 September 2026 that is Debian Trixie 13. Docker's own
*Raspberry Pi OS* install page covers 32-bit only and points 64-bit users at the Debian instructions — the
installer already does the right thing here, but it is worth knowing before somebody follows a page that
talks about armhf and concludes the node needs one.

**The install.** The same line as every other platform. Nothing about it is Pi-specific:

```bash
curl -fsSL planetai.fab.city/install | bash
```

**The run.** Seven days. Leave it alone. The point is not whether it starts — CI answers that — but whether
it is still answering on day seven with a database that has grown, a disk that has been fsynced a few
thousand times and a room that got hot in the afternoon.

**What to report, on day seven:**

```bash
planetai doctor --json          # every check, and each failing one names its own fix
planetai status --json          # uptime, readings, the last report, the last alert
iostat -x 5 3                   # the disk, which is the thing most likely to be the story
vcgencmd measure_temp           # Pi-only: whether it throttled
docker stats --no-stream        # what the two containers actually took on this machine
```

Plus one sentence in plain words: did anything about it feel slow to a person standing in front of it.

**And the thing this replaces.** `data/platform_floors.yml`'s `node:` block carries the node's performance
numbers — 229 MiB, under 5% of a core, a report in 1.5 s — and every one of them was measured on amd64. The
block says so now. The day a seven-day report lands, those become arm64 numbers beside amd64 ones, and
`docs/PLATFORMS.md`'s empty table gets its first row. Until then nobody should quote them for a Pi.

## What CI does and does not prove

`install-smoke.yml`'s fourth `clean-linux` leg runs on `ubuntu-24.04-arm` against a **Debian 13 arm64**
userland. It runs the stranger's command with no terminal, asserts the installer reaches `install OK`, and
would fail if any image the node pulls stopped publishing arm64 — which is the specific regression worth a
gate, because the database image being single-arch is what cost a year.

It is not a Pi and the job name says so. There is no SD card, no 4 GB ceiling, no thermal throttling and no
seven days. Nothing in CI can find the failure this handoff is actually looking for.

## Two things found on the way, which the next person should not re-find

**The PGDG image would have corrupted every existing node, silently.** `FROM postgres:16` plus
`postgresql-16-postgis-3` is the image we would rather own, and it builds in two lines on arm64. It is also
Debian, so glibc, while what the node has always shipped is Alpine, so musl. A musl `initdb` writes
`datcollate='en_US.utf8'` and leaves `datcollversion` **blank** — musl reports no collation version — so
Postgres has nothing to compare and issues no warning. Opening a real node's data directory with the PGDG
build, 19 September 2026: it started, all 16 tables present, every query answered, and

```
ERROR:  item order invariant violated for index "s_name"
```

from `bt_index_check`. Every text index out of order, undetectable by the database's own check. This is why
the node runs a borrowed Alpine image rather than a Dockerfile of its own, and it is not a preference. The
image we build comes back the day a node's data directory starts life on glibc, and that day carries a
reindex for the nodes that already exist.

**A `cryptography` wheel SIGILLs on an old kernel, and this may or may not matter.** Building and running
the app container on arm64 on the machine this work was done on, the app died instantly with exit 132
(SIGILL) and no log. Bisected to `import mcp` → `import jwt` → `cryptography`'s Rust bindings:

```
cryptography 50.0.1   from cryptography.hazmat.bindings import _rust   →  Illegal instruction
cryptography 44.0.3   from cryptography.hazmat.bindings import _rust   →  ok
```

Reproduced on a clean `python:3.12-slim` with nothing else installed. That machine is Docker Desktop 23.0.5,
whose LinuxKit kernel is **5.15.49** — from 2022. Raspberry Pi OS Trixie ships 6.12 and Ubuntu 24.04 arm64
ships 6.8, so the reading was an old-kernel artifact rather than a Pi problem — **and the arm64 CI leg has
since said so.** It installs the whole node on `ubuntu-24.04-arm`: Docker in, `imresamu/postgis` pulled,
both images built, `db healthy`, `install OK — ci-clean, 7 steps in 53s`, and `/health` answering. So
`cryptography` is not the next wall, and `app/requirements.txt` needs no pin.

What it leaves behind is a gap worth keeping: `install OK` means seven steps finished and the database went
healthy, not that the app container is still alive — `docker compose up -d` returns when a container starts,
not when it works. An app image that builds and starts on a new architecture and then dies on its first
import would have passed. Every `clean-linux` leg now reads `/health` after the install for exactly that
reason, which is the check that would have caught the SIGILL had it been real.

It also bears on the node-identity spec (PR #93, not merged as this is written), which proposes adding
`cryptography` to `app/requirements.txt` directly. That spec's own stop condition asks whether it installs
on Menorca's architecture. It installs everywhere; whether it *runs* is the question, and this is the first
evidence either way.

## Podman, and what it would cost

`install.sh` detects Podman and refuses to install Docker over it, printing the two commands that give the
node what it needs — `podman-docker` for a `/usr/bin/docker`, and `podman.socket`. With those in place the
repository's **99 `docker` call sites** (57 in `bin/planetai`, 27 in `install.sh`, 13 in `update.sh`, 2 in
`backup.sh`) work unchanged, which is why nothing was refactored.

Nobody has run a node on Podman and no CI leg covers it, so the branch stops rather than proceeding. Making
it real is: one `install-smoke` leg on Fedora under rootless Podman, and then finding out which of those 99
calls Podman answers differently — bind-mount SELinux labels and `--network host` are the two usual ones.
That is a session, not an afternoon, and it should start with the CI leg failing.
