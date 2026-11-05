# Where the data lives
<!-- checked: v0.91.0 -->

`planetai storage` shows all of this on one screen. `GET /storage`, for a token or this machine at every
`SHARE_LEVEL`, gives the sizes as numbers: the database, `out/`, the backups (and what `BACKUP_KEEP` days of dumps
will take), the exports, the free space on the disk `out/` is on, and `days_left`, how long that lasts at the last
seven days' rate of readings.

| what | where | NAS? | who else gets it |
|---|---|---|---|
| live database | a local disk on the node | no | nobody |
| backups | `BACKUP_DIR`, or pulled by a NAS | yes | an rclone remote |
| daily exports (open data) | `exports/<node>/` | yes | IPFS, a parent node, the Index, anyone |
| artifacts (images, briefs, the kept map in `out/ground/`, the workbench's firmware in `out/firmware/`) | `out/` | yes | whoever you send them to |
| the household's pictures | `CAPTURES_DIR` (`./out/captures`); `planetai storage set captures <dir>` | yes, as files | nobody: no export, parent or dump carries them |

## The database stays on a local disk

Postgres needs `fsync` and file locking, and SMB and NFS, what a NAS speaks, do not honour them reliably. A
database on a NAS can corrupt on a power cut, and you find out at a restore. A NAS path that
is not mounted is worse still: it becomes an empty local folder with the NAS's name.

So the node keeps the database and the NAS keeps a copy of every dump. If the node's machine dies,
`planetai restore` on any machine brings it back to last night in a minute.

`DATA_DIR=/path` in `.env` moves the database to another internal disk or partition: back up, stop, edit, start,
restore. A USB drive that goes to sleep is not one.

## Backups

Every night at 03:17 `backup.sh` dumps the database, checks the file is a valid gzip with a readings table, keeps
`BACKUP_KEEP` days (30), and writes `LAST_OK`. If `BACKUP_DIR` is under `/Volumes`, `/mnt` or `/media` and the
drive is not mounted, it refuses rather than write to a local folder with the drive's name. `planetai storage set
backups <dir>` and `planetai storage set keep <days>` change the two.

```bash
planetai backup                                          # now
planetai restore backups/bayu-ungasan-2026-09-05.sql.gz  # replaces the database; takes a safety backup first
```

`planetai restore` asks you to type the node's name before it replaces anything.

A dump holds readings, sensors, alerts, alert events and actions, and the rows of what the house learned, the
things it keeps and its pictures. The picture files themselves stay in `CAPTURES_DIR`. A dump does not hold the
rows of the `settings` table (the dashboard's values, a Telegram token saved from Set up): `backup.sh` leaves them
out so no token travels to a NAS or a remote. After a restore the node runs on `.env`; `planetai telegram`
reconnects the bot if it was set from the dashboard. Alert texts name places and numbers, so treat every dump and
every remote as private anyway.

## A NAS that pulls

Better than mounting the NAS on the node is letting the NAS fetch the dumps. The node serves `/backups` to a
`BACKUP_TOKEN`, which reads backups and nothing else; the admin token works there too, but give the NAS the backup
token. On the NAS a small script in a container asks every hour,
fetches what it lacks, and opens each dump to check it is a database before keeping it. Nothing is deleted there,
and the node holds no NAS credentials and mounts nothing. This is how node #1 is backed up.

`tools/nas/` has the script and its compose file. On the NAS:

```bash
# put pull.py, docker-compose.yml and .env in one folder; write the node's token into .env
docker compose -p planetai-backup up -d
docker logs -f planetai-backup             # "bayu-ungasan: 0 new, 3 dumps held"
```

`planetai ui` on the node prints the token; `planetai storage` says only whether it is set. The script also
collects `/exports`, which only `SHARE_LEVEL=open` serves without a token. At the default, `off`, the dumps still
arrive but the exports are refused, and the log shows `pull failed: HTTPError` instead of the line above.

## Off the machine

`BACKUP_REMOTE` is an [rclone](https://rclone.org) destination: S3, Backblaze B2, Cloudflare R2, Google Drive,
Dropbox, SFTP, WebDAV, Nextcloud. After each backup the last three days of dumps and all exports are copied there.

```bash
brew install rclone && rclone config
planetai storage set remote r2:planetai/bayu-ungasan
```

B2 or R2 cost cents a month for a node's lifetime of dumps. Drive works, but it is a person's account, not
infrastructure. rclone's `crypt` backend encrypts the copy if you want that.

## The export

`/export?day=YYYY-MM-DD`, written every night to `exports/<node>/`: the hourly mean, min and max per sensor and
metric, the Index cells, the alerts (first line only), ρ, and, while the `things` pack is on, the household's offers (class, name,
condition and count at the cell). Your own sensors are named by role (`indoor-1`, `outdoor-2`), never by device id. The position
is the centre of the node's resolution-8 cell, not its point. No raw rows, no tokens, no chat ids. CC BY 4.0,
stated in the file.

This is what a parent node, the Index, a researcher or the commons should receive. The node keeps the raw readings
and gives away the aggregate.

Its first key is `"schema": "export-v0"`. An export is written once, added to IPFS and addressed by its content
for good, so a reader opening one years later cannot ask the node what shape it was; the file says. The version
changes only on a breaking change.

## IPFS

IPFS is content-addressed and public, so only the export goes there, never the database or a dump. Nothing
persists unless it is pinned: the node pins its own exports, and they live as long as the node does. To keep them
beyond one machine you need a second node pinning yours, or a pinning service.

```bash
planetai ipfs            # starts Kubo (low-power profile), turns publishing on
planetai backup          # publishes yesterday now
cat exports/bayu-ungasan/CIDS.txt
```

Anyone can then fetch `ipfs://<cid>`. Turn it on when a second node or a partner wants the data; with one
contributor there is nothing to share yet.
