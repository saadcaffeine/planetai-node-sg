# Updating
<!-- checked: v0.80.10 -->

```bash
planetai update
```

In order: back up the database (and refuse to go on if that fails); fetch tags and pull, or download the tarball if the
node has no repository access, check its checksum **and its signature**, and stop dead if either is wrong; apply
`init.sql`, which is idempotent, to the live database; merge new keys from
`.env.example` into `.env` under a dated marker; rebuild the image; restart; run the doctor; report the schema before
and after.

If the version arriving ships a core pack with the same id as a wild pack on the node (one `planetai packs add`
fetched), it stops after the backup and before anything moves, names the wild copy and where it came from, and asks
for it to be deleted (`rm -rf packs/<id>`); run the update again and the core pack takes its place.

`update.sh` runs from a copy of itself, because pulling rewrites the file bash is reading and it would otherwise continue
from a random offset in the new file.

## Updates are signed

Since v0.61 the tarball arrives with a signature, and a node checks it before it unpacks anything. If a node refuses an
update, **that is the node doing its job** — it means the download was not signed by the key the node trusts, and the
right response is to stop, not to work around it.

```
xx this download is not signed by the PLANETAI release key. Nothing was installed and nothing on this machine changed.
```

Nothing on the machine changed when you see that. Try once more, in case you were on a captive-portal wifi that served
its own page instead of the file. If it says it twice, do not go looking for a way past it — say so. `SECURITY.md` is
how.

The checksum and the signature are not the same check. The checksum is served from the same place as the tarball, so it
only tells you the download arrived whole; whoever can write one can write the other. The signature is made with a key
that is not on the web server. `planetai version` prints the fingerprint your node checks against, and `planetai doctor`
has a row saying whether the last update was verified (on a node installed from the tarball; a git checkout has no such row).

Two other things it can say, both with the fix attached:

**`no ssh-keygen on this machine`** — a bare container or a very thin Linux install. `sudo apt-get install -y
openssh-client`, or `sudo pacman -S openssh` on Arch. Every Mac already has it.

**`could not fetch … planetai-node.tar.gz.sig`** — the site is reachable but that one file is not. Usually a partial
deploy. Wait, then try again.

There is an escape hatch, `PLANETAI_UNSIGNED=1`, which accepts an unsigned tarball and says in red that it did. It is
for building and throwing away a test tarball on a dev machine. It is not for a node anybody relies on, and `planetai
doctor` will show that the node took one.

## If it fails

**`git pull failed`**: local changes. The update clears `.DS_Store` itself before it pulls. When it fails, it names
the offending files (up to ten) and any commits that exist only here but not on origin. If you edited files in the
node folder, `git stash`, then update again. Operational files a node writes (its update log and its
before-copies, `.planetai-*` and `.env.before-*`) are in `.gitignore` now — untrack them if they were
committed, never commit them.

**`backup failed — not updating`**: the update refused on purpose. `planetai backup` alone shows why; `planetai storage`
shows where it is trying to write.

**`app answering ✗`**: `docker compose logs app | tail -40`. Paste it.

**no-op pull (nothing moved)**: the script asks the channel `/VERSION`. If the commit served there has not landed on
this branch yet, it says "already at the newest commit on $branch ($here), but the channel serves $latest, which has
not landed on this branch yet — it is still shipping; try again shortly". Otherwise it confirms you are up to date.

## Rollback

```bash
git checkout v0.76        # or whichever tag you want back
docker compose build app  # the code is inside the image; a restart alone keeps running the new one
planetai restart
planetai restore backups/<node>-<date>.sql.gz    # only if the schema went forward and you need the old shape
```

A node installed from the tarball has no tags to check out. Point it at an earlier release on the mirror (below) and
update: `PLANETAI_GET=https://github.com/fabcity/planetai-node/releases/download/<tag> planetai update`. The same
checksum and signature checks apply.

## Testers without repository access

`update` downloads `planetai.fab.city/node0/get/planetai-node.tar.gz`, checks its checksum and its signature, and
unpacks over the folder keeping `.env`, backups, exports and packs. Publish a new one with `tools/release.sh`, which
builds it, signs it, commits it in the site repo, deploys, and mirrors the same three files, with `VERSION`, to a
GitHub Release.

### Reading from the mirror instead

Every release is published twice, from the same bytes with the same signature. `PLANETAI_GET` points a node at the
other copy — the site serves the files under `/get`, a GitHub Release serves them flat, and the same stub reads either:

```bash
PLANETAI_GET=https://github.com/fabcity/planetai-node/releases/download/<tag> \
  bash -c "$(curl -fsSL planetai.fab.city/install)"
```

`<tag>` is the release you want, `v0.72.1` for example. The first signed release is v0.61; v0.60 never shipped.

Useful when the site is unreachable, and useful when you would rather fetch from somewhere with a history anyone can
read. The signature is what makes the two copies the same artefact rather than two things that look alike.
