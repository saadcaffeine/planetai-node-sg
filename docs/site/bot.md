# The bot and the model ladder
<!-- checked: v0.91.0 -->

The bot adds conversation to a node. Somebody in the house asks "is the air bad right now?" on Telegram and gets an
answer read from the node's own tools. Somebody says "I closed the windows" and the bot records it, in their words,
as an act.

A node needs none of this. It reads its sensors, evaluates its rules, writes its report and sends its alerts with no
model anywhere. The model is a client of the node: it runs in its own container, `agent`, running
`app/agent_loop.py`, which `planetai agent local` starts. Alerts and reports never pass through it. The app container
writes and sends them, including the alert events of `ALERT_ENGINE=events` ([Alerts](alerts.md)), and the agent
container has no clock and sends nothing on a schedule.

## Setting it up

1. **Start the loop.** Run `planetai agent local`. It installs Ollama if it is missing (Homebrew on a Mac, Ollama's
   script on Linux), starts it as a service, adds the compose profile `agent`, and builds and starts the container.
   It downloads no model. With none on the machine it says "no model is on this machine yet, and this command does
   not fetch one." and prints the recommendation for the machine's memory: `qwen3.5:4b` (3.4 GB on disk), or
   `qwen3.5:9b` (6.6 GB) at 16 GB and up. On Linux it sets `OLLAMA_URL=http://172.17.0.1:11434` and warns that Ollama
   must listen on `0.0.0.0` for the container to reach it. It ends by suggesting three things to send the bot.
2. **Pull a model when you want one.** `planetai agent local pull qwen3.5:4b` fetches it, sets `AGENT_MODEL` to that
   tag and recreates the agent container. It says "qwen3.5:4b is on this machine and AGENT_MODEL now points at it".
   With no tag it prints the right `pull` line for this machine. Until a model is pulled the loop answers from the
   remote or online rung if one is configured, and says so if none is.
3. **Ask it something.** Message the bot "is the node healthy?". It should answer in a sentence or two, after
   calling `health_check` and `status`. `planetai logs agent` shows whether Telegram is set, which ladder it built and
   how many tools it was given.

The model must do tool calling. `docs/MODELS.md` lists five tags with their sizes and licences (`qwen3.5:4b`,
`qwen3.5:9b`, `qwen3:4b`, `qwen3:8b`, `qwen3:1.7b`), and names `gemma3:4b` as a good small model that does not call
tools. A container with no `AGENT_MODEL` set asks for `qwen3:4b`. `planetai agent stop` stops the container.

Containers on macOS get the CPU only, on Intel and Apple Silicon alike, and the model is the one place on the node
where that matters.

## What the model is given

The loop hands the model 17 of the node's 21 MCP tools, the `read` ones and `act`. It cannot change a setting, run a
pack's code, or make the node message the household by itself. Each time it opens a session the log says "tools
withheld from the local model (admin): maintenance, report_now, run_pack_script, settings_set". Every rung gets the
same 17, local, remote or online. A person driving an agent over the tailnet still has all 21 ([MCP](mcp.md)).

`act` needs the person's own words. The tool refuses `acted`, `done`, `ok` or another placeholder as the note and
tells the model to ask.

> **Gap in v0.91.0.** The bot's system prompt tells the model to "give the exact command from `maintenance`" for a
> task that needs the node's shell, and `maintenance` is one of the four tools the loop withholds. Asked to update or
> back up the node, the bot cannot look the command up. The commands are in [The command line](cli.md).

## The ladder

Three rungs, all speaking the OpenAI-compatible chat protocol with tools:

| rung | what | settings | default model |
|---|---|---|---|
| `online` | Anthropic, OpenAI or Gemini with a key; the only rung that sends anything off your network | `AGENT_ONLINE_URL` and `AGENT_ONLINE_KEY`, both required; an Anthropic URL also gets `x-api-key` | `AGENT_ONLINE_MODEL` = `claude-sonnet-4-6` |
| `remote` | a bigger model on the tailnet: a laptop's Ollama, exo, llama.cpp. At a public address it counts as online | `AGENT_REMOTE_URL`, optional `AGENT_REMOTE_KEY` | `AGENT_REMOTE_MODEL` = `gpt-oss-120b` |
| `local` | Ollama on this machine, always present | `OLLAMA_URL` + `/v1`; the container's `MODEL`, set from `AGENT_MODEL` | `qwen3:4b` |

`AGENT_PREFER` sets the order. Its default, `private`, removes the online rung, so a node that never chose sends
nothing off the network. `fallback` tries remote, then online, then local: online sits above local because a rung is
skipped only when it fails, and a 4B model never fails, it answers weakly. `strongest` tries online, remote, local. A
rung that raises an error is skipped for five minutes. The loop rebuilds the ladder from the node's settings every
60 seconds, so a change in Set up → Model takes effect without a restart. A value in `AGENT_ONLINE_URL` that is not a
URL is logged and ignored.

The dashboard's ask pane walks the same ladder from the same settings, so one choice governs both; see
[Ask the node](ask.md).

> **Gap in v0.91.0.** The Model group's description in Set up, on the classic dashboard and on the doors, still reads
> "The strongest one the node can reach is used." The default is `private`, and `/model` in Telegram prints the order
> in force.

`tools/remote-model.sh gptoss` runs llama.cpp's server on a laptop or workstation with gpt-oss-120b (about 63 GB),
or `qwen122b` for Qwen3.5-122B (about 75 GB), with an API key and tool calling on, and prints the `AGENT_REMOTE_*`
lines for the node's `.env`. When the laptop is away the node falls back to its local model.

## How it answers

Each question opens its own MCP session to `http://app:8080/mcp` with the admin token. The system prompt tells the
model to use the tools and never guess a number: `health_check` and `status` for "how is it", `context` for the sea,
the weather and the land, `readings` for history. It answers in the language `ALERT_LOCALE` names (English, Bahasa
Indonesia or Spanish), opens with a fitting emoji, avoids statistics, records with `act` when a person says they did
something, never reveals a token, and keeps to plain text under a hundred words without narrating.

It gets up to eight rounds of tool calls at temperature 0.2, with the last six messages of the chat (three exchanges)
as context. On the small local rung the model is told not to think aloud and its final answer is asked for as
constrained JSON, because a 4B model otherwise narrates its reasoning. `<think>` blocks and Markdown are stripped
before sending, since Telegram shows them raw.

A message from a chat not in `TELEGRAM_CHAT_IDS` is logged and not answered. The first one from each such chat since
the loop started gets "This node answers its household only. To be added, ask whoever set it up to add this chat:
&lt;its id&gt;." When no rung answers, the reply is "I can't answer questions right now. Alerts and the morning report
still work. Whoever set up the node can fix this in Set up › Model.", and the log has the error.

The bot's own fixed replies (the `/act` prompts, the errors, the picture and offer replies) are in English and
Spanish, and fall back to English on a node set to Bahasa Indonesia. The model's answers follow `ALERT_LOCALE`.

## Commands that need no model

These are templates over the node's tools and answer even when no model is reachable.

| in Telegram | does |
|---|---|
| `/act 12 closed the windows` | records the action on alert 12 in those words, with the actor `<AGENT_NAME>/telegram`, and replies "Recorded what you did." |
| `/act 12` | records nothing and asks "What did you do about it?", with the form to send it in: `/act 12 <what you did>` |
| `/stack [issue]` | the issue's state, its sentence in your language, the four distances with their provenance and unit, and up to two open alerts (on a node whose alert engine is `shadow` or `events`, not the heat and air alerts an event stands for), read from the `issues` tool |
| `/learned` | what the node learned here, from the `learned` tool: per learning, the alert as the household calls it and the verdict first ("An air alert: acting on it seemed to make it worse than leaving it (the finding holds)"), then its own sentence with the numbers. Empty until the first daily check, and it says why when `AGENT_PREFER` is not `private` |
| `/learned day` · `week` · `month` · `year` | the newest diary entry of that size, as the morning message carries it |
| `/learned smoke` | the five diary entries and learnings that best match the words, newest first among equals |
| `/model [local\|remote\|online\|auto]` | pins a rung for this chat and prints the ladder: each rung, its model, its host, whether it is skipped right now, and what `AGENT_PREFER` means (`private`: "the node's own machines only, nothing leaves the network") |

When the loop starts with Telegram set, it sets `TELEGRAM_BUTTONS=1`, and from then on the node's event messages carry three buttons:
Done (`acted`), Not now (`acknowledged`) and Doesn't fit (`dismissed`). Pressing one posts `POST /actions` with
`event_id`, `stage`, `actor` and `note`. Doesn't fit asks "What did you do instead?" and keeps the reply as the note.
The button labels are in English, Indonesian and Spanish. `/act` answers an alert, never an event.

A pack's rule can ask with buttons of its own, on the same switch. The alert reaches Telegram with its buttons as a
keyboard in the language of `ALERT_LOCALE`, and each press is recorded on that alert as the choice. The bot lifts the
row that was pressed and writes the button's words and the name of whoever pressed it. If the pack marked a button
`acknowledged`, like Not now, the whole keyboard goes. If a button has a question, the bot asks it in the chat, and
the next message there within ten minutes from the person who pressed is kept as the note on that answer, and
anyone else's message in a group chat is not. Pressing the same button twice yourself records nothing new, and on an
alert more than 72 hours old the bot says "This question has closed." If Telegram refuses a keyboard, the message is
sent again without it. Now shows the same buttons under What to do while they are open. A pack writes them in a rule's `buttons` column, described under
Buttons in [Packs](https://github.com/fabcity/planetai-node/blob/main/docs/PACKS.md#buttons).

## Sending a picture

A picture sent to the bot is kept on the node, the same as **+ Add an image** on the dashboard. The bot fetches it
from Telegram and posts it to `POST /captures` ([API](api.md)) with the sender's first name as `actor`, the caption as
the note, and `describe=1`. It answers "Kept." and says where the picture is and whether the image model
(`EYES_MODEL`) is describing it. A picture the node already has (the same file, by its sha256) gets "That picture is
already kept.", and one the node refuses gets the node's own reason. Pictures are the `eyes` pack's: with it off the
node refuses every one, and the reply is "The node did not keep it: the eyes pack is off on this node".

- Sent as a photo, Telegram recompresses it and drops its EXIF, so the node takes the largest size, dates it by the
  message and places it in the node's own cell.
- Sent as a file (Telegram's *File* instead of *Photo*), the original reaches the node byte for byte. Its own date
  and GPS are used, then removed from the stored copy as with every capture. Send a picture taken somewhere else this
  way.
- A tag in the caption names what took it: `#drone`, `#microscope`, `#camera` or `#balloon`, and none means `phone`.
  The tag is taken out of the note; any other `#word` stays in it.
- A file that is not an image is refused, and so is one over 20 MB, the most the Bot API lets a bot fetch (send it
  as a photo, or add it from the dashboard). If the node refuses the bot's token, the reply asks whoever set up the
  node to check the bot's access, and the log has the status: the agent's `ADMIN_TOKEN` is not the app's.

Only the household's chats (`TELEGRAM_CHAT_IDS`) can send pictures; a picture from any other chat is logged and gets
no reply. The download URL holds the bot token, so a failed download is logged by its error's type only. Telegram's
location messages are not read, and the image model's description is on the image's card, not sent back.

## Offers: someone who is not the household

A chat outside `TELEGRAM_CHAT_IDS` gets no answer beyond the one line saying who the node answers, with one exception:
an offer. An offer's `ask` link (`t.me/<bot>?start=offer-<id>`, in `GET /offers` and the daily export) opens the bot
on that offer, and the bot asks for one message about the thing ("Write one message about the cordless drill (to
borrow)…"). The next message, within 30 minutes, goes to every household chat with the offer's number and name, the
message, and the sender's first name and @username.

The sender is told "Passed on". You write back to them yourself through their @username. When they have none, both
sides are told they can be reached only if the message said how. One message per chat an hour is passed on, and a
later one is not. The household's chat ids never show, and nothing the sender writes is kept.

## What leaves the network

Nothing, unless you give the online rung a key and set `AGENT_PREFER` to something other than `private`. The
settings describe `AGENT_ONLINE_KEY` as "The only thing that lets household data leave your network." With
`AGENT_PREFER=private` a key that is set is never used. The remote rung is meant for a machine of yours; the
node reads its address, and a remote model at a public address (a city's server, a rented GPU) counts as online.
With `AGENT_PREFER=private` it is not used at all. With `fallback` or `strongest` the bot hands it no settings,
report bundle or day's export, the pane names it online, and agents stop reading what the house learned. The bot's writes appear in the audit trail as
`<AGENT_NAME>/<rung>` (`local-model/local` by default), and tool arguments whose names contain `KEY`, `TOKEN` or
`PASS` are masked in its log.

> **Note.** Nothing checks the model's numbers. The report is written by the node from SQL; the bot's answers are the
> model's, told to use the tools and not to guess.

## Where this leads

The bot records an act the way every other surface does, as a row in `actions` that ρ counts: [ρ](rho.md). To put a
stronger agent on the node, driven by a person, see [Bring your own agent](agents.md).
