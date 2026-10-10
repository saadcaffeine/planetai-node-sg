# The bot and the model ladder
<!-- checked: v0.80.10 -->

The bot adds conversation to a node. Somebody in the house asks "is the air bad right now?" on Telegram and
gets an answer read from the node's own tools; somebody says "I closed the windows" and that is recorded, in
their words, as an act. `docs/MODELS.md` opens on what this is not: "A node needs none of this." The node
reads its sensors, evaluates its rules, writes its report and sends its alerts with no model anywhere.

The model is a client of the node, not a component of it. It runs in its own container, `agent`, running
`app/agent_loop.py`, started by `planetai agent local`. Alerts and reports never pass through it: the app
container writes and sends those itself, and the agent container has no clock and sends nothing on a
schedule. That holds for the alert-event engine's messages too (`ALERT_ENGINE=events`, see [Alerts](alerts.md)):
the app container sends them, they carry no buttons and no id yet, and `/act` below answers an alert, never an event.

## Setting it up

1. **Start the loop.** `planetai agent local` installs Ollama if it is missing (Homebrew on a Mac, Ollama's
   script on Linux), starts it as a service, adds the compose profile `agent`, builds and starts the
   container. It downloads no model. If none is on the machine it says "no model is on this machine yet, and
   this command does not fetch one." and prints the recommendation for the machine's memory: `qwen3.5:4b`
   (3.4 GB on disk), or `qwen3.5:9b` (6.6 GB) at 16 GB and up. On Linux it sets
   `OLLAMA_URL=http://172.17.0.1:11434` and warns that Ollama must listen on `0.0.0.0` for the container to
   reach it. It then suggests three things to send the bot: `is the node healthy?`,
   `/act 23 closed the windows` and `/model`.
2. **Pull a model when you want one.** `planetai agent local pull qwen3.5:4b` fetches it, sets `AGENT_MODEL`
   to that tag and recreates the agent container; it says "qwen3.5:4b is on this machine and AGENT_MODEL now
   points at it". With no tag it prints the right `pull` line for this machine. Until a model is pulled the
   loop answers from the remote or online rung if one is configured, and says so if none is.
3. **Ask it something.** Message the bot "is the node healthy?". It should answer in a sentence or two,
   having called `health_check` and `status`. `planetai logs agent` says whether Telegram is set, which
   ladder it built and how many tools it was given.

The model must do tool calling. `docs/MODELS.md` lists five tags with their sizes and licences
(`qwen3.5:4b`, `qwen3.5:9b`, `qwen3:4b`, `qwen3:8b`, `qwen3:1.7b`) and names `gemma3:4b` as a good small model
that does not call tools. A container with no `AGENT_MODEL` set still asks for `qwen3:4b`, the tag nodes held
before `pull` existed. `planetai agent stop` stops the container.

Containers on macOS get CPU only, Intel and Apple Silicon alike; this is the one place that matters.

## What the model is given

The loop hands the model 16 of the node's 20 MCP tools: the `read` ones and `act`. It cannot change a
setting, run a pack's code, or make the node message the household by itself. The log says so each time the loop
opens a session to the node: "tools withheld from the local model (admin): maintenance, report_now, run_pack_script,
settings_set". Every rung gets the same 16, local, remote or online. A person driving an agent over the
tailnet still has all twenty; see [MCP](mcp.md).

`act` needs the person's own words. A model cannot write `acted`, `done` or `ok` as the note: the tool
refuses a placeholder and tells the model to ask.

> **Gap in v0.80.10.** The bot's system prompt tells the model to "give the exact command from
> `maintenance`" for a task that needs the node's shell, and `maintenance` is one of the four tools the loop
> withholds. Asked to update or back up the node, the bot cannot look the command up; the commands are in
> [The command line](cli.md).

## The ladder

Three rungs, all speaking the OpenAI-compatible chat protocol with tools:

| rung | what | settings | default model |
|---|---|---|---|
| `online` | Anthropic, OpenAI or Gemini with a key: the only rung that sends anything off your network | `AGENT_ONLINE_URL` and `AGENT_ONLINE_KEY`, both required; an Anthropic URL also gets `x-api-key` | `AGENT_ONLINE_MODEL` = `claude-sonnet-4-6` |
| `remote` | a bigger model on the tailnet: a laptop's Ollama, exo, llama.cpp | `AGENT_REMOTE_URL`, optional `AGENT_REMOTE_KEY` | `AGENT_REMOTE_MODEL` = `gpt-oss-120b` |
| `local` | Ollama on this machine; always present | `OLLAMA_URL` + `/v1`; the container's `MODEL`, set from `AGENT_MODEL` | `qwen3:4b` |

`AGENT_PREFER` decides the order, and its default is `private`: the online rung is removed, so a node that
never chose sends nothing off the network. `fallback` tries remote, then online, then local, with online kept
above local because a rung is skipped only when it *fails* and a 4B model never fails, it answers weakly.
`strongest` tries online, remote, local. A rung that raises is skipped for five minutes. The ladder is
rebuilt every 60 seconds from the node's settings, so a change in Set up → Model takes effect without a
restart; a value in `AGENT_ONLINE_URL` that is not a URL (node #1 once had the example's comment there) is
logged and ignored.

The dashboard's ask pane walks the same ladder, from the same settings and the same `AGENT_PREFER`, so one
choice governs both. Its local rung is there only when `planetai agent local` set one up, and it runs
read tools only, never a write; see [Ask the node](ask.md).

> **Gap in v0.80.10.** The Model group's description in Set up, on the dashboard and on the doors' Set up page, still reads "The strongest one the node can
> reach is used." The default is `private`, and `/model` in Telegram prints the order in force.

`tools/remote-model.sh gptoss` runs llama.cpp's server on a laptop or workstation with gpt-oss-120b (about
63 GB) or `qwen122b` for Qwen3.5-122B (about 75 GB), with an API key and tool calling on, and prints the
`AGENT_REMOTE_*` lines for the node's `.env`. Tested: gpt-oss-120b answers in about two seconds with correct
tool use; the node falls back to its local model when the laptop is away.

## How it answers

One MCP session per question (a long-lived one died silently once) over `http://app:8080/mcp` with the
admin token. The system prompt says: use the tools, never guess a number; `health_check` and `status` for
"how is it"; `context` for the sea, the weather, the land; `readings` for history; answer in the language
`ALERT_LOCALE` names (English, Bahasa Indonesia or Spanish); open with a fitting emoji; avoid statistics;
when a person says they did something, record it with `act`; never reveal a token; plain text under a
hundred words, without narrating.

Up to eight rounds of tool calls at temperature 0.2, with the last six messages of the chat (three
exchanges) as context. On the small rung the model is told not to think aloud and the final answer is
requested as constrained JSON, because a 4B model otherwise narrates its reasoning as prose. `<think>` blocks
and Markdown are stripped before sending, since Telegram shows them raw. Messages from a chat not in
`TELEGRAM_CHAT_IDS` are ignored and logged. If no rung answers, the reply says so and where to look:
"On the node: `ollama list`, and check AGENT_* in .env."

The bot's own fixed replies (the `/act` prompts, the errors) are written in English and Spanish; on a node
set to Bahasa Indonesia they fall back to English, while the model's answers follow `ALERT_LOCALE`.

## Commands that need no model

| in Telegram | does |
|---|---|
| `/act 12 closed the windows` | records the action on alert 12 in those words, with the actor `<AGENT_NAME>/telegram`; replies "Recorded: you acted on #12." |
| `/act 12` | records nothing and asks "What did you do about #12?", with the form to send it in: `/act 12 <what you did>` |
| `/stack [issue]` | the issue's state, its sentence in your language, the four distances with their provenance and unit, and up to two open alerts (on a node whose alert engine is `shadow` or `events`, not the heat and air alerts an event stands for): a template over the `issues` tool, no model ever |
| `/model [local\|remote\|online\|auto]` | pins a rung for this chat and prints the ladder: each rung, its model, its host, whether it is currently skipped, and what `AGENT_PREFER` means (`private`: "the node's own machines only, nothing leaves the network") |
| Event buttons | When the bot has announced itself (`TELEGRAM_BUTTONS=1`), event messages carry three buttons: Done (`acted`), Not now (`acknowledged`), Doesn't fit (`dismissed`). Pressing one posts `POST /actions` with `event_id`, `stage`, `actor`, `note`; Doesn't fit asks "what did you do instead?" and keeps the reply as the note. Labels in en/id/es. |

## What leaves the network

Nothing, unless you give the online rung a key and set `AGENT_PREFER` to something other than `private`.
`AGENT_ONLINE_KEY` is described in the settings as "The only thing that lets household data leave your
network." With `AGENT_PREFER=private` even a key set is never used. The bot's writes appear in the audit
trail as `<AGENT_NAME>/<rung>` (`local-model/local` by default), and tool arguments containing `KEY`,
`TOKEN` or `PASS` are masked in its log.

> **Note.** There is no fence on the model's numbers yet. The report is written by the node from SQL, and
> the bot's answers are the model's, told to use the tools and not to guess.

## Where this leads

The bot records an act the way every other surface does, as a row in `actions` that ρ counts: [ρ](rho.md).
To put a stronger agent on the node, driven by a person, see [Bring your own agent](agents.md).
