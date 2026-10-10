# Ask the node
<!-- checked: v0.80.10 -->

The dashboard can be asked about what it shows. A pane opens beside the page and talks to the model Set up names
for this node, the same one the Telegram bot uses, asked through the same tools. It reads the page and
the node, it explains, and it changes nothing. When a question needs a change, it puts the change on a card and
the person presses it. Nothing asked or answered is kept.

This is the part of the node that answers in sentences. It needs a model; without one the pane
still searches this documentation.

## Opening it

1. Press **ask the node**, right of the modes in the header. On a phone the button is in the foot, and the pane
   opens as a sheet from the bottom. Learn mode opens it by itself.
2. The pane's header names the model and where it runs (`runs on this machine`, `runs on <host>, on your
   network`, or `runs online at <host>`), and says what it may do: `reads the page · records what you did ·
   changes nothing`. When it says `no model on this node yet`, see the last section.
3. Press one of the three questions under the thread, or type one. The questions are written by the node from
   tonight's figures: why the lead leads, the oldest open alert, what the lead's line means, and then the other
   issues and alerts. A new three shows each time the pane opens and after each answer, and a question you have
   already asked in this conversation is not offered again.

An answer arrives word by word. Under it a ledger line says which model answered and where it runs, and **read
3 things** (or however many) opens to name every read the model made and how many milliseconds each took. When the first model does not answer, the next one does,
and the ledger says so.

`UI_ASK` under Set up turns the pane off for everybody: no toggle, no pane. It is `on` by default. The wall never
shows it. The five doors read it too: with `UI_ASK` off their ask box is gone and the Wall's
narration, which otherwise asks the same model every ten minutes, says asking is off and sends nothing.

## What it may do

| class | tools | in the pane |
|---|---|---|
| `read` | `status`, `health_check`, `sensors`, `context`, `readings`, `report_latest`, `history`, `alerts`, `packs`, `cells`, `issues`, `series` | run, through `/mcp` as `dashboard-chat` |
| `act` | `act` | not run: a card with the page's own **I did this** form |
| `admin` | `settings_set`, `run_pack_script`, `maintenance`, `report_now` | not run: a card, or a sentence naming where it is done |

A tool result the model reads is cut at 8,000 characters, and when it is cut the model is told so, with the
full length, rather than handed half a list as though it were all of it. For a count, `alerts` takes
`since_hours` and answers with the count itself. After a tool result the model answers without thinking
(`reasoning_effort: none`): the thinking is what chooses the tool, and after the result it was a minute or more of
hidden text for one sentence. A server that refuses the field is asked again without it, and not sent it again.

`settings_get`, `report_bundle` and `export_day` are read tools the pane is not given. The pane can be open on a
wall at `SHARE_LEVEL=open`, and the person typing is not always the person who set the node up.

A setting card says what the setting is now, what it would become, what leaves the house (the setting's own help
text) and how to set it back. **turn it on** writes it with the admin token the page holds for Set up; with none
held, the card asks for it and says `needs your token`. **open Set up** goes to the setting's group instead. A
value the setting would refuse is not proposed; the card offers the values it takes.

An act card carries the alert's number and nothing the model wrote. What the person did is theirs to say, in
their own words, because ρ is built out of those sentences.

## What it never sends

The node builds the model's context itself, from the `/issues` bundle the page already has: the lead and its
sentence, the digest, every watched issue's state and values, the open alerts, and the documentation for the part
in focus. On a node whose alert engine is `shadow` or `events`, the open alerts leave out those of the
heat and air packs the events replaced, which nobody can answer there; the pane's first question about the oldest open
alert is then about one of the others, or asks whether anything needs attention. The browser sends only the end of the thread: the question and the three exchanges before it.

That context, and every tool result the model reads, has no coordinate, no sensor or station name, no sensor id
and no `meta`. They are removed or replaced before the model sees them; `tests/test_ask.py` checks the context
built on node #1's own capture for each of them.

Nothing is stored. The thread is in the browser tab. It survives a reload, and goes when the tab closes, when
somebody presses **new conversation** in the pane's header, or after half an hour with no question. The node writes no transcript,
no database row and no log line with a word in it: the log says which tool ran and for how long. `GET
/ask/status` answers `stored: false`.

## Which model answers

Set up → Model decides, with the online key under Keys, for the pane and the Telegram bot alike, and so does
`planetai config`:

| setting | what it does |
|---|---|
| `AGENT_REMOTE_URL`, `AGENT_REMOTE_MODEL` | a bigger model on another machine of yours. Ollama on a laptop is `http://<laptop>.local:11434/v1`, with `OLLAMA_HOST=0.0.0.0` set on the laptop so it listens beyond itself |
| `AGENT_ONLINE_URL`, `AGENT_ONLINE_MODEL`, `AGENT_ONLINE_KEY` | an online model, Anthropic, OpenAI or any other that speaks the OpenAI chat API |
| `AGENT_PREFER` | `private` (the default): the model on your network, then this machine's, and never online. `fallback`: your network, then online, then this machine. `strongest`: online first |

The pane tries them in that order and skips a model that does not answer for five minutes. It reaches the model on
this machine only when `planetai agent local` set one up, so a node with no local model can still answer from a
laptop on its network.

**An online model is a choice to give up sovereignty over what is asked.** With `fallback` or `strongest`, the
question and the page's context go to the provider named in `AGENT_ONLINE_URL`: its own sentences and numbers,
never a coordinate, a sensor's name or its id, because the pane removes those before any model reads them. The
header says so in bold whenever an online model is in the order, every answer that came from it says `runs online
at <host>`, and the fine print says the provider keeps what its own terms say it keeps. The node still keeps
nothing.

## Three ways to give it a voice

With no model set up, the pane says so, offers the documentation search, and shows three cards with a copy button.

- **A model on this machine.** The card names the tag `planetai agent local` suggests for this machine's memory
  and its size, with the line to run on the node: `planetai agent local pull <tag>`. `planetai agent local` sets up
  Ollama and the loop first; neither downloads anything until you pull.
- **A model on another machine of yours.** Under Set up → Model, `AGENT_REMOTE_URL` and `AGENT_REMOTE_MODEL`: see
  "Which model answers" above. It stays on your network.
- **Your own agent, over MCP.** The card prints the `claude mcp add` line with this node's address. `planetai
  agent` on the node prints the token. A remote agent gets the whole MCP surface, which rounds positions,
  refuses what it must and records every write; see [Bring your own agent](agents.md).

When the model is installed and not answering, the pane says so and names `planetai doctor`.

The next part to add is a pack: [packs](packs.md).
