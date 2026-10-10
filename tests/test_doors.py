"""The five doors (/?layout=doors): what they read, and that they read only what a screen is given.

buildD() and flowFrom() run in node on node #1's capture (app/issues/fixtures/node1-2026-10-06-figures.json); the
prototype in planetai-design drew from a hand-built copy of the same capture, and these were checked against it
value for value on 7 Oct 2026. Here the checks are the ones that must keep holding: the shapes the doors read, the
token-only parts left empty without the token, and every file the page names served by its NAME.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "app"))
os.environ.setdefault("DATABASE_URL", "postgresql://test@127.0.0.1:1/test")
STATIC = ROOT / "app" / "static"
FIX = "app/issues/fixtures/node1-2026-10-06-figures.json"

# Every file doors.html names is one the node serves by name (the /static/{name} rule: a name, never a path).
import main  # noqa: E402

html = (STATIC / "doors.html").read_text()
named = re.findall(r'(?:src|href)="/static/([^"]+)"', html)
assert named and all(n in main.COMPANIONS for n in named), [n for n in named if n not in main.COMPANIONS]
for f in STATIC.glob("doors-*.js"):
    assert f.name in main.COMPANIONS, f"{f.name} is shipped but the node does not serve it"
    assert f.name in named, f"{f.name} is served but doors.html never loads it"
js = "".join(f.read_text() for f in STATIC.glob("doors-*.js"))
for asset in re.findall(r"'/static/([\w.-]+)'", js):
    assert asset in main.COMPANIONS, f"a door asks for /static/{asset}, which the node does not serve"
assert "/node/" not in js and "data.json" not in js and "flow.json" not in js, "a door still reads the prototype's capture or proxy"
assert "h3-js" not in html and not re.search(r"\bh3\.\w+\(", js), "the node computes the cells; the page draws them"
print("doors: every file the page names is served by name, and no door reads the prototype's capture")

# / and /?layout=doors serve the doors through the same shell route; ?layout=classic serves the classic dashboard.
from fastapi.testclient import TestClient  # noqa: E402
c = TestClient(main.app)
assert c.get("/").text == html
assert c.get("/", params={"layout": "doors"}).text == html
assert c.get("/", params={"layout": "classic"}).text == (STATIC / "index.html").read_text()
print("doors: / and ?layout=doors is the doors, ?layout=classic the classic dashboard")

if not shutil.which("node"):
    print("doors: node is not installed, skipping the loader checks (skipped)")
    sys.exit(0)

prog = """
const fs = require('fs');
const { buildD } = require('./app/static/doors-load.js');
const src = fs.readFileSync('./app/static/doors-flow.js', 'utf8');
const flowFrom = new Function(src.match(/function flowFrom[\\s\\S]*?\\n}\\n/)[0] + '; return flowFrom;')();
const F = JSON.parse(fs.readFileSync('%s', 'utf8'));
const open = { ...F, days: F.issues_days }; delete open.readings_1h; delete open.actions; delete open.alerts;
const full = buildD({ ...F, days: F.issues_days }, 'en'), locked = buildD(open, 'en');
const fl = flowFrom(full), fo = flowFrom(locked);
/* node #1's live table carries forecast rows up to 48 h ahead (7 Oct): the doors' table must stop at the present */
const ahead = buildD({ ...F, days: F.issues_days, readings_1h: F.readings_1h.concat([{ bucket: '2099-01-01T00:00:00+08:00', sensor_id: 'forecast-om', metric: 'fc_cloud', mean: 1, min: 1, max: 1, n: 1 }]) }, 'en');
console.log(JSON.stringify({
  aheadLast: ahead.raw.buckets[ahead.raw.buckets.length - 1], fullLast: full.raw.buckets[full.raw.buckets.length - 1], aheadN: ahead.raw.n.length, fullN: full.raw.n.length,
  order: full.order, lead: full.lead, n: full.buckets.length, issues: Object.keys(full.issues),
  air: full.issues.air, ev: full.events, raw: full.raw && { b: full.raw.buckets.length, ids: Object.keys(full.raw.series).length },
  lockedRaw: locked.raw, lockedNotes: locked.notes, fullNotes: full.notes, lockedActions: locked.actions.length,
  lockedNote: locked.actions.some(a => 'note' in a), stats: Object.keys(full.stats15).length, point: full.point,
  flow: { b: fl.buckets.length, ids: Object.keys(fl.counts).length, alerts: fl.alerts.length, answers: fl.answers.length, counted: fl.counted },
  flowLocked: { b: fo.buckets.length, ids: Object.keys(fo.counts).length, alerts: fo.alerts.length, answers: fo.answers.length, counted: fo.counted },
}));
""" % FIX
r = json.loads(subprocess.run(["node"], input=prog, capture_output=True, text=True, check=True).stdout)

# the issues, as the doors read them (/issues for the words, /issues/days for the seven days)
assert r["order"] == ["air", "heat", "land", "coast"] and r["lead"] == "heat" and r["n"] == 168, r["order"]
air = r["air"]
assert air["name"] == "Air" and air["line"] == 15 and air["unit"] == "µg/m³" and air["hero_distance"] == "room"
assert air["sentence"].startswith("Climbing to 8") and air["pix"] == "pix-air" and len(air["usual"]) == 24
assert len(air["series"]["room"]) == 168 and air["series"]["region"] is None and len(air["per_day"]) == 8
assert set(air["stack"]["room"]) == {"value", "provenance", "source"}, "the stack keeps three words, not the node's whole row"
# an event carries its own answer, its action's words and its rooms
assert [e["id"] for e in r["ev"]] == [1, 2, 3]
assert r["ev"][2]["answer"]["stage"] == "acted" and r["ev"][0]["answer"] is None and len(r["ev"][0]["rooms"]) == 3
assert r["ev"][0]["action"].startswith("Open the side where it started")
print("doors: the issues and the events are the node's own words, renamed and never recomputed")

# token-only parts: the hourly table and the household's notes stay on the node for a screen without the token
assert r["raw"] == {"b": 24, "ids": 21} and r["lockedRaw"] is None
assert r["fullNotes"] is True and r["lockedNotes"] is False and r["lockedActions"] > 0 and not r["lockedNote"], \
    "without the token the ledger comes from /issues' asks: stages and actors, never the notes"
assert r["stats"] == 18 and r["point"] == [115.164, -8.819], "the point is /health's, rounded as it gives it"
print("doors: without the token the hourly table is absent and the ledger carries no notes")

# the flow: counts from the hourly table, alerts and answers in its window (matched flow.json exactly on 7 Oct)
assert r["flow"] == {"b": 24, "ids": 21, "alerts": 30, "answers": 7, "counted": True}, r["flow"]
assert r["flowLocked"]["counted"] is False and r["flowLocked"]["ids"] == 0 and r["flowLocked"]["b"] == 24
print("doors: the flow counts what the hourly table counted, and says it did not count without it")
assert r["aheadLast"] == r["fullLast"] and r["aheadN"] == r["fullN"], "a forecast hour ahead of /issues entered the replayed table"
print("doors: the hourly table stops at the hour /issues was computed; forecast rows ahead of it stay out")
print("all doors checks passed")
