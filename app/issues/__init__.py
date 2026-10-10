"""Issues — what a place can be better or worse at, that a household recognises by name.

The core measures nothing in particular (docs/DOMAINS.md, first line). The dashboard was the one
component that did: it knew the word `pm25`, it knew WHO 15, and it worked out for itself which
sensor was "the room". This package is where that knowledge moves, so the page can go back to
drawing.

One `.yml` per issue, in this directory. Each declares its name in three languages, whether it is
sensed or context, its metric and unit, its line, which packs feed it, how each of the four
distances is computed, its sentence templates, and what to say with no source. **Adding a fifth
issue is a fifth `.yml` plus a pack that declares its domain, and nothing else changes** —
`tests/test_issues.py` asserts exactly that by loading a synthetic `water.yml`.

Loading is as dumb as `app/packs.py`: read the directory, parse the YAML, validate, log and skip
anything broken. A malformed file must not take the node down; `make lint` is where a broken file in
this repo gets caught.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

log = logging.getLogger("planetai.issues")
HERE = Path(__file__).resolve().parent

LOCALES = ("en", "id", "es")
KINDS = ("sensed", "context")

# The four distances, in order. From schema.py so there is one list, not two.
from .schema import DISTANCES  # noqa: E402  (kept here so `issues.DISTANCES` reads naturally)

# The attribution classifier's classes. A sensed issue needs a sentence for every one of them,
# because the classifier will hand it any of them and a missing template is a `{brace}` on a wall.
CLASSES = ("clear", "inside", "everywhere", "outside_worse", "mixed", "unknown")

# The five states. `act` · `notable` · `quiet` are said with the attribution sentence; `context` and
# `none` have nothing to attribute, so they are said with their own.
STATE_SENTENCES = ("context", "none")

# Everything a template may ask for, and nothing else. The engine fills all of them; a template
# using a name that is not here would render a literal brace to somebody's kitchen wall.
# `span` and `since` are the land record's own history: "between 2024 and 2025", "8.5 % since 2017".
# They fill from the earth cell's `extra` and are empty for every other issue, so a template that
# names them on an issue that cannot fill them renders a clean sentence rather than a brace.
# `line` is the live relation to the issue's line, computed from the value (over · near · under),
# and `event` the clause for the day it crossed and came back — both empty when there is nothing
# true to say, so the sentence never asserts what the reading denies.
PLACEHOLDERS = ("verb", "n", "unit", "where", "cmp", "span", "since", "line", "event")

WHERE_FROM = ("stats", "observations", "earth")
AGGREGATES = ("mean", "median", "fenced_median")
FUNCTIONS = ("apparent",)
COMPARE_MODES = ("ratio", "difference")
# A hero's stamp is a time of day for anything read every few minutes, and a date plus the next look
# for anything read once a year: "at 21:24" about land would be a claim about this evening's ground.
HERO_CLOCKS = ("time", "date")
TRENDS = ("rising", "steady", "falling")

# The words shared by every issue, so four files do not carry four copies of "the street". An issue
# overrides one of these with its own `where:` block — land and coast both rename `region`, because
# "over this square of the map" is not where a wave is.
WHERE_WORDS = {
    "en": {"room": "in the house", "yard": "on the street", "ring": "in the ring around it",
           "region": "over this square of the map"},
    "id": {"room": "di dalam rumah", "yard": "di jalan", "ring": "di sekitarnya",
           "region": "di atas kotak peta ini"},
    "es": {"room": "dentro de casa", "yard": "en la calle", "ring": "en los alrededores",
           "region": "sobre este cuadrado del mapa"},
}
# The same four places as things a number can be compared WITH, which is a different phrase in every
# language and in English too: "over on the street" is not a sentence.
NOUN_WORDS = {
    "en": {"room": "the house", "yard": "the street", "ring": "the ring", "region": "the region"},
    "id": {"room": "rumah", "yard": "jalan", "ring": "sekitarnya", "region": "wilayah"},
    # "la región" takes no contraction, so the three templates that forced "lo que dice el modelo"
    # (por encima de + el) read correctly with the plain noun again.
    "es": {"room": "la casa", "yard": "la calle", "ring": "los alrededores", "region": "la región"},
}
# The four distances as column headings: short, and the same four words wherever they appear.
#
# CHANGED 23 September 2026 (R25), following the programme page. The page names the four distances
# house · street · ring · region, and Tomas decided the node and the documentation say the same, so
# a reader moving between the programme page, the docs and this dashboard meets one vocabulary. The
# rule from 21 September holds: a heading and the sentence under it name the same thing, in every
# language, which is why WHERE_WORDS and NOUN_WORDS moved with this table. Indonesian and Spanish
# translate the English words rather than borrowing them; both want a native reader's pass.
#
# The API KEYS do not change. `room/yard/ring/region` are what `/issues.distances` publishes, what
# every issue's `stack` is keyed on and what a pack's `where:` block overrides; renaming those would
# be a wire break for a wording problem. Only the words a person reads change.
LABEL_WORDS = {
    "en": {"room": "house", "yard": "street", "ring": "ring", "region": "region"},
    "id": {"room": "rumah", "yard": "jalan", "ring": "sekitar", "region": "wilayah"},
    "es": {"room": "casa", "yard": "calle", "ring": "alrededores", "region": "región"},
}
# {cmp} is assembled from these. Never a bare number: a comparison a household can read.
# "a, b and c". The list separator the sentences use when one comparison covers several distances.
JOIN_WORDS = {"en": "and", "id": "dan", "es": "y"}
CMP_WORDS = {
    "en": {"over": "over {noun}", "under": "under {noun}", "level": "level with {noun}"},
    "id": {"over": "di atas {noun}", "under": "di bawah {noun}", "level": "setara dengan {noun}"},
    "es": {"over": "por encima de {noun}", "under": "por debajo de {noun}", "level": "igual que {noun}"},
}
# Why an issue is in the state it is in. The engine returns the code and the rendered line, so the
# page draws a kicker without owning any of these words. Eight codes, three locales, one table.
# How the land record says when. `between` takes the two years of the latest comparison; `since`
# takes the longest span the pack computed and its figure, and carries its own full stop because the
# template puts it between two sentences and it is often absent.
SPAN_WORDS = {
    "en": {"between": "between {a} and {b}", "since": "{pct} % since {year}."},
    "id": {"between": "antara {a} dan {b}", "since": "{pct} % sejak {year}."},
    "es": {"between": "entre {a} y {b}", "since": "{pct} % desde {year}."},
}
# Simple mode's whole answer: one sentence per stage, written HERE and never in the browser. A
# sentence about what was observed is a claim about the data, and the page draws what the node
# computes. Four sentences, three languages, and every figure in them is already in the bundle.
#
# `measure` deliberately does not report rho. rho is specified in docs/SPEC_rho.md over its own
# window and computed by app/index.py from a query this engine cannot make — `Replay` answers five
# table reads and no more, so a fixture could not render it. A second rho computed from a different
# window would be a second rho, and two of them disagreeing on one page is worse than one of them
# being absent. This sentence reports the ledger the Act stage draws, and says that is what it is.
DIGEST_WORDS = {
    "en": {
        "observe": "{issues} issues watched here, read from {stations} stations. "
                   "{headline} has the most to say: it is {phrase}.",
        "observe_none": "{issues} issues watched here, and no station is reading any of them.",
        "decide": "At resolution {res} one cell is {area} m\u00b2, and this node's {stations} stations "
                  "fall in {occupied} of them, {mine} in its own cell. The node says where it is "
                  "to about {metres} m, and {leave}.",
        "act": "{open} alerts are open, {top} of them about {issue}. "
               "Somebody in the house has answered {answered}.",
        "act_none": "Nothing is open. Somebody in the house has answered {answered}.",
        "measure": "Of the {acts} alerts here that asked for something, {answered} have been "
                   "answered, and the usual wait was {median} minutes.",
        "measure_none": "Of the {acts} alerts here that asked for something, none have been "
                        "answered yet.",
        "measure_empty": "Nothing here has asked anybody to do anything.",
        "stays": "nothing at this resolution leaves the machine",
        "leaves": "this resolution may leave the machine",
        "state": {"act": "over the line and asking for something", "notable": "worth a look",
                  "quiet": "quiet", "context": "context, and it never asks",
                  "none": "reading nothing"},
    },
    "id": {
        "observe": "{issues} isu dipantau di sini, dibaca dari {stations} stasiun. "
                   "{headline} paling banyak bicara: {phrase}.",
        "observe_none": "{issues} isu dipantau di sini, dan tidak ada stasiun yang membacanya.",
        "decide": "Pada resolusi {res} satu sel seluas {area} m\u00b2, dan {stations} stasiun node ini "
                  "jatuh di {occupied} di antaranya, {mine} di selnya sendiri. Node menyebut "
                  "posisinya sampai sekitar {metres} m, dan {leave}.",
        "act": "{open} peringatan terbuka, {top} di antaranya tentang {issue}. "
               "Seseorang di rumah telah menjawab {answered}.",
        "act_none": "Tidak ada yang terbuka. Seseorang di rumah telah menjawab {answered}.",
        "measure": "Dari {acts} peringatan di sini yang meminta sesuatu, {answered} telah dijawab, "
                   "dan waktu tunggu biasanya {median} menit.",
        "measure_none": "Dari {acts} peringatan di sini yang meminta sesuatu, belum ada yang "
                        "dijawab.",
        "measure_empty": "Tidak ada di sini yang meminta siapa pun melakukan sesuatu.",
        "stays": "tidak ada pada resolusi ini yang keluar dari mesin",
        "leaves": "resolusi ini boleh keluar dari mesin",
        "state": {"act": "di atas garis dan meminta sesuatu", "notable": "layak dilihat",
                  "quiet": "tenang", "context": "konteks, dan tidak pernah meminta",
                  "none": "tidak membaca apa pun"},
    },
    "es": {
        "observe": "{issues} asuntos vigilados aqu\u00ed, le\u00eddos desde {stations} estaciones. "
                   "{headline} es el que m\u00e1s dice: {phrase}.",
        "observe_none": "{issues} asuntos vigilados aqu\u00ed, y ninguna estaci\u00f3n lee ninguno.",
        "decide": "En la resoluci\u00f3n {res} una celda son {area} m\u00b2, y las {stations} estaciones "
                  "de este nodo caen en {occupied} de ellas, {mine} en la suya propia. El nodo "
                  "dice d\u00f3nde est\u00e1 con unos {metres} m, y {leave}.",
        "act": "{open} alertas abiertas, {top} de ellas sobre {issue}. "
               "Alguien en la casa ha respondido {answered}.",
        "act_none": "No hay nada abierto. Alguien en la casa ha respondido {answered}.",
        "measure": "De las {acts} alertas de aqu\u00ed que ped\u00edan algo, {answered} han sido "
                   "respondidas, y la espera habitual fue de {median} minutos.",
        "measure_none": "De las {acts} alertas de aqu\u00ed que ped\u00edan algo, ninguna ha sido "
                        "respondida todav\u00eda.",
        "measure_empty": "Nada de aqu\u00ed ha pedido a nadie que haga nada.",
        "stays": "nada a esta resoluci\u00f3n sale de la m\u00e1quina",
        "leaves": "esta resoluci\u00f3n puede salir de la m\u00e1quina",
        "state": {"act": "por encima de la l\u00ednea y pide algo", "notable": "merece una mirada",
                  "quiet": "tranquilo", "context": "contexto, y nunca pide nada",
                  "none": "no lee nada"},
    },
}
# The hero's stamp and its line's name. `time` is when the numeral was read; `date` is when a yearly
# record looked and when it looks next, because the satellite does not look again tomorrow.
HERO_WORDS = {
    "en": {"time": "read at {t}", "date": "looked at in {d} · next look {n}", "line": "the line",
           "months": ("January", "February", "March", "April", "May", "June", "July", "August",
                      "September", "October", "November", "December")},
    "id": {"time": "dibaca pukul {t}", "date": "dilihat pada {d} · berikutnya {n}", "line": "batas",
           "months": ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus",
                      "September", "Oktober", "November", "Desember")},
    "es": {"time": "leído a las {t}", "date": "visto en {d} · la próxima vez, {n}",
           "line": "el límite",
           "months": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                      "septiembre", "octubre", "noviembre", "diciembre")},
}
# Simple mode's paragraph, `digest.simple`: three sentences for the three questions, written here and
# never in the browser. Approved by Tomas 25 September 2026. Counts agree in number through the pairs
# below (Indonesian has one form); `{when}` is a time of day for an alert raised today and a date
# otherwise, and `{since}` is the later of thirty days ago and the oldest alert this read reached.
SIMPLE_WORDS = {
    "en": {"own": ("{n} station of its own", "{n} stations of its own"),
           "near": ("{n} other station", "{n} other stations"),
           "times": ("once", "{n} times"),
           "stations": "This house has {own}, and {near} within a kilometre.",
           "stations_far": "This house has {own}; the nearest other station is {km} km away.",
           "stations_alone": "This house has {own}, and no other station is near enough to compare.",
           "stations_none": "This house has no station of its own yet, so the node reads the model for "
                            "this point.",
           "ask": "The oldest open alert is #{id}, about {issue}, open since {when}.",
           "ask_none": "Nothing is open.",
           "loop": "Since {since} the node has asked {asked} and somebody answered {answered}; the usual "
                   "wait was {median} minutes.",
           "loop_none": "Since {since} the node has asked {asked} and nobody has answered yet.",
           "loop_empty": "The node has not asked anybody for anything in the last 30 days.",
           "today": "{t}", "date": "{d} {month}"},
    "id": {"own": ("{n} stasiun sendiri", "{n} stasiun sendiri"),
           "near": ("{n} stasiun lain", "{n} stasiun lain"),
           "times": ("{n} kali", "{n} kali"),
           "stations": "Rumah ini punya {own}, dan {near} dalam satu kilometer.",
           "stations_far": "Rumah ini punya {own}; stasiun lain terdekat berjarak {km} km.",
           "stations_alone": "Rumah ini punya {own}, dan tidak ada stasiun lain yang cukup dekat untuk "
                             "dibandingkan.",
           "stations_none": "Rumah ini belum punya stasiun sendiri, jadi node membaca model untuk titik ini.",
           "ask": "Peringatan terbuka paling lama adalah #{id}, tentang {issue}, terbuka sejak {when}.",
           "ask_none": "Tidak ada yang terbuka.",
           "loop": "Sejak {since} node telah meminta {asked} dan seseorang menjawab {answered}; waktu "
                   "tunggu biasanya {median} menit.",
           "loop_none": "Sejak {since} node telah meminta {asked} dan belum ada yang menjawab.",
           "loop_empty": "Node tidak meminta siapa pun melakukan apa pun dalam 30 hari terakhir.",
           "today": "pukul {t}", "date": "{d} {month}"},
    "es": {"own": ("{n} estaci\u00f3n propia", "{n} estaciones propias"),
           "near": ("{n} estaci\u00f3n m\u00e1s", "{n} estaciones m\u00e1s"),
           "times": ("{n} vez", "{n} veces"),
           "stations": "Esta casa tiene {own}, y hay {near} a menos de un kil\u00f3metro.",
           "stations_far": "Esta casa tiene {own}; la estaci\u00f3n m\u00e1s cercana que no es suya est\u00e1 "
                           "a {km} km.",
           "stations_alone": "Esta casa tiene {own}, y no hay otra estaci\u00f3n lo bastante cerca para "
                             "comparar.",
           "stations_none": "Esta casa a\u00fan no tiene estaci\u00f3n propia, as\u00ed que el nodo lee el "
                            "modelo para este punto.",
           "ask": "La alerta abierta m\u00e1s antigua es la #{id}, sobre {issue}, abierta desde {when}.",
           "ask_none": "No hay nada abierto.",
           "loop": "Desde {since} el nodo ha pedido algo {asked} y alguien respondi\u00f3 {answered}; la "
                   "espera habitual fue de {median} minutos.",
           "loop_none": "Desde {since} el nodo ha pedido algo {asked} y nadie ha respondido todav\u00eda.",
           "loop_empty": "El nodo no ha pedido nada a nadie en los \u00faltimos 30 d\u00edas.",
           "today": "las {t}", "date": "el {d} de {month}"},
}
# The ask pane's questions, `digest.prompts`: written from tonight's bundle so the first thing a person
# does in the pane is press rather than face a blank box. A question, never an answer. The first three are
# the ones the pane opens with; the rest are the pool it rotates through (Tomas, 28 Sep 2026). Every one is
# about this node's own issues and alerts, which is all the model is there to answer. `now` is new on
# 28 Sep and its id and es wording has not yet been read by a native speaker.
PROMPT_WORDS = {
    "en": {"lead": "Why is {issue} what the node leads with?", "ask": "What should I do about alert #{id}?",
           "quiet": "Is anything here asking for attention?", "line": "What does the line for {issue} mean?",
           "model": "Where does the {issue} number come from?", "now": "What is {issue} like right now?"},
    "id": {"lead": "Mengapa {issue} yang ditampilkan paling depan?", "ask": "Apa yang harus saya lakukan dengan peringatan #{id}?",
           "quiet": "Apakah ada yang perlu diperhatikan di sini?", "line": "Apa arti batas untuk {issue}?",
           "model": "Dari mana angka {issue} berasal?", "now": "Bagaimana {issue} saat ini?"},
    "es": {"lead": "\u00bfPor qu\u00e9 el nodo empieza por {issue}?", "ask": "\u00bfQu\u00e9 hago con la alerta #{id}?",
           "quiet": "\u00bfHay algo aqu\u00ed que pida atenci\u00f3n?", "line": "\u00bfQu\u00e9 significa el l\u00edmite de {issue}?",
           "model": "\u00bfDe d\u00f3nde sale la cifra de {issue}?", "now": "\u00bfQu\u00e9 dicen ahora mismo los datos de {issue}?"},
}
# The hero's plain line: the other distances and the line in the household's words, under the
# sentence. Approved by Tomas 25 September 2026. The place words are WHERE_WORDS and NOUN_WORDS, so
# "on the street" means the same thing here as in the sentence above it.
PLAIN_WORDS = {
    "en": {"first": "{where} it is {n}", "more": ", and {where} {n}",
           "under": "The line is {line}, and nothing here is over it.",
           "over_one": "The line is {line}, and {over} is over it.",
           "over_many": "The line is {line}, and {over} are over it.",
           "alone": "Nothing else near here reads it.",
           "model": "The node reads this from a model, not from anything here, and it never asks you "
                    "to do anything about it.",
           "yearly": "The satellite looks once a year, and the node never asks you to do anything "
                     "about it."},
    "id": {"first": "{where} angkanya {n}", "more": ", {where} {n}",
           "under": "Batasnya {line}, dan tidak ada yang melewatinya di sini.",
           "over_one": "Batasnya {line}, dan {over} sudah melewatinya.",
           "over_many": "Batasnya {line}, dan {over} sudah melewatinya.",
           "alone": "Tidak ada yang lain di dekat sini yang membacanya.",
           "model": "Node membaca ini dari model, bukan dari apa pun di sini, dan tidak pernah meminta "
                    "Anda melakukan apa pun tentangnya.",
           "yearly": "Satelit melihat setahun sekali, dan node tidak pernah meminta Anda melakukan apa "
                     "pun tentangnya."},
    "es": {"first": "{where} marca {n}", "more": " y {where} {n}",
           "under": "El l\u00edmite es {line}, y aqu\u00ed nada lo supera.",
           "over_one": "El l\u00edmite es {line}, y {over} lo supera.",
           "over_many": "El l\u00edmite es {line}, y {over} lo superan.",
           "alone": "Nada m\u00e1s cerca de aqu\u00ed lo mide.",
           "model": "El nodo lo lee de un modelo, no de nada que haya aqu\u00ed, y nunca te pide que "
                    "hagas nada al respecto.",
           "yearly": "El sat\u00e9lite mira una vez al a\u00f1o, y el nodo nunca te pide que hagas nada "
                     "al respecto."},
}
# Why THIS issue is at the top, in the household's language. The node ranks them, so the node says
# how — a page that keeps its own copy of the rule goes stale the moment the ranking changes, which
# is not hypothetical: v0.59 changed it on 18 September and the sentence describing it lived in
# dashboard.js, where nothing connected the two. A ranking a reader cannot check is the one thing
# this page does not do, so the explanation travels with the ranking.
HEADLINE_RULE = {
    "en": "An open event leads, the most serious first. With none open, the issue with most to say leads. Where two "
          "have as much to say, the one that has moved most in the last three hours. An even tie goes to the order "
          "this place chose, under Set up \u2192 Basics.",
    "id": "Kejadian yang masih terbuka memimpin, yang paling serius lebih dulu. Bila tidak ada, isu yang paling "
          "banyak bicara memimpin. Bila dua sama banyaknya, yang paling berubah dalam tiga jam terakhir. Bila tetap "
          "seri, urutannya mengikuti pilihan tempat ini, di Set up \u2192 Basics.",
    "es": "Lidera un evento abierto, el m\u00e1s grave primero. Si no hay ninguno, lidera el asunto que m\u00e1s "
          "tiene que decir. Si dos dicen otro tanto, el que m\u00e1s se ha movido en las \u00faltimas tres horas. Si "
          "hay empate exacto, manda el orden que eligi\u00f3 este lugar, en Set up \u2192 Basics.",
}
REASON_WORDS = {
    "en": {
        "open_ask_current": "asked at {when}, and still true",
        "open_ask_stale":   "asked at {when}; the reading came back on its own, the alert is still open",
        "alert_today":      "a {level} at {when}, over now",
        "over_line":        "over the line, and nobody has been asked to do anything",
        "over_line_peak":   "over the line since the day's high of {peak} at {peak_at}, and nobody has been asked to do anything",
        "no_alert":         "quiet",
        "no_alert_peak":    "quiet; the day's high was {peak} at {peak_at}",
        "context_only":     "it informs, it never asks",
        "ask_how":          "Reply /act {id} on Telegram and say what you did.",
        "not_watched":      "not watched here",
        "no_source":        "no source",
        "event_open":       "an event open since {when} ({kind})",
        "event_answered":   "answered at {when} by {who} ({word}); the node is watching",
        "event_cleared":    "an event cleared at {when}",
        "someone":          "someone",
    },
    "id": {
        "open_ask_current": "diminta pada {when}, dan masih berlaku",
        "open_ask_stale":   "diminta pada {when}; bacaannya sudah kembali sendiri, peringatannya masih terbuka",
        "alert_today":      "{level} pada {when}, sudah lewat",
        "over_line":        "di atas batas, dan belum ada yang diminta melakukan apa pun",
        "over_line_peak":   "di atas batas sejak puncak hari ini {peak} pada {peak_at}, dan belum ada yang diminta melakukan apa pun",
        "no_alert":         "tenang",
        "no_alert_peak":    "tenang; puncak hari ini {peak} pada {peak_at}",
        "context_only":     "memberi tahu, tidak pernah meminta",
        "ask_how":          "Balas /act {id} di Telegram dan sebutkan apa yang Anda lakukan.",
        "not_watched":      "tidak dipantau di sini",
        "no_source":        "tidak ada sumber",
        "event_open":       "kejadian terbuka sejak {when} ({kind})",
        "event_answered":   "dijawab pada {when} oleh {who} ({word}); node sedang mengamati",
        "event_cleared":    "kejadian selesai pada {when}",
        "someone":          "seseorang",
    },
    "es": {
        "open_ask_current": "pedido a las {when}, y sigue vigente",
        "open_ask_stale":   "pedido a las {when}; la lectura volvió sola, la alerta sigue abierta",
        "alert_today":      "un {level} a las {when}, ya pasado",
        "over_line":        "por encima del límite, y no se ha pedido nada a nadie",
        "over_line_peak":   "por encima del límite desde el máximo del día, {peak} a las {peak_at}, y no se ha pedido nada a nadie",
        "no_alert":         "tranquilo",
        "no_alert_peak":    "tranquilo; el máximo del día fue {peak} a las {peak_at}",
        "context_only":     "informa, nunca pide",
        "ask_how":          "Responde /act {id} en Telegram y di qué hiciste.",
        "not_watched":      "no se vigila aquí",
        "no_source":        "sin fuente",
        "event_open":       "un evento abierto desde las {when} ({kind})",
        "event_answered":   "respondido a las {when} por {who} ({word}); el nodo lo vigila",
        "event_cleared":    "un evento terminó a las {when}",
        "someone":          "alguien",
    },
}


def _problems(key: str, d: dict) -> list[str]:
    """Everything wrong with one issue declaration, in the words its author needs to fix it."""
    p: list[str] = []
    if not isinstance(d, dict):
        return [f"{key}: the file is not a mapping"]

    for loc in LOCALES:
        if not (d.get("name") or {}).get(loc):
            p.append(f"{key}: name.{loc} is missing")
        if not (d.get("empty") or {}).get(loc):
            p.append(f"{key}: empty.{loc} is missing — say what there is to say with no source")

    kind = d.get("kind")
    if kind not in KINDS:
        p.append(f"{key}: kind is {kind!r}; it must be one of {KINDS}")
    for f in ("metric", "unit"):
        if not d.get(f):
            p.append(f"{key}: {f} is missing")
    if not isinstance(d.get("dp"), int):
        p.append(f"{key}: dp must be an integer number of decimal places")

    line = d.get("line")
    if line is not None:
        if not isinstance(line, dict):
            p.append(f"{key}: line must be a mapping or empty (~)")
        else:
            for f in ("value", "source"):
                if line.get(f) is None:
                    p.append(f"{key}: line.{f} is missing — a line with no named source is a number "
                             f"somebody will have to go and look up")

    cmp_ = d.get("compare") or {}
    if kind == "sensed":
        if cmp_.get("mode") not in COMPARE_MODES:
            p.append(f"{key}: compare.mode is {cmp_.get('mode')!r}; it must be one of {COMPARE_MODES}. "
                     f"A concentration compares by ratio, a temperature by difference, and the engine "
                     f"must not guess from the unit.")
        if not isinstance(cmp_.get("margin"), (int, float)) or cmp_.get("margin") is True:
            p.append(f"{key}: compare.margin must be a number")

    packs = d.get("packs") or {}
    if not isinstance(packs.get("domains"), list) or not packs["domains"]:
        p.append(f"{key}: packs.domains must list at least one pack domain")
    if not isinstance(packs.get("rules", []), list):
        p.append(f"{key}: packs.rules must be a list of <pack>/<rule> ids")
    for rid in packs.get("rules") or []:
        if "/" not in str(rid):
            p.append(f"{key}: packs.rules has {rid!r}; rule ids are namespaced <pack>/<id>")

    dist = d.get("distances")
    if not isinstance(dist, dict) or set(dist) != set(DISTANCES):
        p.append(f"{key}: distances must have exactly these keys: {', '.join(DISTANCES)} "
                 f"(an absent distance is ~, so the page can say why)")
    else:
        if not any(dist.values()):
            p.append(f"{key}: every distance is empty, so this issue can never have a value")
        for name, spec in dist.items():
            p += _distance_problems(f"{key}.distances.{name}", spec)

    for r in d.get("readouts") or []:
        p += [f"{key}: {x}" for x in _readout_problems(r)]

    if "hero" in d:
        p += _hero_problems(key, d)

    want = set(STATE_SENTENCES) if kind == "context" else {"none"}
    for loc in LOCALES:
        s = (d.get("sentences") or {}).get(loc)
        if not isinstance(s, dict):
            p.append(f"{key}: sentences.{loc} is missing — all three locales carry the same placeholders")
            continue
        attribution = s.get("attribution") or {}
        if kind == "sensed":
            for c in CLASSES:
                if not attribution.get(c):
                    p.append(f"{key}: sentences.{loc}.attribution.{c} is missing")
        state = s.get("state") or {}
        for st in want:
            if not state.get(st):
                p.append(f"{key}: sentences.{loc}.state.{st} is missing")
        uses_verb = False
        for where, tpl in list(attribution.items()) + list(state.items()):
            found = re.findall(r"\{(\w+)\}", str(tpl))
            uses_verb = uses_verb or "verb" in found
            for ph in found:
                if ph not in PLACEHOLDERS:
                    p.append(f"{key}: sentences.{loc}.{where} asks for {{{ph}}}, which the engine "
                             f"does not fill. It fills {', '.join(PLACEHOLDERS)}.")
        # {verb} is the only placeholder whose words are the issue's own, because "Climbing to" is
        # right for a concentration and wrong for a sea temperature. An issue that asks for it says
        # its three words; an issue that does not need not.
        if uses_verb:
            for t in TRENDS:
                if not (s.get("verbs") or {}).get(t):
                    p.append(f"{key}: sentences.{loc} uses {{verb}}, so sentences.{loc}.verbs.{t} "
                             f"is needed")
        for w in (d.get("where") or {}).get(loc, {}):
            if w not in DISTANCES:
                p.append(f"{key}: where.{loc}.{w} is not one of {', '.join(DISTANCES)}")
    return p


_said: set[str] = set()


def _warn_once(msg: str, *args) -> None:
    """load() runs on every /issues request, so a pack's mistake is said once per process, not once per page view."""
    text = msg % args if args else msg
    if text not in _said:
        _said.add(text)
        log.warning(text)


def _readout_problems(r) -> list[str]:
    """One readout: a number from one sensor's latest row, shown with a unit and a label in every locale. The engine
    reads `unit` and `label` without a default, so a readout missing either would take the issue down with it."""
    if not isinstance(r, dict) or not r.get("metric") or not r.get("sensor_id"):
        return ["a readout needs at least a metric and a sensor_id"]
    p = []
    if not isinstance(r.get("unit"), str) or not r["unit"]:
        p.append(f"the {r['metric']} readout needs a unit")
    if "dp" in r and (not isinstance(r["dp"], int) or isinstance(r["dp"], bool)):
        p.append(f"the {r['metric']} readout's dp must be a whole number of decimal places")
    if not all((r.get("label") or {}).get(loc) for loc in LOCALES):
        p.append(f"the {r['metric']} readout needs a label in every locale")
    return p


def pack_readouts(decl: dict[str, dict], manifests: list[dict]) -> dict[str, dict]:
    """Readouts a pack adds to an issue, after the issue's own, in the order of the packs' ids.

    A pack declares them in its pack.yaml as `readouts: {<issue>: [<readout>, ...]}`, in the shape an issue file
    uses. A pack adds and never replaces (docs/decisions/2026-10-01-packs.md): a readout already shown for the same
    sensor and metric is not shown twice, and one that names no declared issue, or is not well formed, is logged and
    left out. Only the readout is dropped, never the issue: one pack's mistake must not cost the household a band.
    A readout whose sensor has no row on this node shows nothing, as an issue's own does, so a pack that is on but
    has not fetched yet adds no invented number.
    """
    for m in sorted(manifests, key=lambda m: str(m.get("id", ""))):
        pid, ro = m.get("id", "?"), m.get("readouts")
        if not ro:
            continue
        if not isinstance(ro, dict):
            _warn_once("pack %s: readouts must map an issue to a list of readouts; ignoring them", pid)
            continue
        for key, rows in ro.items():
            if key not in decl:
                _warn_once("pack %s: readouts for %r, which no app/issues/*.yml declares; ignoring them", pid, key)
                continue
            if not isinstance(rows, list):
                _warn_once("pack %s: readouts.%s must be a list; ignoring it", pid, key)
                continue
            have = {(r.get("metric"), r.get("sensor_id")) for r in decl[key].get("readouts") or [] if isinstance(r, dict)}
            for r in rows:
                bad = _readout_problems(r)
                if bad:
                    _warn_once("pack %s: readouts.%s: %s; leaving it out", pid, key, "; ".join(bad))
                    continue
                if (r["metric"], r["sensor_id"]) in have:
                    _warn_once("pack %s: readouts.%s: %s from %s is already shown; not twice", pid, key,
                                r["metric"], r["sensor_id"])
                    continue
                decl[key].setdefault("readouts", []).append(dict(r))
                have.add((r["metric"], r["sensor_id"]))
    return decl


SECTION_STAGES = ("observe", "decide", "act", "measure")
SECTION_CARDS = ("readout",)


def _section_problems(sec) -> list[str]:
    """One section a pack declares in its pack.yaml, to be drawn by the page's own components."""
    if not isinstance(sec, dict):
        return ["a section must be a mapping"]
    p = []
    sid = sec.get("id")
    if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid):
        p.append("its id must be lowercase letters, digits and hyphens")
    if sec.get("stage") not in SECTION_STAGES:
        p.append(f"its stage is {sec.get('stage')!r}; it must be one of {', '.join(SECTION_STAGES)}")
    if not all((sec.get("title") or {}).get(loc) for loc in LOCALES):
        p.append("it needs a title in every locale")
    card = sec.get("card", "readout")
    if card not in SECTION_CARDS:
        p.append(f"its card is {card!r}. A declared section draws readout cards; a stack, a series or a row needs "
                 f"the shell's own code, which is a reason to promote the pack")
    rows = sec.get("readouts")
    if not isinstance(rows, list) or not rows:
        p.append("it needs at least one readout")
    else:
        for r in rows:
            p += _readout_problems(r)
    if "wall" in sec and not isinstance(sec["wall"], bool):
        p.append("wall must be true or false")
    if "order" in sec and (not isinstance(sec["order"], int) or isinstance(sec["order"], bool)):
        p.append("order must be a whole number")
    note = sec.get("note")
    if note is not None and not (isinstance(note, dict) and all(note.get(loc) for loc in LOCALES)):
        p.append("its note needs every locale, or no note at all")
    return p


def pack_sections(manifests: list[dict]) -> list[dict]:
    """The sections the enabled packs declare (docs/decisions/2026-10-01-packs.md, point 5), in the order of the packs'
    ids, each with the id of the pack that declared it. A wild pack ships no script: it says what its section is, and
    the page draws it with its own readout cards, so it looks like the rest of the page and is measured with it. A
    section that is not well formed, or whose id another pack already took, is left out with a line in the log."""
    out, seen = [], set()
    for m in sorted(manifests, key=lambda m: str(m.get("id", ""))):
        pid, secs = m.get("id", "?"), m.get("sections")
        if not secs:
            continue
        if not isinstance(secs, list):
            _warn_once("pack %s: sections must be a list; ignoring them", pid)
            continue
        for sec in secs:
            bad = _section_problems(sec)
            if bad:
                _warn_once("pack %s: section %s: %s; leaving it out", pid,
                           (sec.get("id") if isinstance(sec, dict) else None) or "?", "; ".join(bad))
                continue
            if sec["id"] in seen:
                _warn_once("pack %s: section %s is already declared by another pack; leaving it out", pid, sec["id"])
                continue
            seen.add(sec["id"])
            out.append({**sec, "pack": pid})
    return out


def _sign_ids() -> set[str]:
    """Every symbol id in the frozen signs.svg. A hero naming anything else draws an empty box."""
    try:
        return set(re.findall(r'<symbol[^>]*\bid="([^"]+)"', (HERE.parent / "static" / "signs.svg").read_text()))
    except OSError:
        return set()


def _hero_problems(key: str, d: dict) -> list[str]:
    """The hero contract: what the page draws when this issue leads, checked against what exists.

    Optional — an issue without one is watched and never leads — but a hero that is present has to
    be drawable: its sign is in signs.svg, its numeral is a distance or readout this issue has, and
    its rule only names distances this issue fills.
    """
    h = d["hero"]
    if not isinstance(h, dict):
        return [f"{key}: hero must be a mapping"]
    p: list[str] = []
    signs = _sign_ids()
    for f in ("sign", "pictogram"):
        if (f == "sign" or h.get(f) is not None) and h.get(f) not in signs:
            p.append(f"{key}: hero.{f} is {h.get(f)!r}, which is not a symbol in app/static/signs.svg")
    have = [x for x in DISTANCES if (d.get("distances") or {}).get(x)]
    readouts = [r.get("metric") for r in d.get("readouts") or [] if isinstance(r, dict)]
    numeral = h.get("numeral", "headline")
    if numeral != "headline" and numeral not in have and numeral not in readouts:
        p.append(f"{key}: hero.numeral is {numeral!r}; it must be a distance this issue fills "
                 f"({', '.join(have)}) or one of its readouts ({', '.join(readouts) or 'none'})")
    if not h.get("unit"):
        p.append(f"{key}: hero.unit is missing")
    if not isinstance(h.get("dp"), int):
        p.append(f"{key}: hero.dp must be an integer number of decimal places")
    if h.get("clock") not in HERO_CLOCKS:
        p.append(f"{key}: hero.clock is {h.get('clock')!r}; it must be one of {HERO_CLOCKS}")
    rule = h.get("rule")
    if rule is not None:
        if not isinstance(rule, dict):
            return p + [f"{key}: hero.rule must be a mapping or absent"]
        lo, hi = rule.get("min"), rule.get("max")
        if not all(isinstance(v, (int, float)) and v is not True for v in (lo, hi)) or lo >= hi:
            p.append(f"{key}: hero.rule needs a numeric min below its max")
        for loc in LOCALES:
            ends = (rule.get("ends") or {}).get(loc)
            if not (isinstance(ends, list) and len(ends) == 2 and all(ends)):
                p.append(f"{key}: hero.rule.ends.{loc} must be two words, the low end and the high end")
        dots = rule.get("dots")
        if not isinstance(dots, list) or not dots:
            p.append(f"{key}: hero.rule.dots must list at least one distance")
        for x in dots or []:
            if x not in have:
                p.append(f"{key}: hero.rule.dots names {x!r}, a distance this issue does not have "
                         f"({', '.join(have)})")
        if not isinstance(rule.get("line"), bool):
            p.append(f"{key}: hero.rule.line must be true or false")
        elif rule["line"] and not d.get("line"):
            p.append(f"{key}: hero.rule.line is true and the issue declares no line to draw")
    return p


def _distance_problems(where: str, spec) -> list[str]:
    if spec is None:
        return []
    if not isinstance(spec, dict):
        return [f"{where} must be a mapping or ~"]
    p = []
    src = spec.get("from")
    if src not in WHERE_FROM:
        p.append(f"{where}.from is {src!r}; it must be one of {WHERE_FROM}")
    if src == "stats":
        if spec.get("place") not in DISTANCES:
            p.append(f"{where}.place is {spec.get('place')!r}; it must be one of {DISTANCES}")
        if not spec.get("field"):
            p.append(f"{where}.field is missing — which of the rolling means to read")
        if spec.get("aggregate") not in AGGREGATES:
            p.append(f"{where}.aggregate is {spec.get('aggregate')!r}; it must be one of {AGGREGATES}")
    if src == "observations" and not spec.get("sensor_id"):
        p.append(f"{where}.sensor_id is missing — which model or portal row to read")
    if src in ("stats", "observations"):
        metrics = spec.get("metrics")
        if not isinstance(metrics, list) or not 1 <= len(metrics) <= 2:
            p.append(f"{where}.metrics must be one metric, or two for a function that takes two")
    fn = spec.get("function")
    if fn is not None and fn not in FUNCTIONS:
        p.append(f"{where}.function is {fn!r}; the engine knows {FUNCTIONS}")
    if fn == "apparent" and len(spec.get("metrics") or []) != 2:
        p.append(f"{where} applies apparent(), which needs exactly two metrics: temperature then humidity")
    # There is no `fallback:`. It existed for one afternoon, pointing at a metric retired in v0.33.1,
    # and the reason it was retired is the reason not to have the mechanism: a second number for one
    # idea, with different provenance, is worse than one number. An issue with no source says so.
    if "fallback" in spec:
        p.append(f"{where} has a fallback. Issues do not fall back to a different measure of the "
                 f"same idea — see the region column in app/issues/land.yml for why. A distance "
                 f"with no source is empty and the page says why.")
    return p


def load(path: Path | str | None = None) -> dict[str, dict]:
    """Every issue declared in `path` (this directory by default), keyed by file stem. With the default, the
    readouts the enabled packs add are merged in (`pack_readouts`).

    A file that does not parse or does not validate is logged and dropped: one bad issue must not
    cost the household the other three.
    """
    out: dict[str, dict] = {}
    for f in sorted(Path(path or HERE).glob("*.yml")):
        try:
            d = yaml.safe_load(f.read_text()) or {}
        except Exception as e:  # noqa: BLE001
            log.warning("issue %s: does not parse (%s)", f.name, e)
            continue
        bad = _problems(f.stem, d)
        if bad:
            for b in bad:
                log.warning("issue %s: %s", f.name, b)
            continue
        d["key"] = f.stem
        out[f.stem] = d
    if path is None:
        # The node's own issues are what the files say plus what its enabled packs add. A validator or a test that
        # names a directory gets the files alone.
        try:
            import packs  # app/packs.py: the one place that knows which packs are on
            out = pack_readouts(out, packs.manifests())
        except Exception as e:  # noqa: BLE001 — the packs are an addition; without them the issues still stand
            log.warning("issues: could not read the packs' readouts (%s)", e)
    return out


def order(declared: str, available: dict[str, dict]) -> tuple[list[str], list[str]]:
    """NODE_ISSUES, parsed. Returns (the order to draw, the names that were dropped).

    An unknown name is dropped and logged, never fatal: a keeper who types `air,heat,watar` gets a
    page with air and heat on it and a line in the log, not a node that will not answer. An empty
    setting falls back to the order the files are in, which is the packs' own alphabetical order.
    """
    names = [n for n in (declared or "").replace(" ", "").split(",") if n]
    keep = [n for n in names if n in available]
    dropped = [n for n in names if n not in available]
    for n in dropped:
        log.warning("NODE_ISSUES names %r, which no app/issues/*.yml declares — dropping it", n)
    seen, uniq = set(), []
    for n in keep:
        if n not in seen:
            seen.add(n); uniq.append(n)
    return (uniq or sorted(available)), dropped


def issues(cur, settings) -> dict:
    """The whole issues object: order, per-issue state, stack, line, attribution, sentence, asks.

    The engine is imported here rather than at module scope so that `engine` can import this module
    for its declarations without the two chasing each other round an import cycle.
    """
    from . import engine
    return engine.compute(cur, settings, load())
