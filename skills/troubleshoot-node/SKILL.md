---
name: troubleshoot-node
description: Diagnose a PLANETAI node that is broken, quiet, or lying, from what its own diagnostics say.
---

# Troubleshooting a node

Somebody's node stopped doing something. You are probably reading a paste, not sitting at the machine.

## Ask for exactly these four things

```bash
planetai doctor --json
planetai status --json
planetai logs                 # the last twenty lines are enough
```

and, if a sensor is the complaint, `planetai sensors --json`.

**Never ask for `.env`, and never accept it.** It holds their Telegram token, their admin token and their
database password. If one arrives anyway, say so plainly and stop: **tell them to revoke it now** — a
Telegram token is revoked with `/revoke` to @BotFather, which issues a new one, then `planetai telegram`
again. A log line containing `api.telegram.org/bot` is the same leak; that string is a token.

## Read, in this order

1. The *When it breaks* table in `docs/START_HERE.md`. Everything in it has happened to a real node, and
   most pastes are one of its rows. Do not copy that table into your answer; read it and point at the row.
2. `planetai doctor` output — every failing check already carries its own fix. Use that fix before you
   invent one. Its **Data sources** block and *To finish setting up* list what is not set up yet (a sensor,
   Telegram, the backup); a node with a cross there is unfinished, not broken.
3. `docs/UPDATING.md` if the trouble began at an update, `docs/NETWORKING.md` if it began at a network
   change, `docs/STORAGE.md` if it is about the database or backups.
4. `AGENTS.md` — how to read `status.errors`, what `local` and `indoor` mean, and what "outside" resolves to.

## The four that are not in the table

| what you see | what it actually is |
|---|---|
| The node is healthy and silent for days | Usually correct. Check ρ and the alert count before assuming a fault; a quiet node is the normal state of a good week. |
| Alerts stopped after somebody "fixed the noise" | A threshold was raised. **A node that is quiet because you raised its threshold is lying.** Put it back and say why the place is noisy instead. |
| The bot answers "This node answers its household only" | That chat is not in `TELEGRAM_CHAT_IDS`. The message carries the chat's id; whoever runs the node adds it to *Telegram chat ids* in Set up, after the ids already there. |
| One neighbour station reads wildly high | Not necessarily a fault. Read the note in `CHANGELOG.md` for v0.41.2: either something is burning there or that sensor is wrong, and the node is built to say both. |

## What you may touch, and what you may not

May: read anything over MCP or the CLI; `planetai restart`; `planetai update`; `planetai backup`;
`planetai logs`; ask the node to re-run a check.

May not, without the person saying yes in this conversation:

- change a threshold or any rule, for the reason above;
- `planetai act` on an alert. `acted_at` is the person's note on what *they* did. Ask them, record their
  words, never invent one.
- move the database off a local disk, or onto a network mount;
- change `.env` or any setting that the dashboard also writes — the dashboard wins, and the page says so.

## Escalating

`info@fab.city`, with `planetai status`, `planetai doctor` and the last twenty lines of `planetai logs`.
Not `.env`. Say what they expected as well as what happened — the first is the part that gets lost.

## When a doc and this file disagree

The doc wins and this file has a bug. Say so, and open an issue.
