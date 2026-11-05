"""A pack's buttons on the doors' Now, under What to do (#asks).

A rule may send its alert with buttons (app/buttons.py); the bot draws them as a keyboard and Now draws them as the
same answers, POST /actions {alert_id, choice, actor, note}. asksFrom(alerts, actions, now) decides what is still
asked: an alert of the last 72 hours with buttons and a row nobody answered yet. A row is answered once anybody
pressed one of its buttons; an acknowledged button answers the whole alert. drawAsks() draws it in the page's
locale. Both are lifted out of doors-now.js and run in node, as tests/test_doors_sections.py does.
Run: python3 tests/test_doors_asks.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NOW = "2026-11-03T09:00:00+08:00"
B = lambda en, v, stage="acted", ask=None, es=None: {"text": {"en": en, **({"es": es} if es else {})}, "value": v, "stage": stage, "ask": ask}  # noqa: E731
ALERTS = [
    {"id": 1, "ts": "2026-11-03T08:00:00+08:00", "rule_id": "surf/evening", "text": "\n".join(f"line {i}" for i in range(1, 9)),
     "buttons": [[B("Going", "going", es="Voy"), B("Not today", "skip")], [B("Tell me why", "why", ask={"en": "What would make it better?"})]]},
    {"id": 2, "ts": "2026-10-31T07:59:00+08:00", "rule_id": "surf/evening", "text": "73 hours old", "buttons": [[B("Going", "going")]]},
    {"id": 3, "ts": "2026-11-03T07:00:00+08:00", "rule_id": "surf/evening", "text": "snoozed", "buttons": [[B("Going", "going")], [B("Later", "later", "acknowledged")]]},
    {"id": 4, "ts": "2026-11-03T07:00:00+08:00", "rule_id": "air-quality/x", "text": "no buttons", "buttons": None},
    {"id": 5, "ts": "2026-11-03T06:00:00+08:00", "rule_id": "surf/evening", "text": "all rows taken", "buttons": [[B("Going", "going")]]},
]
ACTIONS = [
    {"ts": "2026-11-03T08:05:00+08:00", "alert_id": 1, "stage": "acted", "actor": "wayan", "note": "big swell", "choice": "skip"},
    {"ts": "2026-11-03T07:10:00+08:00", "alert_id": 3, "stage": "acknowledged", "actor": "tomas", "note": None, "choice": "later"},
    {"ts": "2026-11-03T06:10:00+08:00", "alert_id": 5, "stage": "acted", "actor": "", "note": None, "choice": "going"},
    {"ts": "2026-11-03T08:06:00+08:00", "alert_id": 1, "stage": "acted", "actor": "made", "note": None, "choice": None},
]

prog = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), now = fs.readFileSync('./app/static/doors-now.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0], fn = (src, n) => src.match(new RegExp('function ' + n + '\\b[\\s\\S]*?\\n}\\n'))[0];
const [alerts, actions, at] = JSON.parse(process.argv[1]), out = {};
for (const locale of ['en', 'es', 'id']) {
  const els = {}, ctx = { D: { tz: 'Asia/Makassar', locale, alerts, actions }, doorsLocal: L.doorsLocal, Date: Object.assign(class extends Date {}, { now: () => Date.parse(at) }),
    $: q => (els[q] ||= { hidden: true, innerHTML: '', querySelector: () => null }) };
  vm.createContext(ctx);
  vm.runInContext(['esc', 'WD', 'loc', 'dayOf', 'dLabel', 'wdhm', 'said'].map(pick).join('\n') + '\n'
    + fn(now, 'asksFrom') + fn(now, 'packWord') + fn(now, 'drawAsks') + 'var got = asksFrom(D.alerts, D.actions, Date.now()); drawAsks();', ctx);
  out[locale] = { got: ctx.got, html: els['#asks'].innerHTML, hidden: els['#asks'].hidden };
}
const empty = { innerHTML: '', hidden: true, querySelector: () => null }, c2 = { D: { tz: 'Asia/Makassar', locale: 'en', alerts: [], actions: [] }, doorsLocal: L.doorsLocal, Date, $: () => empty };
vm.createContext(c2);
vm.runInContext(['esc', 'WD', 'loc', 'dayOf', 'dLabel', 'wdhm', 'said'].map(pick).join('\n') + '\n' + fn(now, 'asksFrom') + fn(now, 'packWord') + fn(now, 'drawAsks') + 'drawAsks();', c2);
out.none = empty;
console.log(JSON.stringify(out));
"""
r = subprocess.run(["node", "-e", prog, json.dumps([ALERTS, ACTIONS, NOW])], capture_output=True, text=True, cwd=ROOT)
assert r.returncode == 0, r.stderr[-2000:]
out = json.loads(r.stdout)
got = out["en"]["got"]

assert [g["alert"]["id"] for g in got] == [1], [g["alert"]["id"] for g in got]
print("  an alert of 73 h, one whose acknowledged button was pressed, one with every row taken and one with no buttons are gone")

rows = got[0]["rows"]
assert [[b["value"] for b in row] for row in rows] == [["why"]], rows
assert [(a["choice"], a["actor"]) for a in got[0]["answers"]] == [("skip", "wayan")], got[0]["answers"]
print("  an alert with one row answered keeps its other rows; the answer is anyone's, and an answer with no choice is not one")

h = out["en"]["html"]
assert not out["en"]["hidden"] and h.count('<button') == 1 and 'data-al="1" data-v="why" data-ask="What would make it better?"' in h, h
assert "line 6" in h and "line 7" not in h and "…" in h, h
assert "answered: Not today by wayan at 08:05 · “big swell”" in h, h
assert "surf" in h and "Tue 08:00" in h, h
print("  Now draws the text's first six lines, the rows left as buttons, a button's question with it, and each answer")

es_alert = [dict(ALERTS[0], buttons=[[B("Going", "going", es="Voy")]])]
r2 = subprocess.run(["node", "-e", prog, json.dumps([es_alert, [], NOW])], capture_output=True, text=True, cwd=ROOT)
assert r2.returncode == 0, r2.stderr[-2000:]
o2 = json.loads(r2.stdout)
assert ">Voy</span></button>" in o2["es"]["html"] and ">Going</span></button>" in o2["id"]["html"] and ">Going</span></button>" in o2["en"]["html"], o2
print("  a button says the page's locale, else English: never a dict")

assert {k: out["none"][k] for k in ("innerHTML", "hidden")} == {"innerHTML": "", "hidden": True}, out["none"]
print("  nothing asked (or no token, so no /alerts): #asks stays hidden and empty")

html = (ROOT / "app/static/doors.html").read_text()
nowh = html[html.index('<main class="face view" data-view="now">'):html.index("<!-- PLACE -->")]
assert nowh.index('id="decide"') < nowh.index('id="asks"') < nowh.index('id="ndecl-decide"'), "#asks is not under What to do"
src = (ROOT / "app/static/doors-now.js").read_text()
assert "drawAsks();" in src.split("VIEWS.now = function")[1].split("};")[0]
prog2 = r"""
const fs = require('fs'), vm = require('vm'), now = fs.readFileSync('./app/static/doors-now.js', 'utf8');
const fn = (src, n) => src.match(new RegExp('(?:async )?function ' + n + '\\b[\\s\\S]*?\\n}\\n'))[0], sent = [], said = [];
const answers = [[200, { ok: true }], [200, { ok: true, kept: true }], [409, { detail: 'this question has closed' }], [403, {}]];
const ctx = { sent, said, WORDS: { locked: 'LOCKED', noreply: 'NOREPLY' }, DOORS_AUTH: () => ({ authorization: 'Bearer t' }),
  localStorage: { getItem: k => k === 'planetai_actor' ? 'ibu' : null },
  fetch: async (u, o) => { sent.push([u, o.method, o.headers, JSON.parse(o.body)]); const [st, j] = answers.shift(); return { ok: st === 200, status: st, json: async () => j }; } };
vm.createContext(ctx);
vm.runInContext(fn(now, 'actorHere') + fn(now, 'askAnswer') + `(async () => { for (const n of ['', 'too big', '', '']) said.push(await askAnswer('1', 'why', n)); })()`, ctx);
setTimeout(() => console.log(JSON.stringify({ sent, said })), 50);
"""
r3 = subprocess.run(["node", "-e", prog2], capture_output=True, text=True, cwd=ROOT)
assert r3.returncode == 0, r3.stderr[-2000:]
o3 = json.loads(r3.stdout)
assert o3["sent"][0] == ["/actions", "POST", {"content-type": "application/json", "authorization": "Bearer t"},
                         {"alert_id": 1, "choice": "why", "actor": "ibu", "note": ""}], o3["sent"][0]
assert o3["sent"][1][3]["note"] == "too big" and o3["said"] == ["", "", "this question has closed", "LOCKED"], o3
print("  #asks sits under What to do, Now draws it on every visit, and a press is the bot's POST /actions, with the token, the actor and then the note")
print("  a kept answer is taken; a 409 says the node's own words, a 403 says the screen is locked")

# Fix round 1: any redraw of Now (a resize: a phone's keyboard opening, a rotation) ran drawAsks() over the note form,
# and drew the row just answered again, because D.actions was the load before the press.
prog3 = r"""
const fs = require('fs'), vm = require('vm');
const L = require('./app/static/doors-load.js');
const core = fs.readFileSync('./app/static/doors-core.js', 'utf8'), now = fs.readFileSync('./app/static/doors-now.js', 'utf8');
const pick = n => core.match(new RegExp('^const ' + n + ' = .*$', 'm'))[0], fn = (src, n) => src.match(new RegExp('function ' + n + '\\b[\\s\\S]*?\\n}\\n'))[0];
const [alerts] = JSON.parse(process.argv[1]), out = [];
const typing = { id: 'input' }, form = { note: { value: '' }, contains: e => e === typing };
const el = { hidden: true, innerHTML: '', open: false, querySelector: q => q === 'form' && el.open ? form : null };
const ctx = { D: { tz: 'Asia/Makassar', locale: 'en', alerts, actions: [] }, doorsLocal: L.doorsLocal, $: () => el, document: { activeElement: null } };
vm.createContext(ctx);
vm.runInContext(['esc', 'WD', 'loc', 'dayOf', 'dLabel', 'wdhm', 'said'].map(pick).join('\n') + '\n'
  + fn(now, 'asksFrom') + fn(now, 'packWord') + fn(now, 'drawAsks') + fn(now, 'askTaken'), ctx);
const snap = () => out.push({ html: el.innerHTML, hidden: el.hidden, n: ctx.D.actions.length });
vm.runInContext('drawAsks()', ctx); snap();                                             // 0: the alert, both rows
vm.runInContext("askTaken('1', 'why', 'ibu')", ctx);                                    // the press was taken
el.open = true; ctx.document.activeElement = typing; el.innerHTML = 'FORM';
vm.runInContext('drawAsks()', ctx); snap();                                             // 1: focused: kept
ctx.document.activeElement = null; form.note.value = 'smaller';
vm.runInContext('drawAsks()', ctx); snap();                                             // 2: words typed: kept
form.note.value = ''; vm.runInContext('drawAsks()', ctx); snap();                       // 3: neither: drawn again, without the row
out.push(ctx.D.actions[0]);
console.log(JSON.stringify(out));
"""
two = [dict(ALERTS[0], buttons=[[B("Going", "going")], [B("Tell me why", "why", ask={"en": "What would make it better?"})]])]
r4 = subprocess.run(["node", "-e", prog3, json.dumps([two])], capture_output=True, text=True, cwd=ROOT)
assert r4.returncode == 0, r4.stderr[-2000:]
o4 = json.loads(r4.stdout)
assert 'data-v="why"' in o4[0]["html"] and 'data-v="going"' in o4[0]["html"], o4[0]
assert o4[1]["html"] == "FORM" and o4[2]["html"] == "FORM", (o4[1], o4[2])
print("  a redraw while the note form has focus or words keeps the form as it is")
assert 'data-v="why"' not in o4[3]["html"] and 'data-v="going"' in o4[3]["html"] and "answered: Tell me why by ibu at" in o4[3]["html"], o4[3]
a = o4[4]
assert (a["alert_id"], a["choice"], a["actor"], a["stage"]) == (1, "why", "ibu", "acted") and a["ts"], a
print("  a press is recorded on the page at once, so any redraw before the next load draws its row as answered")
src_now = (ROOT / "app/static/doors-now.js").read_text()
assert "addEventListener('hashchange'" in src_now and "view() !== 'now'" in src_now, "leaving Now does not drop the note form"
print("doors asks: a pack's buttons draw under What to do, answered with the bot's own POST /actions")
sys.exit(0)
