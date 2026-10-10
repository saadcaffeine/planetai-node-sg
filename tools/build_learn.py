#!/usr/bin/env python3
"""Build app/static/learn.json, the learn layer's marks, out of docs/site.

    python3 tools/build_learn.py            # write app/static/learn.json
    python3 tools/build_learn.py --check    # fail if the committed file is not what docs/site says

The node does not serve docs/site; the site build does. So the marks are extracted here, at build
time, into one small file the page fetches only in learn mode. Every quote is a VERBATIM span of the
page it cites — this tool never writes a word of its own into `quote`, it only cuts. A docs edit that
moves the prose therefore changes learn.json, `--check` fails in `make lint`, and somebody has to look
at the diff. That is the whole point: the tester guide cannot drift from the documentation it claims
to be quoting, because it is not a copy of it, it is a cut of it.

MARKS below names the cut, not the text: page, the `##` section it must sit inside, and the first and
last few words of the span. Short markers survive a reflow; a pasted paragraph does not. Each entry
also carries the page's own `# Title` as `page_title`, so the card can cite "From <title> · <section>"
the way the site names it, rather than by a path in this repository.

The marks explain what the node is FOR and what it PUBLISHES as well as how to read the ladder: the
purpose and the DIDO rule from introduction.md sit on the foot and on the request ledger, and every
registered section carries at least one mark (tests/test_learn.py holds the page to that).

`more` is the only prose here, and it is the PAGE talking about itself — what this dashboard draws,
in the dashboard's voice — never a paraphrase of the docs. The card labels it as such.

`questions` is two short questions per mark in each locale, the ask pane's chips while that mark's card
is in focus. They are the page asking, never the documentation answering.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "docs" / "site"
OUT = ROOT / "app" / "static" / "learn.json"
# The documentation as the node can read it: every page of docs/site cut at its `##` headings, for
# GET /docs/search. data/ is mounted into the container and docs/ is not, so this is the copy made at
# build time rather than at request time. It is a copy, not an index: the route reads it with a substring.
DOCS_OUT = ROOT / "data" / "docs_site.json"
DOCS = "https://planetai.fab.city/docs"

# A quote is a counting unit like a sign: it has to be readable on its own, at the size the panel
# gives it. Sixty words is the ceiling the prompt set and it is about right — past that a reader
# stops reading and the mark has failed.
MAX_WORDS = 60

# key · title · page · section (None = the page's lead, above the first heading) · first words · last
# words · the page's own line. The order here is only the order learn.json lists them in, and the
# order Back and Next fall back to for a mark that is not on the view being read. The walk itself
# follows the page: dashboard.js steps through the marks in the order the current view drew them,
# top to bottom. Grouped below by where each mark is drawn.
MARKS = [
    ("dial", "The ladder: one rung per resolution", "dashboard.md", "The lead",
     "The **ladder** sits above the lead", "are struck through.",
     "The rungs that may leave the machine are drawn as a dotted texture rather than the cells "
     "blue, so blue keeps its one meaning on this page: an H3 cell. Under the ladder, a fold draws "
     "one cell at the rung you are on against the rungs either side, to scale, and what each "
     "thing this node speaks for costs to cover at it."),
    ("lead", "The lead", "dashboard.md", "The lead",
     "The first thing on Now", "a why line and the rule.",
     "The node computes and the page draws. A number this page worked out for itself would be a "
     "bug, which is why the sentence, the numeral and the state word all arrive from GET /issues."),
    ("containment", "Exact in the index, approximate on the ground", "dashboard.md", "The lead",
     "At resolution 8 one cell is", "how many of those are its own.",
     "That is the documentation's example resolution line. The one on Network, under What each rung "
     "is worth, is tonight's, read from this node, and when the neighbouring rungs give the same "
     "answer the page says so."),
    ("distances", "Four distances, not four resolutions", "concepts.md", "Sources and sensors",
     "**The four distances.**", "sekitar · wilayah.",
     "The page prints them as house, street, ring and region, on one scale, so the eye can answer "
     "whether it is me or everywhere without arithmetic."),
    ("prov", "Provenance words", "concepts.md", "Provenance words on the page",
     "`live`: measured by this node", "the node's own engine.",
     "Provenance is ink only and square on this page, never a coloured pill, and the full H3 id is "
     "printed once per object and never truncated."),
    ("cell", "The cell this node stands in", "concepts.md", "The node and its place",
     "**The H3 cell.** The node stands", "with its edge length beside it.",
     "Resolution 8 is coarser than the rounding already applied to the node's position, so the "
     "cell drawn on the ground puts nothing back that the node had held out."),
    ("tiles", "What a map costs", "dashboard.md", "The ground",
     "Three bases: `plan`, offline", "`osm`, OpenStreetMap tiles.",
     "The request count sits in the tab bar so the price of switching to satellite is visible "
     "before you pay it: live tiles need MAP_TILES=on, and a press may only ever reduce it."),
    ("stages", "The order the loop runs", "dashboard.md", "The sections",
     "Every section is registered with the page contract",
     "Now draws Decide first.",
     "Observe, decide, act, measure: the four stages of the loop. Now draws Decide first, because "
     "what asks for a person is read first. A section whose data is not on this node prints one "
     "honest line in its place, never a blank and never a guess."),
    ("cards", "Four card kinds and no fifth", "dashboard.md", "The sections",
     "Four card kinds and no fifth:", "a factor of a thousand.",
     "The house is the solid line, the ring dotted, the street and the region dashed, the line "
     "itself dashed red. Where a distance has no source its trace is absent and the legend says "
     "which one."),
    ("states", "States, in weight not hue", "dashboard.md", "Issues, states and distances",
     "For every issue the keeper declared", "or `none` (no record).",
     "State is carried by weight, fill and dash, never by hue: act is set at 700 and the other "
     "states at 500. Colour is argument only: blue a cell, green a loop closed, red a line crossed."),
    ("custody", "Custody: who may be counted", "concepts.md", "Sources and sensors",
     "**`custody`.** A generated column", "still never be counted.",
     "Your own instruments are drawn in ink on this page, the borrowed ones faint, and what only "
     "the satellite knows in orange."),
    ("share", "Reach, not publishing", "sharing.md", "`SHARE_LEVEL`",
     "`SHARE_LEVEL` is reach, not publishing", "it is live within 20\nseconds.",
     "The request ledger below is this page confessing what it asked of the world while you looked "
     "at it. The offline plan asks nothing; Telegram is reached by the node, never by this page."),
    ("raw", "Raw readings stay", "how-it-works.md", "What leaves the machine, and what never does",
     "Raw readings stay.", "under CC BY 4.0",
     "The strips under Observe are hourly means, one cell an hour: the finest time step this "
     "page shows, and still not a raw reading."),
    ("levels", "Three levels, one floor", "alerts.md", "Levels",
     "`ALERT_LEVEL` (default `act`) is the floor", "is written from.",
     "An alert's acted_at stays null until a person acts and records it, with this page's button, "
     "the CLI, the bot, a radio or an agent. It is the one measurement the node cannot make itself."),
    ("current", "Conditions that are not events", "alerts.md", "Conditions that are not events",
     "The dashboard marks\nan open act-level alert", "the alert is still open.",
     "A heat alert is a condition that holds for hours; a cooking spike is an event with a "
     "cooldown. The schema does not yet know an alert can clear, so the page says which it is."),
    ("rho", "ρ: the loop closed", "rho.md", None,
     "ρ (rho) is the share", "rather than an app feature.",
     "The page draws it as the alerts answered over the alerts raised, with the median minutes to the "
     "first answer, and counts the rings rather than sizing them."),
    ("refusals", "Refusals that hold at every stage", "how-it-works.md",
     "Refusals that hold at every stage",
     "No raw readings leave the instance", "not declared from above.",
     "The care label under Measure is those refusals as signs. Nothing to press on the wall is the "
     "wall's own refusal: it is an instruction, not a control."),

    # --- Now: the sections that had no mark ------------------------------------------------------
    ("counted", "Yours, here, and counted", "sensors.md", None,
     "Once one is", "`local` and `custody`.",
     "`planetai sensors` prints these stations one line each, with `yours` or `reference` beside the "
     "id, and GET /sensors is the route a script reads them from. Only the ones in this node's "
     "custody can make a cell say live."),
    ("dido", "Data in, data out", "introduction.md", "What it is for",
     "The rule it runs on", "moves between cities.",
     "On this page the rule is small enough to check: every request this page made of anywhere but "
     "this node is in the ledger below, and the plan base makes none. What the node itself sends "
     "upward, and to whom, is on the Network view."),
    ("forecast", "Context, not a prediction", "packs-reference.md", "forecast",
     "Official and model weather for this point", "it never sends an alert.",
     "The card is drawn from GET /forecast: the wind and the rain for the hours ahead, and a "
     "forecast point more than 10 km from the node is said to be another place. Nothing on this "
     "card can raise an alert."),
    ("events", "What an alert event is", "dashboard.md", "The sections",
     "An event is the bot's own unit", "the message it sent.",
     "Decide is the first section under the lead. The numeral is red only when the peak is past the "
     "issue's line, and the action and the message are the node's words, in the household's "
     "language: this page holds no copy of either."),
    ("buttons", "Done, Not now and Doesn't fit", "dashboard.md", "The sections",
     "**Done**, **Not now** and **Doesn't fit** each write", "keeps the answer as the note.",
     "The first press asks for a name, and this browser keeps it for the next. The labels come "
     "from the node, and an answer needs the act token from another device. ρ does not count "
     "events yet, so none of the three moves it."),
    ("claims", "One number, over how much ground", "dashboard.md", "The sections",
     "\"Whose word, over how much ground\" covers", "that one number has to cover.",
     "The line above the fold names the widest and the narrowest footprint; the fold holds all six. "
     "Each card counts its cells at the rung you are on, so the count moves with the ladder."),
    ("workshop", "The nearest place to make it", "introduction.md", "What it is for",
     "The `make` pack names the nearest fab lab", "is the direction.",
     "In Act, under the record of what was asked, the row with the nearest fab lab is that sentence "
     "where the pack is on: the lab, how far, and the dated archive it came from. With MAKE_ENABLED off, the row is "
     "the node's own help text for that setting instead."),
    ("note", "The note is the record", "cli.md", "Reading the node",
     "`planetai act` is the terminal's way", "record of what was\ndone.",
     "Each row here is one of those records, newest first: who, which stage, how long ago, and "
     "decided first where a decision came before the act."),
    ("bot", "An answer in the household's words", "bot.md", None,
     "Somebody in the house asks", "in\ntheir words, as an act.",
     "An act recorded through the bot lands in this ledger like one pressed on this page, with the "
     "person's own words as its note."),
    ("actions", "The table ρ is counted from", "schema.md", "Tables",
     "The ρ instrument:", "one row per answer.",
     "The note column is shown here only to a reader with a token, because GET /actions is on no "
     "sharing allowlist."),
    ("effect", "Elapsed time, not an effect", "rho.md", "What worked, per rule",
     "It is elapsed time, not an effect.", "and the node cannot tell.",
     "One row per rule, read from GET /effect over the whole record: how many acts, and how many "
     "were followed by the condition stopping. A recovery time in hours appears only for a rule "
     "that declares what it watches."),
    ("figures", "One API, and no private path in", "api.md", None,
     "Every node exposes the same API on port 8080.", "has a private path in.",
     "Every row here arrived in GET /issues as provenance: the figure, its value, where it came "
     "from, the node's word for it and its age. A script or a spreadsheet reads the same route, "
     "with a token, or with none at SHARE_LEVEL=open."),

    # --- Historical ------------------------------------------------------------------------------
    ("shape", "The day this place usually has", "api.md", "Sensors and readings",
     "The day this place usually has: one mean", "(`local`) count.",
     "The page waits for seven local days before it names the worst hour, and until then says how many it "
     "has. GET /shape?metric=pm25 returns the same hours, with how many hourly means went into each."),
    ("figure", "The day, drawn once", "dashboard.md", "The day figure",
     "Each issue with a day has one drawing", "last 14 days.",
     "The figure reads the node's own 24 hourly values for every distance, the usual for each hour from "
     "usual_by_hour, and the alert events from /issues. The page draws them; all it counts is the hours over the "
     "line and above the usual that it draws."),
    ("strips", "One row a day, one cell an hour", "dashboard.md", "The strips",
     "One row a day and one cell an hour", "on Historical.",
     "The strips read GET /issues/days: the same hourly values the lead uses, over up to 90 days, with the node's "
     "own count of hours over the line for each day."),
    ("earth", "It says something changed, never what", "packs-reference.md", "earth",
     "The node's own copy of Google's AlphaEarth", "never what.",
     "The years come from files this node already holds, read through GET /earth, and the node "
     "fetches none of them while you look. `planetai run earth fetch` is how a year gets here."),
    ("reach", "Where this node's own line starts", "install.md", None,
     "This page puts the node itself on a machine", "keeps every reading it takes on this machine.",
     "Each row is one kind of source, with the oldest and newest hourly mean this node holds for it, "
     "from GET /reach. The climate normals the node pulled at install are dated years before it was "
     "switched on; its own sensors start on the day they were first polled."),
    ("trust", "Whether its own sensors tell the truth", "packs-reference.md", "trust",
     "Whether the node's own sensors are telling it the truth", "all three\nwere wrong.",
     "The figures here are GET /trust, one row per local sensor: its coverage over seven days, the "
     "channels that stopped moving, and how old the sensor is, which explains a low coverage without "
     "a fault."),

    # --- Network ---------------------------------------------------------------------------------
    ("parent", "One cell in a district's picture", "federation.md", None,
     "With a parent set", "and nothing else.",
     "The wires on the right are what leaves this node: hourly means to a parent, the Index cells "
     "and ρ. A wire with nothing on it is dashed. `planetai config set PARENT_API_URL` and "
     "`PARENT_TOKEN` give this node a parent."),
    ("registry", "What could be measured here", "sources.md", None,
     "A node measures what its adapters read.", "carried inside every node as a\npinned copy.",
     "The counts here are GET /sources, read the first time somebody opens Network: what the pinned "
     "registry lists for this place, how many entries have code on this node, and the places to make "
     "things and the designs to build. `planetai sources` prints the same list."),
    ("presence", "A coarse cell, and never finer", "channels.md", "Reticulum, LXMF",
     "Presence is separate and off by default", "so an exact place never leaves.",
     "The cell drawn here is the one this node would announce, and its area is the whole of what a "
     "stranger on the radio learns. GET /presence answers with enabled false until "
     "RETICULUM_PRESENCE=1."),
    ("mesh", "Where there is no WiFi", "channels.md", "Meshtastic, the LoRa mesh",
     "For sensors and alerts where there is no WiFi.", "when the\ninternet is down.",
     "What this card counts arrives through the gateway radio's MQTT uplink to this node's own "
     "broker. `planetai meshtastic` sets that up; with MESH_ALERTS=1 an act alert's first line goes "
     "back out over the mesh."),
    ("siting", "Named for its place, in a box made nearby", "sensors.md", "Siting",
     "Name it after the place", "Fab Lab Bali\nprints it.",
     "These are the devices on this node's own ground, with their source, indoors or out, what each "
     "measures and when it last spoke. The row for an open hardware manager says what is not here "
     "yet: design files, firmware, and where nearby a device could be made or mended."),

    # --- Set up ----------------------------------------------------------------------------------
    ("settings", "A setting is a decision", "configuration.md", None,
     "A setting is a decision the household makes", "for an online model.",
     "Each value here says where it came from. A value saved here is live within 20 seconds and wins "
     "over .env, a blank returns the key to .env, and every save is a row in actions with the actor "
     "dashboard."),

    # --- the foot, on every view but the wall ----------------------------------------------------
    ("production", "One computer per place", "introduction.md", None,
     "PLANETAI is hyperlocal compute", "the place already owns.",
     "The foot of every view but the wall opens on this sentence and the purpose that goes with it, "
     "quoted from the documentation rather than rewritten, so this page and the documentation say "
     "the same thing."),
    ("purpose", "What a node is for", "introduction.md", "What it is for",
     "Its purpose is", "around each node.",
     "Every number on this page answers to that purpose. The issues the lead can name are air, heat, "
     "land and coast; water and soil are not among them in this version, so the page draws neither."),
    ("health", "What every screen asks first", "api.md", "Status",
     "What every screen in the house polls.", "outbound request of its own.",
     "The version at the foot is the one GET /health reports. Open it from the foot to read what "
     "every screen here asks first: the node, its version, its cell at resolution 8, its last poll."),
    ("mcp", "The surface an agent holds", "mcp.md", None,
     "This is the surface an agent holds.", "that somebody\nacted.",
     "The foot names POST /mcp for an agent handed this node's address: streamable HTTP, with "
     "Authorization: Bearer and the admin token on every call. `planetai agent` prints the snippet "
     "to paste into a client."),
]


# Two short questions per mark, in each locale: the ask pane's chips while that mark's card is in focus.
# A question the pane can answer from the page and the quote, never a quiz. The id and es strings
# are assistant-written and want a native reader. build() refuses a mark without two in every locale.
QUESTIONS = {
    'dial': {"en": ['Which rung is this page reading at?', 'Why may the coarse rungs leave the machine?'],
        "id": ['Di anak tangga mana halaman ini membaca?', 'Mengapa anak tangga yang kasar boleh keluar dari mesin?'],
        "es": ['¿En qué peldaño está leyendo esta página?', '¿Por qué los peldaños gruesos pueden salir de la máquina?']},
    'lead': {"en": ['Why does this issue lead tonight?', 'What would make another issue lead?'],
        "id": ['Mengapa isu ini memimpin malam ini?', 'Apa yang membuat isu lain memimpin?'],
        "es": ['¿Por qué este asunto va primero esta noche?', '¿Qué haría que otro asunto fuera primero?']},
    'containment': {"en": ["How many stations fall in this node's cell?", 'Why is a cell exact in the index and not on the ground?'],
        "id": ['Berapa stasiun yang jatuh di sel node ini?', 'Mengapa sel tepat di indeks tetapi tidak di lapangan?'],
        "es": ['¿Cuántas estaciones caen en la celda de este nodo?', '¿Por qué una celda es exacta en el índice y no sobre el terreno?']},
    'distances': {"en": ['What are the four distances for this house?', 'Which distance is missing here, and why?'],
        "id": ['Apa empat jarak untuk rumah ini?', 'Jarak mana yang tidak ada di sini, dan mengapa?'],
        "es": ['¿Cuáles son las cuatro distancias de esta casa?', '¿Qué distancia falta aquí, y por qué?']},
    'prov': {"en": ['Which numbers here are live and which are modelled?', 'What does partial mean on this page?'],
        "id": ['Angka mana yang langsung dan mana yang dimodelkan?', 'Apa arti sebagian di halaman ini?'],
        "es": ['¿Qué cifras son en vivo y cuáles son de un modelo?', '¿Qué significa parcial en esta página?']},
    'cell': {"en": ['How big is the cell this node stands in?', 'Who can see this cell and who cannot?'],
        "id": ['Seberapa besar sel tempat node ini berdiri?', 'Siapa yang bisa melihat sel ini dan siapa yang tidak?'],
        "es": ['¿Qué tamaño tiene la celda donde está este nodo?', '¿Quién puede ver esta celda y quién no?']},
    'tiles': {"en": ['What does the satellite map send, and to whom?', 'Why is the offline plan the default?'],
        "id": ['Apa yang dikirim peta satelit, dan kepada siapa?', 'Mengapa denah luring menjadi bawaan?'],
        "es": ['¿Qué envía el mapa satelital, y a quién?', '¿Por qué el plano sin conexión es el predeterminado?']},
    'stages': {"en": ['Where is this house in the loop right now?', 'What happens between deciding and acting?'],
        "id": ['Di mana rumah ini dalam lingkaran sekarang?', 'Apa yang terjadi antara memutuskan dan bertindak?'],
        "es": ['¿En qué punto del ciclo está esta casa ahora?', '¿Qué pasa entre decidir y actuar?']},
    'cards': {"en": ['Which kind of card is this?', 'Why are there only four kinds?'],
        "id": ['Kartu jenis apa ini?', 'Mengapa hanya ada empat jenis?'],
        "es": ['¿Qué tipo de tarjeta es esta?', '¿Por qué hay solo cuatro tipos?']},
    'states': {"en": ['What state is each issue in tonight?', 'Why are states not shown in colour?'],
        "id": ['Dalam keadaan apa setiap isu malam ini?', 'Mengapa keadaan tidak ditunjukkan dengan warna?'],
        "es": ['¿En qué estado está cada asunto esta noche?', '¿Por qué los estados no se muestran con color?']},
    'custody': {"en": ['Which sensors does this node count as its own?', "Why is a neighbour's sensor not counted?"],
        "id": ['Sensor mana yang dihitung node ini sebagai miliknya?', 'Mengapa sensor tetangga tidak dihitung?'],
        "es": ['¿Qué sensores cuenta este nodo como suyos?', '¿Por qué no se cuenta el sensor de un vecino?']},
    'share': {"en": ['Who can read this page without a token?', 'What changes if SHARE_LEVEL is open?'],
        "id": ['Siapa yang bisa membaca halaman ini tanpa token?', 'Apa yang berubah jika SHARE_LEVEL terbuka?'],
        "es": ['¿Quién puede leer esta página sin token?', '¿Qué cambia si SHARE_LEVEL está en open?']},
    'raw': {"en": ['What leaves this machine, and what never does?', 'Where are the raw readings kept?'],
        "id": ['Apa yang keluar dari mesin ini, dan apa yang tidak pernah?', 'Di mana bacaan mentah disimpan?'],
        "es": ['¿Qué sale de esta máquina, y qué nunca sale?', '¿Dónde se guardan las lecturas en bruto?']},
    'levels': {"en": ['What is the difference between act, warn and info?', 'Which alerts reach me on Telegram?'],
        "id": ['Apa beda act, warn dan info?', 'Peringatan mana yang sampai ke saya di Telegram?'],
        "es": ['¿Qué diferencia hay entre act, warn e info?', '¿Qué alertas me llegan por Telegram?']},
    'current': {"en": ['Is this a condition or an event?', 'Why does the node not alert on every reading?'],
        "id": ['Apakah ini keadaan atau kejadian?', 'Mengapa node tidak memberi peringatan untuk setiap bacaan?'],
        "es": ['¿Es una condición o un evento?', '¿Por qué el nodo no avisa con cada lectura?']},
    'rho': {"en": ["What is this node's ρ, and what counts toward it?", 'How do I close the loop on an alert?'],
        "id": ['Berapa ρ node ini, dan apa yang dihitung?', 'Bagaimana saya menutup lingkaran pada sebuah peringatan?'],
        "es": ['¿Cuál es la ρ de este nodo, y qué cuenta para ella?', '¿Cómo cierro el ciclo de una alerta?']},
    'refusals': {"en": ['What will this node always refuse to do?', 'Can an agent change a setting here?'],
        "id": ['Apa yang selalu ditolak node ini?', 'Bisakah agen mengubah pengaturan di sini?'],
        "es": ['¿Qué se negará siempre a hacer este nodo?', '¿Puede un agente cambiar un ajuste aquí?']},
    'counted': {"en": ['Which of these stations are ours and here?', 'What makes a sensor counted?'],
        "id": ['Stasiun mana yang milik kita dan ada di sini?', 'Apa yang membuat sebuah sensor dihitung?'],
        "es": ['¿Cuáles de estas estaciones son nuestras y están aquí?', '¿Qué hace que un sensor cuente?']},
    'dido': {"en": ['What data comes in to this node?', 'What data goes out, and how coarse is it?'],
        "id": ['Data apa yang masuk ke node ini?', 'Data apa yang keluar, dan seberapa kasar?'],
        "es": ['¿Qué datos entran en este nodo?', '¿Qué datos salen, y con qué detalle?']},
    'forecast': {"en": ['What is the forecast for the next hours?', 'Why is a forecast context and not a prediction?'],
        "id": ['Apa prakiraan untuk beberapa jam ke depan?', 'Mengapa prakiraan adalah konteks, bukan ramalan?'],
        "es": ['¿Cuál es el pronóstico para las próximas horas?', '¿Por qué un pronóstico es contexto y no una predicción?']},
    'events': {"en": ['What is an alert event, and how is it different from an alert?', 'Why is there one card for several rule rows?'],
        "id": ['Apa itu kejadian peringatan, dan apa bedanya dengan peringatan?', 'Mengapa hanya ada satu kartu untuk beberapa baris aturan?'],
        "es": ['¿Qué es un evento de alerta, y en qué se diferencia de una alerta?', '¿Por qué hay una sola tarjeta para varias filas de reglas?']},
    'buttons': {"en": ['What does each of the three buttons record?', 'What happens to the card when I put it off?'],
        "id": ['Apa yang dicatat oleh masing-masing dari tiga tombol itu?', 'Apa yang terjadi pada kartu jika saya menundanya?'],
        "es": ['¿Qué registra cada uno de los tres botones?', '¿Qué pasa con la tarjeta si la dejo para más tarde?']},
    'claims': {"en": ['How much ground does this number cover?', 'Why does the number change with the rung?'],
        "id": ['Seberapa luas wilayah yang dicakup angka ini?', 'Mengapa angkanya berubah dengan anak tangga?'],
        "es": ['¿Cuánto terreno cubre esta cifra?', '¿Por qué la cifra cambia con el peldaño?']},
    'workshop': {"en": ['Where is the nearest place to make something?', 'Why does the node point to a workshop?'],
        "id": ['Di mana tempat terdekat untuk membuat sesuatu?', 'Mengapa node menunjuk ke bengkel?'],
        "es": ['¿Dónde está el lugar más cercano para fabricar algo?', '¿Por qué el nodo señala un taller?']},
    'note': {"en": ['What should my note say?', 'Who reads the notes I write?'],
        "id": ['Apa yang harus ditulis dalam catatan saya?', 'Siapa yang membaca catatan yang saya tulis?'],
        "es": ['¿Qué debería decir mi nota?', '¿Quién lee las notas que escribo?']},
    'bot': {"en": ['How do I ask the bot on Telegram?', 'Which model answers, and where does it run?'],
        "id": ['Bagaimana cara bertanya ke bot di Telegram?', 'Model mana yang menjawab, dan di mana ia berjalan?'],
        "es": ['¿Cómo pregunto al bot en Telegram?', '¿Qué modelo responde, y dónde se ejecuta?']},
    'actions': {"en": ['What is recorded when someone acts?', 'How is ρ counted from these rows?'],
        "id": ['Apa yang dicatat saat seseorang bertindak?', 'Bagaimana ρ dihitung dari baris-baris ini?'],
        "es": ['¿Qué se registra cuando alguien actúa?', '¿Cómo se cuenta ρ a partir de estas filas?']},
    'effect': {"en": ['Which of our actions seem to work?', 'Why is elapsed time not an effect?'],
        "id": ['Tindakan kita mana yang tampaknya berhasil?', 'Mengapa waktu yang berlalu bukan efek?'],
        "es": ['¿Cuáles de nuestras acciones parecen funcionar?', '¿Por qué el tiempo transcurrido no es un efecto?']},
    'figures': {"en": ['Where does each number on this page come from?', 'Can I read these figures from my own tools?'],
        "id": ['Dari mana setiap angka di halaman ini berasal?', 'Bisakah saya membaca angka ini dari alat saya sendiri?'],
        "es": ['¿De dónde sale cada cifra de esta página?', '¿Puedo leer estas cifras con mis propias herramientas?']},
    'shape': {"en": ['What does a usual day look like here?', 'Is today different from the usual day?'],
        "id": ['Seperti apa hari biasa di sini?', 'Apakah hari ini berbeda dari biasanya?'],
        "es": ['¿Cómo es un día normal aquí?', '¿Es hoy distinto de un día normal?']},
    'figure': {"en": ['What does the grey band mean?', 'Which hours were over the line today?'],
        "id": ['Apa arti pita abu-abu itu?', 'Jam berapa saja yang melewati garis hari ini?'],
        "es": ['¿Qué significa la banda gris?', '¿Qué horas pasaron la línea hoy?']},
    'strips': {"en": ['At what hour is the air usually worst here?', 'Which days were over the line?'],
        "id": ['Jam berapa udara biasanya paling buruk di sini?', 'Hari apa saja yang melewati garis?'],
        "es": ['¿A qué hora suele estar peor el aire aquí?', '¿Qué días pasaron la línea?']},
    'earth': {"en": ['What changed on the ground around here?', 'Why can the satellite not say what changed?'],
        "id": ['Apa yang berubah di tanah sekitar sini?', 'Mengapa satelit tidak bisa mengatakan apa yang berubah?'],
        "es": ['¿Qué cambió en el terreno de alrededor?', '¿Por qué el satélite no puede decir qué cambió?']},
    'reach': {"en": ["Where does this node's own line start?", 'Who does this node reach?'],
        "id": ['Di mana garis node ini sendiri dimulai?', 'Siapa yang dijangkau node ini?'],
        "es": ['¿Dónde empieza la línea propia de este nodo?', '¿A quién llega este nodo?']},
    'trust': {"en": ["Are this node's sensors telling the truth?", 'Which sensor looks stuck or silent?'],
        "id": ['Apakah sensor node ini jujur?', 'Sensor mana yang tampak macet atau diam?'],
        "es": ['¿Dicen la verdad los sensores de este nodo?', '¿Qué sensor parece atascado o callado?']},
    'parent': {"en": ['What does this node send to its district?', 'How does this cell join the Index?'],
        "id": ['Apa yang dikirim node ini ke distriknya?', 'Bagaimana sel ini bergabung dengan Index?'],
        "es": ['¿Qué envía este nodo a su distrito?', '¿Cómo entra esta celda en el Índice?']},
    'registry': {"en": ['What else could be measured here?', 'Which open sources cover this place?'],
        "id": ['Apa lagi yang bisa diukur di sini?', 'Sumber terbuka mana yang mencakup tempat ini?'],
        "es": ['¿Qué más se podría medir aquí?', '¿Qué fuentes abiertas cubren este lugar?']},
    'presence': {"en": ['What does this node announce over radio?', 'How coarse is the cell it announces?'],
        "id": ['Apa yang diumumkan node ini lewat radio?', 'Seberapa kasar sel yang diumumkannya?'],
        "es": ['¿Qué anuncia este nodo por radio?', '¿Con qué detalle anuncia su celda?']},
    'mesh': {"en": ['How does the mesh work without WiFi?', 'Which radios can hear this node?'],
        "id": ['Bagaimana mesh bekerja tanpa WiFi?', 'Radio mana yang bisa mendengar node ini?'],
        "es": ['¿Cómo funciona la malla sin WiFi?', '¿Qué radios pueden oír a este nodo?']},
    'siting': {"en": ['Where should a sensor go in this house?', 'Why is a sensor named for its place?'],
        "id": ['Di mana sebaiknya sensor ditaruh di rumah ini?', 'Mengapa sensor dinamai menurut tempatnya?'],
        "es": ['¿Dónde debería ir un sensor en esta casa?', '¿Por qué un sensor lleva el nombre de su lugar?']},
    'settings': {"en": ['Which setting should I look at first?', 'Who can change a setting, and how is it recorded?'],
        "id": ['Pengaturan mana yang harus saya lihat dulu?', 'Siapa yang bisa mengubah pengaturan, dan bagaimana dicatat?'],
        "es": ['¿Qué ajuste debería mirar primero?', '¿Quién puede cambiar un ajuste, y cómo queda registrado?']},
    'production': {"en": ['Why one computer per place?', 'What does distributed production mean for this house?'],
        "id": ['Mengapa satu komputer untuk satu tempat?', 'Apa arti produksi terdistribusi bagi rumah ini?'],
        "es": ['¿Por qué un ordenador por lugar?', '¿Qué significa la producción distribuida para esta casa?']},
    'purpose': {"en": ['What is this node for?', 'How does it help the air, water and soil here?'],
        "id": ['Untuk apa node ini?', 'Bagaimana node ini membantu udara, air dan tanah di sini?'],
        "es": ['¿Para qué sirve este nodo?', '¿Cómo ayuda al aire, el agua y el suelo de aquí?']},
    'health': {"en": ['Is this node healthy right now?', 'What does a screen check first?'],
        "id": ['Apakah node ini sehat sekarang?', 'Apa yang diperiksa layar pertama kali?'],
        "es": ['¿Está sano este nodo ahora mismo?', '¿Qué comprueba primero una pantalla?']},
    'mcp': {"en": ['What can an agent do through MCP here?', 'Which tools are read, act and admin?'],
        "id": ['Apa yang bisa dilakukan agen lewat MCP di sini?', 'Alat mana yang read, act dan admin?'],
        "es": ['¿Qué puede hacer un agente por MCP aquí?', '¿Qué herramientas son read, act y admin?']},
}

def slugify(value):
    """build_docs.py's own slug, for the page-per-folder build where the prefix is empty."""
    s = re.sub(r"[^\w\s-]", "", value.lower(), flags=re.U).strip()
    return re.sub(r"[\s_-]+", "-", s) or "section"


def section_body(text, heading):
    """The markdown under one `##`, or everything above the first one when heading is None."""
    heads = [(m.start(), m.group(1)) for m in re.finditer(r"^## (.+)$", text, re.M)]
    if heading is None:
        end = heads[0][0] if heads else len(text)
        return text[text.index("\n", text.index("# ")):end]
    for i, (at, name) in enumerate(heads):
        if name.strip() == heading:
            stop = heads[i + 1][0] if i + 1 < len(heads) else len(text)
            return text[at:stop]
    return None


def cut(body, first, last):
    a = body.find(first)
    if a < 0:
        return None, f"the span does not start there: {first!r}"
    b = body.find(last, a)
    if b < 0:
        return None, f"the span starts but does not end there: {last!r}"
    return body[a:b + len(last)], None


def build():
    marks, errs = {}, []
    for key, title, page, heading, first, last, more in MARKS:
        src = SITE / page
        if not src.exists():
            errs.append(f"{key}: docs/site/{page} does not exist")
            continue
        text = src.read_text(encoding="utf-8")
        head = re.match(r"# (.+)", text)
        body = section_body(text, heading)
        if body is None:
            errs.append(f"{key}: docs/site/{page} has no section '{heading}'")
            continue
        quote, why = cut(body, first, last)
        if quote is None:
            errs.append(f"{key}: in docs/site/{page} · {heading or 'the lead'}, {why}")
            continue
        n = len(quote.split())
        if n > MAX_WORDS:
            errs.append(f"{key}: the span is {n} words, over the {MAX_WORDS} the panel holds")
            continue
        qs = QUESTIONS.get(key) or {}
        if not all(isinstance(qs.get(l), list) and len(qs[l]) == 2 and all(qs[l]) for l in ("en", "id", "es")):
            errs.append(f"{key}: QUESTIONS needs two questions in each of en, id and es")
            continue
        anchor = slugify(heading) if heading else ""
        marks[key] = {
            "questions": qs,
            "title": title,
            "quote": quote,
            "more": more,
            "page": page,
            # The page's own `# Title`, which is what the site's sidebar calls it and what the panel
            # cites. A repository path means nothing to a household reading the panel.
            "page_title": head.group(1).strip() if head else page[:-3],
            "section": heading or "",
            "anchor": anchor,
            "url": f"{DOCS}/{page[:-3]}/" + (f"#{anchor}" if anchor else ""),
        }
    return {"order": [m[0] for m in MARKS], "marks": marks}, errs


def docs_copy():
    """Every page of docs/site, one row per `##` section and one for the page's lead."""
    rows = []
    for src in sorted(SITE.glob("*.md")):
        text = re.sub(r"^<!-- checked: v[0-9.]+ -->\n?", "", src.read_text(encoding="utf-8"), flags=re.M)
        head = re.match(r"# (.+)", text)
        title = head.group(1).strip() if head else src.stem
        heads = [None] + [m.group(1).strip() for m in re.finditer(r"^## (.+)$", text, re.M)]
        for h in heads:
            try:
                body = section_body(text, h)
            except ValueError:
                body = None
            if not body or not body.strip():
                continue
            rows.append({"page": src.name, "anchor": slugify(h) if h else "",
                         "title": f"{title} · {h}" if h else title,
                         "text": re.sub(r"\s+", " ", re.sub(r"^## .+$", "", body, count=1, flags=re.M)).strip()})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="compare the committed learn.json with what docs/site says now")
    args = ap.parse_args()

    out, errs = build()
    if errs:
        sys.exit("learn marks that no longer have a span in docs/site:\n  "
                 + "\n  ".join(errs)
                 + "\n\nEdit tools/build_learn.py so the markers point at the prose as it reads "
                   "now. Do not paraphrase: the quote is a cut of the page, not a copy.")

    text = json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    docs = docs_copy()
    docs_text = json.dumps(docs, ensure_ascii=False, separators=(",", ":")) + "\n"
    if args.check:
        have = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if have != text:
            sys.exit("app/static/learn.json is not what docs/site says. Run `make learn` and look "
                     "at the diff: a quote moved because the documentation moved.")
        if (DOCS_OUT.read_text(encoding="utf-8") if DOCS_OUT.exists() else "") != docs_text:
            sys.exit("data/docs_site.json is not what docs/site says. Run `make learn`: GET /docs/search "
                     "reads that copy, and a stale one answers with last week's documentation.")
        print(f"  learn.json: {len(out['marks'])} marks, every quote still a span of its page; "
              f"docs_site.json: {len(docs)} sections")
        return
    OUT.write_text(text, encoding="utf-8")
    DOCS_OUT.write_text(docs_text, encoding="utf-8")
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(out['marks'])} marks, "
          f"and {DOCS_OUT.relative_to(ROOT)}: {len(docs)} sections")


if __name__ == "__main__":
    main()
