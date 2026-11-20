# SPEC: a node is a key, not a string

**Decided by Tomas on 5 November 2026, built on branch `node-identity-2026-11-05`.** Each node gets a unique ID: a
key pair made at first start, the ID a short hash of the public key, and everything the node sends upstream signed
with it. Upstream, the node is the owner of what it shares, not a person. The shared `AGGREGATE_TOKEN` stays as it
is: it says who may write; the key says who is writing.

This replaces the Phase 1 draft of 19 September (153f7cb), which nobody built. Three of its calls are overruled by
the 5 November decision and are marked below where they changed: the ID was the whole public key, a parent enrolled
each child by hand, and the token was to be retired after one release.

## 1 · What is wrong today

A child pushes hourly means to `POST /aggregates` and alert timestamps to `POST /events`. Both handlers check the
one `AGGREGATE_TOKEN` every child of that parent holds, then take `body["node"]`, a name the child declares about
itself, and write the rows under it (`sensors.sensor_id = "<name>/<sensor>"`, `events.child = <name>`). So any child
holding the token can push readings as a sibling, rewrite a sibling's ρ events, or invent a household. `NODE_NAME` is
free text, unique only inside `registry.json`, and that lists only the nodes that joined by pull request.

## 2 · The key and the ID

- **Ed25519**, through `cryptography`, now a direct dependency in `app/requirements.txt`. It was already in node #1's
  image, but only because a pack's google-auth pulled it in; a clean node did not have it. The host CLI stays Apple's
  stdlib Python 3.9 and never signs anything.
- **The private key is 32 random bytes in `.env`, as `NODE_KEY`** (64 hex characters). `install.sh` writes it on a new
  node and `update.sh` adds it to an existing one on its first update to this release, the way both already create
  `ADMIN_TOKEN` and `BACKUP_TOKEN`. The app derives the public key from it at start. An update runs the `update.sh`
  of the release it starts from (it copies itself before fetching), so a node updating from an older release gets
  `NODE_KEY` on the update after this one, or on `./update.sh` run once more; `planetai doctor` says which until then. `.env` is where the node keeps
  every other secret, it is gitignored, `update.sh` keeps it (and its `.env.before-update` copy is mode 600), and no
  surface prints it: `NODE_KEY` is not a settings key, so neither `/settings`, Set up nor `planetai config` lists it.
- **The ID is `base32(sha256(public key))`, the first 16 characters, lowercase**: 80 bits, `a`–`z` and `2`–`7`, short
  enough to read down a phone. The full public key travels beside it on every push, so the ID never has to carry the
  security on its own; a collision would need 2^80 tries against one known key. (19 Sep draft: the ID was the whole
  52-character key. Tomas asked for a short hash.)
- `NODE_NAME` stays the human label on the page, in the report and in `registry.json`.
- A node without `NODE_KEY` (a compose file started by hand, an `.env` from before this release that `update.sh` has not
  seen yet) runs as before: `/health` says `"node_id": null`, its pushes go unsigned, and `planetai doctor` names the fix.

## 3 · Where the key lives, how it is backed up and restored

The nightly dump leaves `.env` out, and so it leaves the key out: dumps travel (a NAS, an rclone remote), which is why
`backup.sh` already drops the `settings` table's data. Nothing here changes `backup.sh`.

So the key is backed up the way the database password already has to be: **a copy of `.env`, kept somewhere that is
not the backup share**, a password manager or a USB stick in a drawer. The docs say so on the install and updating
pages, and `planetai doctor` says it once a node has a key.

- **Restore on the same machine** (`planetai restore <dump>`): nothing to do, `.env` never moved.
- **Restore on a new machine**: put the old `.env` in the new folder before `install.sh`; the node keeps its ID, and its
  parent sees the same node.
- **A lost `.env` is a new node.** A fresh install writes a new key and the node has a new ID. Its parent refuses it
  under the old name (§5) with a sentence that says what to run there. If the node is in `registry.json`, its keeper
  runs `planetai hello` again, so the list carries the new key.
- **A copied `.env` is the same node twice.** Never copy one to start a second node.

## 4 · Where the ID shows

- `GET /health` gains `node_id` and `node_key` (the public key, base64). Both are public by design, and `/health`
  answers at every `SHARE_LEVEL`.
- **Set up › Sharing** opens with this node's ID, what it is for, and that losing `.env` loses it. On a parent, the
  same section lists the children it has pinned (§5), unlocked only.
- `planetai status` prints the ID. `planetai hello` puts the ID and key in the registry entry.

## 5 · Signing a push, and trust on first use

**The child signs** every up-link push. Bodies do not change: the identity rides in four headers, so a parent on an
older release ignores them and reads the body exactly as before.

```
X-Node-Id         the ID (§2)
X-Node-Key        the raw 32-byte public key, base64
X-Node-Ts         unix seconds, when it was signed
X-Node-Signature  base64( Ed25519_sign( "planetai-node-v1\n" + route + "\n" + ts + "\n" + hex(sha256(body bytes)) ) )
```

`route` is the parent's route (`/aggregates`, `/events`), not the URL the child posted to, so a parent behind a
proxy that adds a prefix still verifies. The child hashes the bytes it is about to send and posts those bytes
(`content=`, not `json=`); the parent hashes the body it received. No canonical JSON to agree on.

**The parent checks the token first** (403/401 as today), then the signature: a bad signature, an ID that is not the
hash of the key, or a timestamp more than 10 minutes from the parent's clock is refused with 401 and a sentence. The
10-minute window is the whole replay defence: both routes are idempotent upserts, so a replay inside it writes the
same rows again. The first signed route that is not an upsert needs a nonce table.

**Then it pins.** A new table on the parent:

```sql
CREATE TABLE IF NOT EXISTS children (
  name       TEXT PRIMARY KEY,   -- the name its rows are stored under here: sensors '<name>/…', events.child
  node_id    TEXT UNIQUE,        -- NULL while it pushes unsigned
  public_key TEXT,
  first_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

One row per name, one name per key. On each push, after the token:

| the push | the row for its name | what the parent does |
|---|---|---|
| signed | none | pins it (trust on first use), unless `registry.json` lists that name with another ID: 409 |
| signed | same key | accepts, `last_seen` |
| signed | no key yet (it pushed unsigned before) | pins the key: the child has updated |
| signed | another key | **409**: "`<name>` is pinned here to node `<old id>` since `<date>`, and this push is signed by node `<new id>`. If `<name>` lost its key, the keeper of this parent runs `planetai children forget <name>` and its next push is pinned." |
| signed, its key pinned under another name | | **409**: "node `<id>` is pinned here as `<other>`, and now calls itself `<name>`. Set its NODE_NAME back to `<other>`, or run `planetai children forget <other>` on this parent." |
| unsigned | none, or no key | accepts, as before; the row records the name with no key (§7) |
| unsigned | has a key | **401**: "`<name>` signs its pushes here since `<date>`; an unsigned push under its name is refused." |

The child's push loops raise the parent's sentence instead of swallowing it, so it lands in `/health`'s `errors` and
in Set up › Machine, on the child, where its keeper reads it.

**Pinning makes the name the node's on that parent**, which is the 5 November ruling put into rows: everything a child
shares is stored under a name only its key can write to, so the owner of the rows is the node. The rows keep their
current shape and namespace; nothing already stored moves. (19 Sep draft: a parent accepted only children enrolled by
hand with `planetai children add`. Trust on first use needs no step on the parent until something changes.)

`GET /children` (admin token) lists the pins; `DELETE /children/{name}` (admin token) forgets one and keeps its rows;
`planetai children` and `planetai children forget <name>` are the same two on the CLI.

## 6 · The registry

`registry.json` entries gain `id` and `key`. `planetai hello` reads both from `/health` and puts them in the pull
request, and counts a changed key as a change worth sending. Anyone can prove a listed node: the ID is the hash of the
key, and the node signs with it. The ID is computable with the standard library, so the CLI and the tests check that
every listed `id` matches its `key`.

A parent reads the list hourly already (`check_registry`). `/nodes` now carries `id`. On first contact, a parent
refuses a signed child whose name the registry lists under another ID, so a listed name cannot be taken by trust on
first use. The two entries on main today (`bayu-ungasan`, `barcelona`) have no key yet; each gets one when its keeper
says hello again after updating. Nobody has to.

## 7 · Old children during the transition

The token is kept, so nothing forces anybody to update on a schedule.

- An old child (no key) pushing to a new parent: accepted as today, its name recorded in `children` with no key, and
  listed as "unsigned" in `GET /children` and Set up.
- A new child pushing to an old parent: the old parent ignores the headers and reads the same body.
- Once a name has signed, an unsigned push under it is refused, so nobody can fall back to the token to impersonate a
  node that has updated.
- Not built: a setting to refuse unsigned pushes outright. It belongs to the release after every listed node has a key.

## 8 · Shared maps (#377)

`push_maps` and `POST /place/maps/received` take the same three steps as the two routes above:

1. the child posts through `identity.post(PARENT(), "/place/maps/received", payload, PARENT_TOKEN())`, which signs the
   bytes it sends (`_post_parent` in main.py is the same call with the refusal raised);
2. the parent's handler takes the raw body (`raw: bytes = Depends(_raw_body)`) and calls `identity.admit` after the
   token check, before a `put` writes or a `delete` deletes;
3. the map's `owner` is the node: its ID, which the child also sends as the GeoJSON's `owner`, or its name when it
   pushes unsigned. Never a person, and never `body["node"]` unchecked.

A key refused by the parent (a 409, or a 401 that does not name the token) becomes the map's `share_error`, in the
parent's own sentence. The registry's list reaches `admit` as `identity.LISTED`, which `check_registry` sets, so a map
pushed before any aggregate cannot take a listed name either.

## 9 · Tests

`tests/test_identity.py`, a new suite (`tests/all` count moves by one):

1. the ID is 16 base32 characters, derived the same way in `app/identity.py` and in the CLI's stdlib Python;
2. sign and verify round trip; one byte of the body changed, another route, a wrong key, an ID that is not the
   key's hash, a timestamp 11 minutes old or 11 minutes ahead: each refused;
3. every row of the pin table in §5, on a fake cursor, including the refusal sentences naming both IDs;
4. every `registry.json` entry that has a `key` has the `id` that key hashes to;
5. the push functions post the bytes they signed, and the receive functions pass the raw body to `admit`.

## 10 · Calls made in building this, for Tomas to check

- `NODE_KEY` in `.env`, not a Docker volume (the 19 Sep draft's choice). A volume is one more thing to lose that no
  keeper knows about; `.env` is already the file a keeper must keep to restore the database at all.
- 16 base32 characters (80 bits) as "short".
- Unix seconds in `X-Node-Ts`, a 10-minute window, no nonce table.
- 409 for a changed key or a renamed key, 401 for a signature that does not verify.
- The registry outranks trust on first use when it lists the name with a key.
