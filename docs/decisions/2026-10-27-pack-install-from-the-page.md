# Installing a pack from the page

**Question.** Set up › Packs should list every pack a node could run: the core packs in `packs/`, and the wild packs
listed at fabcity/planetai-wild-packs. Each one says whether it is installed here and whether it is on, and a pack
that is not installed has an Install button. Installing a wild pack means fetching someone else's code onto a
household's machine. `planetai packs add` already does that on the host, but the app container cannot run it, and it
must not be able to write `packs/`. How does a press on the page become an install, who may press it, what does the
person see before the code arrives, and how does the page follow the install through a rebuild and a restart?

Asked by Tomas, 27 October 2026. Nothing is built until he approves this note.

## What is true today

- `packs/` is mounted read-only in the app (`docker-compose.yml`). `out/` is the one writable mount.
- `GET /packs` lists only the packs this node loads (`packs.manifests()` filters by `PACKS_ENABLED`). Set up draws
  its switches from it, so **a pack switched off disappears from Set up** and can only come back through
  `planetai config set`. This change fixes that on the way.
- Nothing on the page has ever started anything on the host. Every host action is a sentence: "run `planetai update`
  on the node".
- The host already runs one scheduled job: the nightly backup, a crontab line `install.sh` writes.
- The wild list (`packs.json`) has eight entries. Seven are code packs; two declare `pip:` lines (bmkg-synop,
  xiaomi-air), so their install rebuilds the image. An entry may pin a `commit`; none does, so `packs add <id>`
  takes the head of the repository at the moment it runs.

## Recommendation

**1. The page asks, the host does.** `POST /packs/install` writes one request, `out/requests/pack-add.json`, holding
only `{id, commit, actor, at}`. A crontab line on the host, written by `install.sh` and added by `update.sh` the way
the backup line is, tests for that file every minute and runs `planetai packs pending` only when it is there. With one,
it runs the same `packs_add` the terminal runs, then restarts the app, and writes what happened to
`out/requests/pack-add.status` as it goes. The app reads that file back for the page.

Not chosen:

- *The container fetches the pack itself.* It would need `packs/` writable, and then anything running in the app,
  every code pack included, could rewrite the core's packs. It still could not rebuild the image for a `pip:` line.
- *A launchd agent on a Mac, a systemd path unit on Linux.* Two mechanisms to install and keep right, and sudo on
  Linux. A crontab line is one mechanism, already used, and needs no root.
- *A small HTTP server on the host.* A second server and a second port, on a machine whose only server is the app.

The cost is up to a minute before anything starts; the page says so. ponytail: a minute's latency, a launchd
WatchPaths agent on a Mac if that ever matters.

**2. The host trusts the request for two things only, an id and a commit, and checks both itself.** It reads the wild
list again, by itself. The id must be on it. The commit must be the one the host resolves for that entry now: the
entry's pinned `commit` if it has one, otherwise the head of its repository. Anything else is refused with "the pack
changed since you read it; look again". This matters because GitHub serves a commit from any fork of a repository
under the parent's name, so a request that could name any commit could install anyone's code under
`fabcity/planetai-wild-packs`. The page only ever installs what the list names. `planetai packs add <owner>/<repo>`
for a pack that is not on the list stays a terminal command.

**3. Who may press it: the admin token, every time.** `POST /packs/install` needs `Authorization: Bearer
<ADMIN_TOKEN>` even from this machine, since a person at the terminal already has `packs add`. It is in no
`SHARE_LEVEL` allowlist, so a screen on the network without the token is refused at `off` and at `open` alike. It is
not an MCP tool and not in `app/tool_classes.py`, so neither the local model nor a remote agent installs a pack. A
person does. Each install writes an `actions` row (`stage=settings`), so Set up's history shows who added what and
when.

**4. What the person sees before anything is fetched.** Install opens a confirmation built from `GET
/packs/preview?id=…` (admin token). The app resolves the commit and reads that commit's `pack.yaml` from GitHub; it
writes nothing. The confirmation shows:

- the pack's name, its author, and the listed or reviewed status, said plainly ("listed: nobody who keeps the wild
  list has read it");
- where it comes from: the repository and folder, and the commit, with a link to read the code at that commit;
- what it reads and what it needs: the list's `reads` line, and its `pack.yaml`'s `metrics:` and `needs:` (bmkg-synop's
  says it holds a connection open to a WIS2 broker on port 8883);
- whether it is a code pack, and if so that it runs Python on this machine with the node's privileges;
- its `pip:` lines, each in full, and that they mean a rebuild of a few minutes;
- the settings it will ask for (`env:`), and whether it loads on this node's version (`requires:`).

The request the confirm button sends carries the commit shown, so what gets installed is what was read.

**5. Progress, failure and the restart.** The card shows one line that `GET /packs/install` keeps current, polled
every few seconds:

`waiting for the node (within a minute)` → `fetching <commit>` → `installing its libraries (a rebuild, a few
minutes)` when there are `pip:` lines → `restarting` → `installed, on`.

While the app restarts the page cannot reach it, so it says "restarting" and keeps asking. A request still waiting
after three minutes means the crontab line is missing, and the card says so: `planetai packs pending` on the node,
and `planetai doctor` checks the line. A failure shows `packs add`'s own last line and keeps the log in
`out/requests/pack-add.log`. A new pack whose install fails is removed again, so a half-installed folder is never
loaded at the restart. The page installs only a pack that is not here; updating one stays `planetai packs add <id>`
in the terminal. One install at a time:
a second press while one runs gets 409 and the line of the one running.

**6. The list.** A new `GET /packs/all`, gated like `GET /packs`, returns every pack folder on disk and every wild
list entry not on disk, each with: core or wild, installed, on (in `PACKS_ENABLED`, or that list is empty), loaded,
and the reason it is not when it is not: switched off, refused by `requires:`, or a code pack waiting for Allow code
packs. Installed wild packs say where they came from and at which commit (`.wild`). The app reads the wild list at
most once an hour; when it cannot, the page shows what is on disk and says the list could not be read. Set up draws
every row from this, so a pack switched off stays on the page with its switch.

**7. Code packs stay off until the keeper allows them.** Installing does not touch `PACKS_ALLOW_CODE`. Seven of the
eight wild packs are code, so an install usually ends with "installed, on, waiting for Allow code packs" and that
switch one row above. See the second question below.

**8. A new pack on the list is news, like a new release.** The node reads the wild list every hour, as it asks for
the newest release, under the same `UPDATE_CHECK` switch. A pack that appears on the list after the node's first
read is said once, on the household's channels (`info`, held back by quiet hours like the release line), and the
Packs section marks it new. The first read of the list says nothing: every pack on it would be news.

## What Tomas decided

On 27 October 2026:

1. *"It could be every hour and user can get a notification about a new pack, similarly when there is a new
   release."* The hourly read is the list, and the notice comes from it (8). The pickup of a pressed Install stays
   every minute, because an hour on "waiting" reads as broken, and the crontab line tests for the request file
   before it runs anything, so a minute with no request starts nothing but that test. Told to Tomas; one number to
   change if he wants the hour anyway.
2. Allow code packs stays its own switch (7).
3. *"Can turn on and off. Remove should be done in the terminal, can give instructions."* Every pack keeps its
   switch, an installed one switched off included, and a wild pack's card says how to remove it.
4. The test on node #1 is bmkg-synop, installed from the page.

## Built after approval

`app/main.py` (three routes), `app/packs.py` (`all_packs()`, the wild list read), `bin/planetai` (`packs pending`,
the crontab line in the doctor), `install.sh` and `update.sh` (the line), `app/static/doors-setup.js` (the packs
section only; the Sources line #357 adds is left alone), a new test suite with its `tests/all` line, a section in
`docs/site/packs.md`, the API docs, and a CHANGELOG line.
