"""Sections a pack declares as data (docs/decisions/2026-10-01-packs.md, point 5).

The node half: issues.pack_sections() refusing what is not well formed, engine._sections() filling a declared section
with the node's own rows and nothing for a row it does not have, and no shipped pack declaring one, so /issues gains
an empty list and nothing else on any node today. The page half: the shell's declared(), lifted out of dashboard.js
and run in node, turning a served section into a section of the page's own shape, drawn with its readout card.
Run: PYTHONPATH=app python3 tests/test_pack_sections.py
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("PACKS_DIR", str(ROOT / "packs"))
os.environ.setdefault("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")

import issues as I          # noqa: E402
from issues import engine   # noqa: E402
import packs                # noqa: E402

L3 = lambda s: {"en": s, "id": s, "es": s}  # noqa: E731
RO = {"metric": "psi", "sensor_id": "nea-psi", "unit": "PSI", "dp": 0, "label": L3("NEA PSI")}
RO2 = {"metric": "wind_speed", "sensor_id": "nea-windspeed", "unit": "kn", "dp": 0, "label": L3("wind")}


def sec(**kw):
    s = {"id": "sg-air", "stage": "observe", "title": L3("Singapore air"), "readouts": [dict(RO), dict(RO2)]}
    s.update(kw)
    return {k: v for k, v in s.items() if v is not None}


def declared(*manifests):
    I._said.clear()
    return I.pack_sections(list(manifests))


# ---------------------------------------------------------------- the node: what a pack may declare
got = declared({"id": "zeta", "sections": [sec(id="z-one")]}, {"id": "alpha", "sections": [sec(id="a-one", wall=True, order=5)]})
assert [(s["id"], s["pack"]) for s in got] == [("a-one", "alpha"), ("z-one", "zeta")], got
print("  sections come in the order of the packs' ids, each with the pack that declared it")

for bad, why in ((sec(stage="look"), "stage"), (sec(title={"en": "x"}), "title in every locale"),
                 (sec(card="series"), "promote the pack"), (sec(readouts=[]), "at least one readout"),
                 (sec(readouts=[{"metric": "psi"}]), "metric and a sensor_id"), (sec(wall="yes"), "true or false"),
                 (sec(order="1"), "whole number"), (sec(note={"en": "x"}), "note needs every locale"),
                 (sec(id="SG_air"), "lowercase")):
    assert declared({"id": "p", "sections": [bad, sec(id="ok-one")]}) == [{**sec(id="ok-one"), "pack": "p"}], why
    assert any(why in m for m in I._said), (why, I._said)
print("  a section that is not well formed is left out alone; a stack, series or row says to promote the pack")

assert [s["pack"] for s in declared({"id": "a", "sections": [sec()]}, {"id": "b", "sections": [sec()]})] == ["a"]
assert declared({"id": "p", "sections": "sg-air"}) == [] and declared({"id": "p"}) == []
print("  an id another pack took is refused, and sections that are not a list are ignored")

# ---------------------------------------------------------------- the engine: the node's own numbers, or none
from datetime import datetime, timezone  # noqa: E402
now = datetime(2026, 10, 2, 7, 0, tzinfo=timezone.utc)
obs = [{"sensor_id": "nea-psi", "metric": "psi", "value": 61.4, "name": "NEA PSI (east region)", "kind": "model",
        "ts": "2026-10-02T06:40:00+00:00"}]
out = engine._sections([{**sec(wall=True, note=L3("why")), "pack": "sg-test"}], obs, now)
assert len(out) == 1 and out[0]["expected"] == 2 and out[0]["wall"] is True and out[0]["note"]["en"] == "why", out
r = out[0]["readouts"]
assert len(r) == 1 and r[0]["value"] == 61 and r[0]["sensor_id"] == "nea-psi" and r[0]["provenance"] == "model", r
assert round(r[0]["age_minutes"]) == 20 and not [k for k in r[0] if k.startswith("_")], r
print("  a declared section carries the rows the node has, with their age, and says how many it expected")
assert engine._sections([{**sec(), "pack": "p"}], [], now)[0]["readouts"] == []
print("  and nothing for a row the node does not have, never an invented number")

assert not [m["id"] for m in packs.manifests() if m.get("sections")], "a shipped pack declares a section"
assert I.pack_sections(packs.manifests()) == []
print("  no shipped pack declares a section, so /issues on every node gains an empty list")

# ---------------------------------------------------------------- the page: declared(), lifted and run
js = (ROOT / "app/static/dashboard.js").read_text()
block = re.search(r"\nconst fromNode = \[\];.*?\nfunction declared\(ctx\) \{.*?\n\}\n", js, re.S)
assert block, "dashboard.js no longer defines declared() beside register()"
for must, what in (("  const ordered = sections.concat(declared(ctx)).filter(", "render() no longer draws declared sections"),
                   ("function wall(ctx) {\n  const ordered = sections.concat(declared(ctx)).sort(", "the wall no longer takes them"),
                   ("const homeless = PAI.sections.concat(PAI.declared(ctx))", "the router no longer homes them on Now"),
                   ("window.PAI.declared = declared;", "the shell no longer exports declared()")):
    assert must in js, what
if shutil.which("node"):
    served = [
        {"id": "sg-air", "pack": "sg-test", "stage": "observe", "title": {"en": "Singapore air", "es": "Aire"},
         "order": 50, "wall": True, "note": {"en": "Why.", "es": "Por qué."}, "expected": 2,
         "readouts": [{"metric": "psi", "value": 61, "dp": 0, "unit": "PSI", "label": {"en": "NEA PSI", "es": "PSI"},
                       "source": "NEA PSI (east region)", "provenance": "model", "sensor_id": "nea-psi", "age_minutes": 20}]},
        {"id": "ground", "pack": "rogue", "stage": "observe", "title": {"en": "x"}, "expected": 1, "readouts": []},
        {"id": "odd", "pack": "rogue", "stage": "nowhere", "title": {"en": "x"}, "expected": 1, "readouts": []},
        {"id": "empty", "pack": "slow", "stage": "measure", "title": {"en": "Nothing yet"}, "expected": 3, "readouts": []},
    ]
    prog = """
const STAGE_INDEX = { observe: 0, decide: 1, act: 2, measure: 3 };
const sections = [{ id: 'ground' }];
const calls = [];
const window = { K: { esc: s => String(s), fmt: (v, dp) => Number(v).toFixed(dp),
  readout: o => { calls.push(o); return `<div data-kind="readout" id="${o.id}">${o.title} ${o.value}</div>`; },
  cmpText: o => ({ none: true, text: 'no comparison yet · ' + o.reason }) } };
""" + block.group(0) + """
const ctx = { LOC: 'es', S: { issues: { sections: %s } } };
const a = declared(ctx), again = declared(ctx);
const s = a.find(x => x.id === 'sg-air'), e = a.find(x => x.id === 'empty');
const body = s.render(), wall = s.wall(), notes = s.notes(), ebody = e.render();
ctx.LOC = 'en'; const en = declared(ctx).find(x => x.id === 'sg-air').title;
console.log(JSON.stringify({ ids: a.map(x => x.id), same: a === again && again.length === 2, title: s.title, en,
  stage: s.stage, reads: s.reads, learn: s.learn, declared: s.declared, wallNull: e.wall,
  body, wall, notes, ebody, call: calls[0], problems: fromNodeProblems }));
""" % json.dumps(served)
    o = json.loads(subprocess.run(["node"], input=prog, capture_output=True, text=True, check=True).stdout)
    assert o["ids"] == ["sg-air", "empty"] and o["same"], o
    print("  served sections become page sections; asking again gives the same sections, never twice as many")
    assert any("ground" in p and "already has" in p for p in o["problems"]) and any("odd" in p for p in o["problems"]), o["problems"]
    print("  an id the page already has, or a stage it does not know, is a registration problem, not a section")
    assert o["title"] == "Aire" and o["en"] == "Singapore air" and o["stage"] == "observe", o
    assert o["reads"] == ["/issues"] and o["learn"] == ["cards", "prov"] and o["declared"] is True, o
    print("  in the reader's language, citing /issues, carrying learn marks like every other section")
    c = o["call"]
    assert c["title"] == "PSI" and c["value"] == 61 and c["num"] == "sg-air.nea-psi.psi" and c["ref"] == "sg-air", c
    assert c["prov"] == "model" and c["age"] == 20 and c["pack"] == "sg-test" and c["source"] == "NEA PSI (east region)", c
    assert "1 of the 2 readings the sg-test pack declares has not arrived" in o["body"], o["body"]
    print("  drawn with the page's own readout card, and a short card says how many readings have not arrived")
    assert 'class="col" id="wall-sg-air-0"' in o["wall"] and 'data-num="sg-air.nea-psi.psi"' in o["wall"] and ">61<" in o["wall"], o["wall"]
    assert o["wallNull"] is None
    print("  a section that asks for the wall gives it one column per reading; one that does not gives none")
    assert o["notes"][0]["text"].startswith("Por qué. Declared by the sg-test pack in its pack.yaml"), o["notes"]
    assert "None of the 3 readings the slow pack declares has arrived" in o["ebody"], o["ebody"]
    print("  its note says which pack declared it and that the pack ships no code; an empty one says nothing has arrived")
print("pack sections: declared as data, filled by the node, drawn by the page's own cards; shipped packs change nothing")
