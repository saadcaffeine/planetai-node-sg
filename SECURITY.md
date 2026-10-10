# Security

A node sits in somebody's house and holds their readings. This page is how to tell us when something
about that is wrong, and how a node decides whose code it will run.

## Telling us about a vulnerability

Open a private advisory:

**https://github.com/fabcity/planetai-node/security/advisories/new** — the repository's *Security* tab,
then *Report a vulnerability*.

It is visible only to you and the maintainers until there is a fix to publish. `MAINTAINERS.md` says
who those are — on 20 September 2026 that is one person, which you should know when you judge how long
to wait for an answer. There is deliberately no
mailbox: a security address is only as good as whoever remembers to read it, and this project is small
enough that an unread inbox was the likelier failure.

Please do not open a public issue for anything that would let somebody else reach a node before it is
fixed. Anything else — a crash, a wrong number, a confusing sentence — is an ordinary issue and welcome
as one.

We will acknowledge a report and tell you what we think it is. If a fix ships, the changelog says what
was wrong and credits you unless you would rather it did not.

### What to put in it

The four commands, whose output is safe to paste:

```bash
planetai version        # the version, and the signer this node trusts
planetai doctor --json  # every check, and the fix for the ones that failed
planetai status --json  # what the node is doing
planetai logs           # the last twenty lines are usually enough
```

Then: what you did, what happened, and what you expected instead. A node's own name and city are in
that output; nothing else about the household is.

**Never send `.env`.** Not in an advisory, not in an issue, not in a chat, not redacted. It holds the
database password, the admin token, the backup token, the Telegram bot token and any key a pack asked for, and the
four commands
above answer every question `.env` would. If a report needs a setting, name the setting.

The same goes for raw container logs. Versions before v0.4.3 wrote Telegram bot tokens into them; if you
find one in yours, revoke it with @BotFather `/revoke` before pasting anything.

## What a node will run

Since v0.60 an update has to be signed. `install` and `update.sh` download the tarball, check its
published checksum, and then check an `ssh-keygen -Y` signature made by one key. A node that cannot
verify the signature does not install the download and says so; that refusal is the node doing its job,
not a bug.

The checksum and the signature answer different questions. The checksum is served from the same place as
the tarball, so it proves only that the download arrived whole — whoever can write one writes the other.
The signature is made with a key that is not on the web server and never was.

**The signer.** One key, principal `fabcity`, published in
[`tools/allowed_signers`](tools/allowed_signers) and embedded in `install`, `update.sh` and
`bin/planetai` so that a node can check an update before it has one and can say what it trusts
afterwards:

```
SHA256:1+MvZWJUBWisjY08E1KR77znXLs2lVWgVkh+Z++8IL4   issued 19 September 2026
```

Compare that fingerprint against a node with `planetai version`, from a machine that is not the node.
If they disagree, something replaced the node's copy of the CLI, and the CLI is not the thing to ask.

**Where the private half lives.** With the Fab City Foundation: in the Foundation's password manager,
with one working copy on the machine that cuts releases. It is not in this repository, not in the
tarball, not in CI and not in a log, and `tools/release.sh` refuses to run if it is pointed at a key
inside the repository. Rotation is in [`docs/SIGNING.md`](docs/SIGNING.md).

**Every release is published twice** — at `planetai.fab.city/node0/get` and as a GitHub Release — from
the same bytes with the same signature, so the two copies can be compared by anyone.

**A wild pack is not signed.** `planetai packs add` fetches a pack from GitHub at a pinned commit, and the node
records which commit in `packs/<id>/.wild`, but nobody's key vouches for it, and `listed` at
fabcity/planetai-wild-packs means it passed the checks, not that anyone read it. A data pack is SQL and words, and
its SQL runs as `planetai_ro`: it can read every table but `settings`, and write none. A code pack's `adapter.py`
runs as Python with the node's privileges, and only once `PACKS_ALLOW_CODE=1` is set: read the adapter before you
set it. A vulnerability in a core pack is reported here; one in a wild pack goes to its author, and to us as well
if it shows a way past those limits.

## What is not covered

The node is meant to be reachable by the household and by an agent they invited, over a tailnet or on
the LAN. Putting it on the public internet, or handing out `ADMIN_TOKEN`, is a configuration and not a
vulnerability. `docs/NETWORKING.md` says what to do instead.
