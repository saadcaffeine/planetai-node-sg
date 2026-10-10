# Where the data lives
<!-- checked: v0.80.10 -->

`planetai storage` shows all of this on one screen. `GET /storage`, for a token or this machine at every
`SHARE_LEVEL`, gives the sizes as numbers: the database, `out/`, the backups (and what `BACKUP_KEEP` days of dumps
will take), the exports, the free space on the disk `out/` is on, and `days_left`, how long that lasts at the last seven days' rate of readings.

| what | where | NAS? | who else gets it |
|---|---|---|---|
| live database | a local disk on the node | no | nobody |
| backups | `BACKUP_DIR`, or pulled by a NAS | yes | an rclone remote |
| daily exports (open data) | `exports/<node>/` | yes | IPFS, a parent node, the Index, anyone |
| artifacts (images, briefs, the kept map in `out/ground/`) | `out/` | yes | whoever you send them to |

## The database stays on a local disk

Postgres needs `fsync` and file locking. SMB and NFS, what a NAS speaks, do not honour them reliably. The result is
not slowness: it is a database that corrupts on a power cut and you find out at a restore. There is also the trap this
project hit three times this week: a mount path that is not mounted becomes an empty local folder with the NAS's name.

So the mini keeps the database. The NAS keeps a copy of every dump. If the mini dies, `planetai restore` on any machine
brings it back to last night in a minute.

`DATA_DIR=/path` in `.env` moves the database to another **internal** disk or partition: backup, stop, edit, start,
restore. A USB drive that sleeps is not that.

## Backups

Nightly at 03:17, `backup.sh` dumps the database, checks the file is a valid gzip with a readings table, keeps
`BACKUP_KEEP` days (30), and writes `LAST_OK`. If `BACKUP_DIR` is under `/Volumes`, `/mnt` or `/media` and the drive
is not mounted, it refuses rather than write to a local folder with the drive's name.

```bash
planetai backup                                    # now
planetai restore backups/bayu-ungasan-2026-09-05.sql.gz  # replaces the database; takes a safety backup first
```

## A NAS that pulls (node #1's setup)

Better than mounting the NAS on the node: the NAS fetches the dumps. The node serves `/backups` behind a read-only
`BACKUP_TOKEN` (separate from the admin token), and `/exports` to anyone only at `SHARE_LEVEL=open`; at the default,
`off`, `/exports` needs a token too. On the NAS, one 120-line script in a small container asks every hour and fetches
what it lacks. It opens each dump to check it is a database before keeping it.
Nothing is deleted there. The node holds no NAS credentials and mounts nothing.

`tools/nas/` has the script and compose file. On the NAS:

```bash
# put pull.py, docker-compose.yml and .env in one folder; write the node's token into .env
docker compose -p planetai-backup up -d
docker logs -f planetai-backup             # "bayu-ungasan: 0 new, 3 dumps held"
```

`planetai ui` on the node prints the token (`planetai storage` says only whether it is set). At `SHARE_LEVEL=off`
`pull.py` still fetches the dumps, but it asks for `/exports` without the token, is refused, and logs `pull failed:
HTTPError` where the line above should be: exports and the earth results are not collected until that is fixed.
Node #1's dumps have been on TX-NAS-BALI at `/volume2/docker_1/agentic-os/backups/planetai/bayu-ungasan/` since 5 September 2026, collected hourly.

## Off the machine

`BACKUP_REMOTE` is an [rclone](https://rclone.org) destination: S3, Backblaze B2, Cloudflare R2, Google Drive,
Dropbox, SFTP, WebDAV, Nextcloud. After each backup the last three days of dumps and all exports are copied there.

```bash
brew install rclone && rclone config
planetai storage set remote r2:planetai/bayu-ungasan
```

B2 or R2 cost cents a month for a node's lifetime of dumps. Drive works but is a person's account, not infrastructure.
Dumps hold readings, sensors, alerts, alert events and actions. They do not hold the rows of the `settings` table (the dashboard's
values, a Telegram token saved from Set up): `backup.sh` excludes them so no token travels to a NAS or a remote. After
a restore the node runs on `.env`; `planetai telegram` reconnects the bot if it was set from the dashboard. Alert texts
name places and numbers, so treat every dump and every remote as private anyway. rclone's `crypt` backend encrypts if
you want that.

## The export

`/export?day=YYYY-MM-DD`, written nightly to `exports/<node>/`. Hourly mean, min and max per sensor and metric; the
Index cells; alerts (first line); ρ. Your sensors are named by role (`indoor-1`, `outdoor-2`), not device id.
The position is the centre of the node's resolution-8 cell, not its point (since v0.73; earlier exports carry three decimals). No raw rows, no tokens, no chat ids. CC BY 4.0, stated in the file.

This is what a parent node, the Index, a researcher or the commons should receive. The node keeps the raw and gives
away the aggregate.

Its first key is `"schema": "export-v0"`. That matters more here than anywhere else on the node: an export is written
once, added to IPFS and addressed by its content forever, so a reader opening one in 2031 cannot ask the node that
wrote it what shape it was. The file says. `tools/check_wire.py` holds the top-level key list in
`tests/data/wire/export-v0.json`, and a key cannot be added or dropped without editing that file in the same commit.
A version bumps only on a breaking change, and the bump is a `docs/decisions/` entry.

## IPFS

Content-addressed and public. So only the export goes, never the database or a dump. And nothing persists unless
pinned: the node pins its own exports, which live while the node does. Durability beyond one machine needs a second
node pinning yours, or a pinning service.

```bash
planetai ipfs            # starts Kubo (low-power profile), turns publishing on
planetai backup          # publishes yesterday now
cat exports/bayu-ungasan/CIDS.txt
```

Anyone can fetch `ipfs://<cid>`. Turn this on when a second node or a partner wants the data; with one contributor
there is nothing to share yet.
