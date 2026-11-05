# Ask the node
<!-- checked: v0.91.0 -->

The dashboard can be asked about what it shows. A pane opens beside the page and talks to the model Set up names for
this node, the same one the Telegram bot uses, through the same tools. It reads the page and the node, it explains,
and it changes nothing. When a question needs a change, it puts the change on a card and the person presses it.
Nothing asked or answered is kept.

The pane needs a model. Without one it still searches this documentation.

## Opening it

1. On the classic dashboard (`/?layout=classic`), press **ask the node**, right of the modes in the header. On a
   phone the button is in the foot, and the pane opens as a sheet from the bottom. Learn mode opens it by itself. The
   five doors, the default layout, have a smaller box of their own (below). The phone page (`/?layout=mobile`) has
   none; its **Full dashboard** link goes to the doors.
2. The pane's header names the model and where it runs (`runs on this machine`, `runs on <host>, on your network`, or
   `runs online at <host>`), and says what it may do: `reads the page · records what you did · changes nothing`. If it
   says `no model on this node yet`, see the last section.
3. Press one of the three questions under the thread, or type one. The node writes the questions from tonight's
   figures: why the lead leads, the oldest open alert, what the lead's line means, then the other issues and alerts.
   A new three shows each time the pane opens and after each answer, and a question already asked in this
   conversation is not offered again.

The answer arrives word by word. Under it a ledger line says which model answered and where it runs, and **read 3
things** (or however many) opens to name every read the model made and how many milliseconds each took. When the
first model does not answer, the next one does, and the ledger says so.

`UI_ASK` under Set up turns the pane off for everybody, with no toggle left on the page. It is `on` by default. The
Wall never shows the pane. With `UI_ASK` off the doors' box is gone too, and the Wall's narration, which otherwise
asks the same model every ten minutes, draws nothing and sends nothing.

## The doors' ask box

On the five doors, the speech-bubble icon in the header, or **Ask the node** in the foot, opens a pane on its own
grey, so the page's paper is only ever the data. It asks the same `POST /ask`, with the door you are on as its `view`,
and draws only the words of the answer as they arrive. It reads like any chat: the box is at the bottom, each question
appears as your own line with the answer under it, and the exchanges stay on screen while the tab is open. Only the
new question is sent, never the ones before it. It shows no ledger line, no list of reads and no cards, so a change the model reaches
for is not drawn there; make it in Set up. Type in the box and press Enter, or the arrow inside the box; Shift and
Enter starts a new line, as the line under the box says. Above the box, three questions are offered, written by the
node from tonight's figures (`digest.prompts` in `GET /issues`), such as "What should I know about the heat today?".
With learn on, the two that the parts of the door carry come first. Pressing one asks it, and after each answer the
next three come round.

The line at the top of the pane says what answers. With no model set up, the box is a search of these docs: the
question's words are looked up in every section (`GET /docs/search`), the rarest words weighing most, and the five
best sections come back as links with a line of each. When a model answers a question you typed, the three best
sections follow its answer under **In the docs**, and when it does not answer, the search answers instead and says so. When the node itself does not answer, the box says "The node did not answer. Check this
screen is on the home network, then try again."

**Learn this page**, in the same pane, numbers every part of the door you are on, the bar and the foot included, and
lists for each one its name, its stage in the loop, what this documentation says about it, a line on what the part
draws, the routes it reads, the pack that drew it, and a link to the section it quotes.

## What it may do

| class | tools | in the pane |
|---|---|---|
| `read` | `status`, `health_check`, `sensors`, `context`, `readings`, `report_latest`, `history`, `alerts`, `packs`, `cells`, `issues`, `series` | run, through `/mcp` as `dashboard-chat` |
| `act` | `act` | not run: a card with the page's own **I did this** form |
| `admin` | `settings_set`, `run_pack_script`, `maintenance`, `report_now` | not run: a card, or a sentence naming where it is done |

`settings_get`, `report_bundle` and `export_day` are read tools the pane is never given: it can be open on a wall at
`SHARE_LEVEL=open`, and the person typing is not always the person who set the node up. `learned` is given only to a
request carrying the admin or act token, or coming from this machine, and never to the Wall's narration, because what
the house learned stays with the house.

A tool result is cut at 8,000 characters, and when it is cut the model is told so, with the full length. For a count,
`alerts` takes `since_hours` and answers with the count itself. After a tool result the model answers with
`reasoning_effort: none`; a server that refuses the field is asked again without it, and not sent it again.

A setting card says what the setting is now, what it would become, what leaves the house (the setting's own help
text) and how to set it back. **turn it on** writes it with the admin token the page holds for Set up; with none
held, the card asks for it and says `needs your token`. **open Set up** goes to the setting's group instead. A value
the setting would refuse is not proposed, and the card offers the values it takes.

An act card carries the alert's number and nothing the model wrote. What the person did is theirs to say, in their
own words, because ρ is built from those sentences.

## What it never sends

The node builds the model's context itself, from the `/issues` bundle the page already has: the lead and its
sentence, the digest, every watched issue's state and values, the open alerts, and the documentation for the part in
focus. On a node whose alert engine is `shadow` or `events`, the open alerts leave out those of the heat and air
packs the events replaced, since nobody can answer them there. The browser sends only the end of the thread: the
question and the three exchanges before it. The Wall's narration (`prompt: wall`) is offered no tools, so the model answers without thinking, and has a
context of its own, short facts anybody walking past may read: what is usual for the place, and none of the house's learnings, digests,
things, alerts' words or who answered ([API](api.md#post-ask)).

That context, and every tool result the model reads, has no coordinate, no sensor or station name, no sensor id and
no `meta`. The node removes or replaces them before the model sees anything.

Nothing is stored. The thread lives in the browser tab. It survives a reload, and goes when the tab closes, when
somebody presses **new conversation** in the pane's header, or after half an hour with no question. The node writes
no transcript, no database row and no log line with a word in it; the log says which tool ran and for how long.
`GET /ask/status` answers `stored: false`.

## Which model answers

Set up → Model decides, with the online key under Keys, for the pane and the Telegram bot alike. `planetai config`
sets the same keys.

| setting | what it does |
|---|---|
| `AGENT_REMOTE_URL`, `AGENT_REMOTE_MODEL` | a bigger model on another machine of yours. Ollama on a laptop is `http://<laptop>.local:11434/v1`, with `OLLAMA_HOST=0.0.0.0` set on the laptop so it listens beyond itself |
| `AGENT_ONLINE_URL`, `AGENT_ONLINE_MODEL`, `AGENT_ONLINE_KEY` | an online model: Anthropic, OpenAI or any other that speaks the OpenAI chat API |
| `AGENT_PREFER` | `private` (the default): the model on your network, then this machine's, and never online, which includes a remote model at a public address. `fallback`: your network, then online, then this machine. `strongest`: online first |

The pane tries them in that order and skips a model that does not answer for five minutes. It reaches the model on
this machine only when `planetai agent local` set one up, so a node with no local model can still answer from a
laptop on its network. [The bot](bot.md#the-ladder) has the ladder in full.

With `fallback` or `strongest` you give up control of what is asked: the question and the page's context go to the
provider named in `AGENT_ONLINE_URL`. That is their sentences and numbers, never a coordinate, a sensor's name or its
id, because the pane removes those before any model reads them. The header says so in bold whenever an online model
is in the order, every answer that came from it says `runs online at <host>`, and the fine print says the provider
keeps what its own terms say it keeps. The node still keeps nothing.

## Three ways to give it a voice

With no model set up, the pane says so, offers the documentation search, and shows three cards with a copy button.

- A model on this machine. The card names the tag `planetai agent local` suggests for this machine's memory, its
  size, and the line to run on the node: `planetai agent local pull <tag>`. `planetai agent local` sets up Ollama and
  the loop first, and neither downloads anything until you pull.
- A model on another machine of yours: `AGENT_REMOTE_URL` and `AGENT_REMOTE_MODEL` under Set up → Model, as in the
  table above. It stays on your network; at an address outside it, it counts as online.
- Your own agent, over MCP. The card prints the `claude mcp add` line with this node's address, and `planetai agent`
  on the node prints the token. A remote agent gets the whole MCP surface; see [Bring your own agent](agents.md).

When the model is installed and not answering, the pane says so and names `planetai doctor`.

The next part to add is a pack: [packs](packs.md).
