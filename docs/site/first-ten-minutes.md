# First ten minutes
<!-- checked: v0.80.10 -->

The install ends with a node that is reading your place and has nobody to tell. These ten minutes add the
rest of the loop: a channel to your phone, one alert that goes all the way through, a person's answer
recorded against it, and the first value of ρ, the share of act-level alerts somebody answered. By the end the
node can do what `ARCHITECTURE.md` says only this layer can: measure whether anybody acted on what it said.

Each step says what to type, what the screen shows when it worked, and which part of the node now exists.

## 1. See that it is reading

```bash
planetai status
```

```
  node      <name>   <version>   schema <schema>
  up        <h>h <m>m   polls <n>   readings <n>
  last poll <time of the last poll>
  errors    none
  sensors   none of yours yet (models only)
  reference <n>: <the first four public stations and models it reads>
  alerts    0 so far
  rho       not yet measured  (0/0 act-level alerts answered, 30d)
```

The angle brackets are this node's own figures. `polls` climbs by one every `POLL_SECONDS` (300).
`errors none` means every source answered. With a Smart Citizen kit configured, `sensors` names it instead of saying "models only".

**Now there is:** sense. The poll loop is running and the models for your coordinates are in the database.

## 2. Connect Telegram

```bash
planetai telegram
```

It walks you through it. Make a bot with **@BotFather** (`/newbot`), paste its token when asked, then open
a chat with the bot and send it any message, because a bot cannot start a conversation. The command waits up
to two minutes for that message. When it worked:

```
● token works. Your bot is @<yourbot>
● found your chat: <chat id>
● sent you a hello
● the node is restarting with Telegram on. Try:  planetai test-alert
```

Your phone shows "<name> is connected. Alerts will arrive here." The command writes `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_IDS` to `.env` and to the running node, so the terminal and the dashboard agree. Several
people can receive alerts: comma-separate chat ids in `TELEGRAM_CHAT_IDS`.

**Now there is:** a channel. An alert has somewhere to go that a person will see.

## 3. Prove the whole path

```bash
planetai test-alert
```

```
  A rule that always fires has been added. The node checks rules every minute.
  Waiting......
● it fired. Alert #12 is in the log and on your phone.

  Now close the loop, which is the part the Index measures:
    planetai act 12
```

It writes a temporary pack with one act-level rule that always fires, waits up to ninety seconds for the
rules loop to pick it up, and removes the pack the moment it finds its own alert, so the phone gets one test message and not two. The message on your phone says: "Test alert from your node.
If you can read this, the whole path works: rule to message to you. Record it with `planetai act <id>`." It
is the only end-to-end proof there is; a quiet node is not a working node until this has happened once.
(The API has a second test alert, `POST /test-alert`, whose text asks you to close the loop with `/act N` or
`planetai act N`.)

**Now there is:** act. A rule fired, an alert was written to `alerts`, and it went out on every channel the
node has.

## 4. Close the loop

```bash
planetai act 12 "read the test alert on my phone"
```

```
● recorded: you acted on #12
  rho is now <ρ>  (<answered>/<asked> alerts answered, median <m> min)
```

The number after `act` is the alert id the test printed. On a node whose only act-level alert is the test,
ρ is now `1.0`, one of one. Write what you did in your own words: the note is the record. Leave it out and
the CLI writes `acted`, which is a placeholder and tells nobody anything; the bot and the MCP `act` tool
refuse a blank note for that reason.

**Now there is:** measure. There is a row in `actions`, and ρ has a value. It is the one number on the page
that comes from a person, and it counts every act-level alert answered within 24 hours over the last 30
days. See [ρ](rho.md).

## 5. Open the dashboard

```bash
planetai ui
```

```
  On this machine:      http://localhost:8080/
  On your network:      http://<lan ip>:8080/
  On a wall screen:     add  #wall  — the dark register, moves its own ladder; needs SHARE_LEVEL=open

  SHARE_LEVEL is off, so a screen on your network gets the dashboard and the node's status and no readings.
```

Then three tokens, each under its own line. The **admin token** is for Set up: "Anyone with it can change
what the node reads and where it sends alerts. Treat it like a password." The **backup token** is read-only,
for a NAS. The last is "for closing a loop from a phone": the **act token**, which "cannot read a secret or
change a setting". `planetai ui` creates the admin and act tokens if they are missing.

Open `http://localhost:8080/`. At the default `SHARE_LEVEL=off` every browser, including the one on the
machine the node runs on (Docker presents it as a network client), sees the node's name, its status and no
readings. Go to **Set up**, paste the admin token (or only the act token, in the field labelled "Token for
closing a loop") and press **Unlock**. The header has six views, Now, Historical, Network, Wall, Arrange and
Set up, and three modes, Simple, Advanced and Learn. Learn is the full page with a question mark at each
part; pressing one puts the passage of these pages that explains it, and a link to it, in the ask pane beside the page. Set up is where sensors are added or changed
(Sources), where the bot's model lives (Model), and where every runtime setting can be changed without
touching `.env`. See [Dashboard](dashboard.md) and [Sharing](sharing.md).

**Now there is:** the loop, on a screen. The same `GET /issues` document the bot and the report read, drawn
with what asks for a person first and the evidence after it.

## When a real alert arrives

The test alert belongs to no issue, so it counts in ρ but never appears as an open alert on the page. The first
real act-level alert from a pack rule about the air or the heat does, and the loop closes on the Now view. Until then Decide says:
"This node sends alerts, not events." and, under it, "Nothing is asking for anything."

1. **Read it under Decide.** Decide is the first section under the lead. On a node that still sends alerts, as a
   new node does, it shows a card for each open alert: *what was seen*, the alert's first line, and *what this
   node suggests*, the rule's own 👉 recommendation. (A node set to `ALERT_ENGINE=events`, or to `shadow`, shows one card for each
   open event instead, with the action it chose and **Done**, **Not now** and **Doesn't fit**; see
   [Dashboard](dashboard.md#decide).) Press **Decide about this**,
   fill in "Who is deciding" and "What will be done" (or press **Take its word**), then **Record the
   decision**. The page answers: "Decided. Nothing has moved — press "I did this" on this card when it is
   done." A decision closes no alert and does not enter ρ. It is the record that somebody looked.
2. **Record it when it is done.** The same card has a button, **I did this**. Fill in "Who" and "What you
   did", then **Record it**. The page answers: "Recorded. The
   node watches what happens next." This needs the act token or the admin token in this browser. Without
   one the node answers "this node is set to SHARE_LEVEL=<level>, so /actions answers only this machine or a
   request carrying a token." and the page adds where the token comes from. The same act can come from `planetai act`, from `/act <id>
   <what you did>` in Telegram, from an agent's `act` tool, or over Reticulum.
3. **See it under Measure.** "Whether it worked" shows ρ reported, answered ÷ asked, and the median minutes
   from alert to answer; `planetai status` prints the same figure on its `rho` line. The funnel beside it
   counts asked, acknowledged, acted and measured. `measured` goes up 48 hours after the act if the same
   rule has stayed silent on the same sensor, and "Which of these worked" shows the same thing rule by rule.

**Now there is:** the whole loop, observe · decide · act · measure, on one page, and a ledger of who
decided and who did what.

> **Note.** `DECISION_REQUIRED=1` (Set up → Alerts, off by default) makes the node refuse an act with no
> decision recorded against the same alert first, with HTTP 409, however the act arrives. It is for a node that
> acts for a street rather than a house.

## 6. Talk to it

```bash
planetai agent local
```

It installs Ollama on the machine if it is missing, starts it as a service, and then says what model it
recommends and does not download it:

```
● machine has 16 GB
● no model is on this machine yet, and this command does not fetch one.
     For 16 GB the recommendation is  qwen3.5:9b  (6.6 GB on disk, Apache-2.0)
     Pull it when you want it:   planetai agent local pull qwen3.5:9b
```

Under 16 GB the recommendation is `qwen3.5:4b` (3.4 GB). `planetai agent local pull <tag>` downloads it and
points `AGENT_MODEL` at it. The command still builds and starts the `agent` container, a loop that answers
your Telegram messages with the node's own tools, and ends: "running. Message your bot: is the node healthy?
/act 23 closed the windows /model". On Linux it also sets `OLLAMA_URL=http://172.17.0.1:11434` and warns that
the Ollama service must listen on `0.0.0.0` so the container can reach it.

`/act 23` with no words gets a question back ("What did you do about #23?") and records nothing. The model
on this machine gets the node's read and act tools only, never the admin ones. By default
(`AGENT_PREFER=private`) nothing the bot is asked leaves your network; a bigger model on a machine of yours
can sit above the local one on the [model ladder](bot.md), and an online model is used only after someone
here chooses `fallback` or `strongest` and sets a key.

**Now there is:** an agent on the node, answering from the node's own tools.

## Every day

```
planetai status      is it alive, what has it read, what fired, ρ
planetai doctor      every check, with the fix written next to any failure
planetai logs        what it is doing right now
planetai update      backup, fetch the latest version, check its signature, migrate, rebuild, verify
planetai storage     where the data is, where the copies go
```

`planetai doctor` prints one line per check, `✓` or `✗`, or an amber `!` for something worth saying that does not
fail the run, such as a new version being out; the fix is under every `✗` and `!` after a `→`. It ends with
`all good` or `fix the marked lines, then run planetai doctor again`. A tarball node also shows
`release signature verified on last update` and the source registry it carries.

A good week looks like this: a short report from the node a few times a day, a handful of alerts rather
than dozens, one or two that changed what you did, and a fresh file in `backups/` every morning. Dozens of
alerts a day means the thresholds are wrong for your place. Say which ones rather than raising them: a node
that is quiet because you raised its threshold is lying.

## When something is off

`planetai doctor` first. Then [Troubleshooting](troubleshooting.md), which is ordered by what is on your
screen. When you ask for help, write to **info@fab.city** with `planetai status`, `planetai doctor` and the
last twenty lines of `planetai logs`. Never `.env`: it holds your tokens.

## Where this leads

The node now reads models and public stations. The next part is what measures your own place:
[Sensors and sources](sensors.md). After that, [the dashboard](dashboard.md) and [the report](report.md) are
how you read it, and [alerts](alerts.md) are how it asks.
