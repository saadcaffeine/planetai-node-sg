# Updating
<!-- checked: v0.91.0 -->

One command brings the node to the published release. Your settings, readings, backups, exports and the packs you
added stay.

```bash
planetai update
```

## What it does

1. **Backs up the database**, and stops if that fails. It also copies `.env` and `config/rules.yml` aside with
   `.before-update` on the end.
2. **Gets the new code.** A node installed from the tarball downloads it from `planetai.fab.city/node0/get`, checks
   its checksum and signature, and unpacks it over the folder. A git checkout fetches tags and pulls. If the new
   version ships a core pack with the same id as a wild pack on the node (one `planetai packs add` fetched), it
   stops here and names it; delete the wild copy with `rm -rf packs/<id>` and update again.
3. **Applies `init.sql`**, which is idempotent.
4. **Adds new settings** from `.env.example` to `.env` with their defaults, under a dated marker. Nothing you set is
   overwritten, with one exception: on a node that lists its packs in `PACKS_ENABLED` (in `.env` or in Set up), it
   adds each pack that took over something the node already did, so nothing is lost: `home-assistant`,
   `smartcitizen`, `airgradient`, `purpleair`, `air-quality` and `bali-air-dispatch` where their switch is on, the
   pack of each issue `NODE_ISSUES` names (`water` brings `terrain`), and `things` and `eyes` always. It takes `trust`
   out, since it is core now, unless it was the only pack listed. An empty list is every pack and is left alone.
5. **Rebuilds and restarts**, and on a node with the Reticulum bridge on, fetches the bridge at the commit this
   release pins and rebuilds it; a bridge that does not build keeps running the one it had. Then it checks the database, the app, the readings, the views and the packs, prints the schema
   before and after, and ends on `updated. Nothing was lost:` with the counts of readings, alerts and actions. On the way it adds, once, the
crontab line that Install on Set up › Packs needs (`planetai packs cron`).
6. **Runs `planetai doctor`**, ending with **To finish setting up**. In a terminal it offers to do the first item,
   and to fetch the map if the node has none; from cron or an agent it only prints. A cross there never fails an
   update that has succeeded.

If it then says a pack needs libraries the image does not have, run `planetai packs install` and
`planetai restart`. If it says `config/rules.yml` changed, put any thresholds you had edited into a pack
([Packs](PACKS.md)).

## Updates are signed

The checksum and the signature prove different things. The SHA256 checksum is served from the same place as the
tarball, so it only proves the download arrived whole. The signature is made with a key that is not on the web
server: the node runs `ssh-keygen -Y verify` with signer `fabcity` and namespace `planetai-node`, against a key
written into the installer and `update.sh`. `planetai version` prints the key this node trusts:

```
  updates signed by  fabcity  SHA256:OrUQK/jsjNjpei1U8B5tyuEWY36/gwYWXrgVF+5ycIY
```

When a check fails, the install or update stops before touching the node:

| it prints | what to do |
|---|---|
| `this download is not signed by the PLANETAI release key. Nothing was installed and nothing on this machine changed.` | try once more on a network you trust (a captive-portal WiFi can serve its own page instead of the file); if it says it twice, stop and tell us, as [SECURITY.md](../SECURITY.md) says |
| `the download does not match its published checksum. Try again; if it repeats, tell us.` | the download was cut or altered on the way |
| `could not fetch …/planetai-node.tar.gz.sig, so it is not known who built this download.` | that one file is missing, usually a partial deploy; wait and try again |
| `no ssh-keygen on this machine, so it cannot be checked who built this download.` | `sudo apt-get install -y openssh-client`, or `sudo pacman -S openssh` on Arch; every Mac has it |

A refused update is the node doing its job. Do not look for a way past it.

Every install and update writes `.planetai-release`, `signed` or `unsigned` with the time, and on a tarball node
`planetai doctor` has the row `release signature verified on last update`. `PLANETAI_UNSIGNED=1` accepts an
unsigned tarball and says so in red; it is for a throwaway test tarball, never a node anybody relies on.

## If it fails

**The backup failed, so it stopped.** On purpose. `planetai backup` alone shows why, and `planetai storage` where it
is writing.

**`git pull failed`** on a git checkout: local changes. It names the changed files and any commits that exist only
here. `git stash`, then update again. The node's own files (`.planetai-*`, `.env.before-*`) are in `.gitignore`;
untrack them if they were ever committed.

**`already at the newest commit`** on a git checkout: nothing moved. If the release channel already serves a commit
this branch lacks, it says so; try again shortly.

**`app answering ✗`** or `something is off`: run `docker compose logs app | tail -40` and send it to us.

## Rollback

On a git checkout:

```bash
git checkout v0.82.0      # the tag you want back
docker compose build app  # the code is inside the image; a restart alone keeps the new one
planetai restart
planetai restore backups/<node>-<date>.sql.gz    # only if the schema went forward and you need the old shape
```

A tarball node has no tags: point it at an earlier release on the mirror and update.

## Reading from the mirror

Every release is published twice, on the site and as a GitHub Release, from the same bytes with the same signature.
`PLANETAI_GET` points an update or an install at the GitHub copy, with the same checks:

```bash
PLANETAI_GET=https://github.com/fabcity/planetai-node/releases/download/<tag> planetai update
PLANETAI_GET=https://github.com/fabcity/planetai-node/releases/download/<tag> \
  bash -c "$(curl -fsSL https://planetai.fab.city/install)"
```

`<tag>` is a release such as `v0.82.0`. Releases from v0.61 on are signed, and the node refuses an older one. Use the
mirror when the site is unreachable, or when you would rather fetch from a history anyone can read.
