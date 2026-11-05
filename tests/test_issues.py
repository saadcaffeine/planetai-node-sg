"""The issue declarations: they validate, they cover every shipped pack, and a fifth one is one file.

  · the four shipped app/issues/*.yml validate, in all three locales
  · every enabled pack's domain reaches an issue, or is named here as deliberately not one
  · every alert rule a cross-domain pack ships is claimed by an issue, or named here
  · the line each issue names is the same number as the pack rule it points at
  · a synthetic tap-water issue loads and appears, with no code change anywhere
  · NODE_ISSUES parsing: unknown names dropped, empty falls back, duplicates collapse

Run: PACKS_DIR=packs PYTHONPATH=app python3 tests/test_issues.py
"""
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
os.environ.setdefault("PACKS_DIR", "packs")
sys.path.insert(0, str(ROOT / "app"))

import issues as I  # noqa: E402
import packs        # noqa: E402

# order() logs every dropped name, which is the point of it — but this test drops names on purpose
# seven times and the reasons belong in the assertions, not above them.
logging.getLogger("planetai.issues").setLevel(logging.ERROR)

fails = []
DECL = I.load()

# --- the five shipped files validate -------------------------------------------------------------
# Since 23 Oct 2026 an issue ships in the pack that watches it (packs/<id>/issue.yml), read while that pack is on.
OWNER = {"air": "air-quality", "heat": "heat", "land": "earth", "coast": "coast", "water": "terrain"}
for want, pk in OWNER.items():
    if want not in DECL:
        raw = yaml.safe_load((ROOT / f"packs/{pk}/issue.yml").read_text()) or {}
        fails += [f"packs/{pk}/issue.yml: {b}" for b in I._problems(want, raw)] or \
                 [f"packs/{pk}/issue.yml does not load"]
shipped = {yaml.safe_load(p.read_text()).get("key") for p in (ROOT / "packs").glob("*/issue.yml")}
for extra in shipped - set(DECL):
    fails.append(f"an issue.yml declares {extra!r}, which did not validate")
assert not list((ROOT / "app/issues").glob("*.yml")), "the core ships no issue of its own; each is its pack's"
assert all(yaml.safe_load((ROOT / f"packs/{pk}/issue.yml").read_text())["key"] == k for k, pk in OWNER.items())

# update.sh step 5d: a node that lists its packs keeps the issues it draws, by gaining the pack that ships each one.
import os as _os, subprocess as _sp, tempfile as _tf
_u = open(ROOT / "update.sh").read()
_step = _u[_u.index("# 5d."):_u.index("# 5e.")]
_STUB = r"""
pq() {   # the settings table, as a key=value file
  if [[ "$1" == SELECT* ]]; then k="$(sed -E "s/.*key = '([A-Z_]+)'.*/\1/" <<< "$1")"; sed -n "s/^${k}=//p" "$DB"
  else add="$(sed -E "s/.*\|\| ',([a-z-]+)'.*/\1/" <<< "$1")"; sed -i.bak -E "s/^(PACKS_ENABLED=.+)$/\1,${add}/" "$DB"; rm -f "$DB.bak"; fi
}
"""
def _5d(db, env):
    with _tf.TemporaryDirectory() as t:
        open(f"{t}/db", "w").write(db); open(f"{t}/.env", "w").write(env)
        _sp.run(["bash", "-c", "set -euo pipefail\n" + _STUB + _step], cwd=t, env={**_os.environ, "DB": f"{t}/db"},
                capture_output=True, text=True, check=True)
        return open(f"{t}/db").read(), open(f"{t}/.env").read()
_db, _ = _5d("NODE_ISSUES=air,heat\nPACKS_ENABLED=smartcitizen,heat\n", "")
assert _db.endswith("PACKS_ENABLED=smartcitizen,heat,air-quality\n"), _db
assert _5d(_db, "")[0] == _db, "a second update changed the list again"
_, _env = _5d("", "NODE_ISSUES=\nPACKS_ENABLED=heat\n")
assert "PACKS_ENABLED=heat,air-quality,coast,earth,terrain" in _env, "NODE_ISSUES empty draws every issue: every owner"
# Every shipped issue's pack is in 5d's list: on 23 Oct 2026 `water` shipped without it, so naming water in a node's
# NODE_ISSUES drew nothing on a node that lists its packs (node #1 does).
_pairs = set(_step.split("for owned in ", 1)[1].split(";", 1)[0].split())
assert _pairs == {f"{k}:{pk}" for k, pk in OWNER.items()}, _pairs
assert _5d("NODE_ISSUES=air\n", "PACKS_ENABLED=\n") == ("NODE_ISSUES=air\n", "PACKS_ENABLED=\n"), "an empty list is every pack"
print("  update.sh 5d: a node that lists its packs gains the pack of each issue it draws, once")

# The validator has to actually refuse things, or "it validates" means nothing. Ten ways in.
BREAKS = {
    "no kind": lambda d: d.pop("kind"),
    "no compare mode": lambda d: d["compare"].pop("mode"),
    "verb with no verbs": lambda d: d["sentences"]["en"].pop("verbs"),
    "a where for a fifth distance": lambda d: d.__setitem__("where", {"en": {"street": "x"}}),
    "a fifth distance": lambda d: d["distances"].__setitem__("street", None),
    "an unfillable placeholder": lambda d: d["sentences"]["en"]["attribution"].__setitem__("clear", "{room} µg"),
    "a line with no source": lambda d: d["line"].pop("source"),
    "a rule id with no pack": lambda d: d["packs"]["rules"].append("digest"),
    "one locale missing": lambda d: d["sentences"].pop("id"),
    "apparent on one metric": lambda d: d["distances"]["room"].__setitem__("metrics", ["temp"]),
}
for name, break_it in BREAKS.items():
    d = yaml.safe_load((ROOT / "packs/air-quality/issue.yml").read_text())
    if name == "apparent on one metric":
        d["distances"]["room"]["function"] = "apparent"
    try:
        break_it(d)
    except Exception:                                   # a break that no longer applies to this file
        fails.append(f"the validator's own test case {name!r} could not be set up")
        continue
    if not I._problems("air", d):
        fails.append(f"the validator accepts a declaration with {name}")

# --- the hero contract refuses what the page could not draw -------------------------------------
# Coast, because it is the issue with distances missing: a rule dot or a numeral naming the room is
# a hero the page would have to invent a number for.
HERO_BREAKS = {
    "a sign that is not in signs.svg": lambda d: d["hero"].__setitem__("sign", "sign-surf"),
    "a pictogram that is not in signs.svg": lambda d: d["hero"].__setitem__("pictogram", "pix-surf"),
    "a rule dot at a distance it lacks": lambda d: d["hero"]["rule"]["dots"].append("room"),
    "a numeral that is neither a distance nor a readout": lambda d: d["hero"].__setitem__("numeral", "tide"),
    "a numeral at a distance it lacks": lambda d: d["hero"].__setitem__("numeral", "yard"),
    "a line on the rule with no line declared": lambda d: d["hero"]["rule"].__setitem__("line", True),
    "a clock that is neither": lambda d: d["hero"].__setitem__("clock", "tide"),
    "one end word": lambda d: d["hero"]["rule"]["ends"].__setitem__("es", ["en calma"]),
}
for name, break_it in HERO_BREAKS.items():
    d = yaml.safe_load((ROOT / "packs/coast/issue.yml").read_text())
    break_it(d)
    if not I._problems("coast", d):
        fails.append(f"the validator accepts a hero with {name}")
_ok = yaml.safe_load((ROOT / "packs/coast/issue.yml").read_text())
_ok["hero"]["numeral"] = "swell_height_m"
if I._problems("coast", _ok):
    fails.append("the validator refuses a hero whose numeral is one of the issue's own readouts")
_ok.pop("hero")
if I._problems("coast", _ok):
    fails.append("the validator refuses an issue with no hero; it is optional, and such an issue never leads")

# --- every pack reaches an issue, or is named as not one ------------------------------------------
# A pack domain that is deliberately outside the environmental picture. Weather feeds air and heat
# (wind for attribution, the forecast for the day ahead) but is not itself something a place is
# better or worse at; place is the ground everything sits on; governance is the loop and the Index;
# repair is a catalogue somebody maintains, not a quality of the air, water or land here.
NOT_ISSUES = {"weather", "place", "governance", "repair"}
# Alert rules from cross-domain packs, or from packs with no domain at all, that belong to no issue.
# trust is the node's own instruments: whether they are frozen, missing hours, or disagreeing.
UNMAPPED_RULES = {
    "trust/channel_dead", "trust/coverage_low", "trust/peer_disagreement",
}
claimed_domains = {dom for d in DECL.values() for dom in d["packs"]["domains"]}
claimed_rules = {r for d in DECL.values() for r in (d["packs"]["rules"] or [])}

manifests = {m["id"]: m for m in packs.manifests()}
if not manifests:
    fails.append("no packs loaded — run with PACKS_DIR=packs from the repo root")
for pid, m in manifests.items():
    dom = m.get("domain")
    if dom in claimed_domains or dom in NOT_ISSUES:
        continue
    # cross-domain, or a pack with no domain: every alert it ships must be claimed rule by rule
    for r in packs.alerts():
        if not r["id"].startswith(pid + "/"):
            continue
        if r["id"] not in claimed_rules and r["id"] not in UNMAPPED_RULES:
            fails.append(f"{r['id']} belongs to no issue. Add it to an issue's packs.rules, or to "
                         f"UNMAPPED_RULES in this test with the reason it is not an issue.")
for r in sorted(claimed_rules):
    if r not in {a["id"] for a in packs.alerts()}:
        fails.append(f"an issue claims {r}, which no enabled pack ships")
for dom in sorted(claimed_domains):
    if dom not in {m.get("domain") for m in manifests.values()}:
        fails.append(f"an issue claims the pack domain {dom!r}, which no enabled pack declares")

# --- the line is the pack's own number -----------------------------------------------------------
# No pack declares a threshold as data (`thresholds:` is prose in both pack.yaml files that have
# one), so each issue writes its line down and names the rule whose SQL carries the same number.
# This is the gate that keeps the two from drifting; it is why retyping the number is safe.
for key, d in DECL.items():
    line = d.get("line")
    if not line:
        continue
    ref = line.get("sql")
    if not ref:
        fails.append(f"{key}: line has no sql: pointer, so nothing holds it to the pack's own rule")
        continue
    pack, _, rule = ref.partition("/")
    hit = next((r for r in packs.rules() if r["id"] == ref), None)
    if not hit:
        fails.append(f"{key}: line.sql names {ref}, which is not a rule any enabled pack ships")
        continue
    n = line["value"]
    body = str(hit.get("sql", ""))
    if not re.search(rf"(?<![\d.]){re.escape(str(n))}(?![\d])", body):
        fails.append(f"{key}: the line is {n} but {ref}'s SQL does not contain that number. One of "
                     f"the two moved; they must say the same thing.")

# --- a fifth issue is a fifth file ---------------------------------------------------------------
# Tap water, not `water`: since 23 Oct 2026 the terrain pack ships a real `water` issue (where rain runs), so the
# synthetic one needs a key of its own.
WATER = {
    "name": {"en": "Tap water", "id": "Air bersih", "es": "Agua del grifo"},
    "kind": "sensed", "metric": "turbidity", "unit": "NTU", "dp": 1,
    "compare": {"mode": "ratio", "margin": 1.5},
    "line": {"value": 5, "unit": "NTU", "source": "WHO drinking-water guideline", "sql": None},
    "packs": {"domains": ["tapwater"], "rules": []},
    "distances": {
        "room": {"from": "stats", "place": "room", "metrics": ["turbidity"], "field": "mean_15m",
                 "aggregate": "mean"},
        "yard": None, "ring": None,
        "region": None,
    },
    "sentences": {loc: {"attribution": {c: "{n} {unit} {where}. {cmp}" for c in I.CLASSES},
                        "state": {"none": "No water sensor here yet."}} for loc in I.LOCALES},
    "empty": {loc: "No water sensor here yet." for loc in I.LOCALES},
}
with tempfile.TemporaryDirectory() as tmp:
    for k, pk in OWNER.items():                       # the five shipped issues, as files in one directory
        shutil.copy(ROOT / f"packs/{pk}/issue.yml", Path(tmp) / f"{k}.yml")
    (Path(tmp) / "tapwater.yml").write_text(yaml.safe_dump(WATER, allow_unicode=True))
    five = I.load(tmp)
    if "tapwater" not in five:
        fails.append("a synthetic tapwater.yml did not load — adding an issue is not one file after all")
    elif five["tapwater"]["name"]["en"] != "Tap water":
        fails.append("tapwater.yml loaded but its name did not survive")
    if len(five) != len(DECL) + 1:
        fails.append(f"loading six files gave {len(five)} issues")
    got, dropped = I.order("air,tapwater,heat", five)
    if got != ["air", "tapwater", "heat"]:
        fails.append(f"NODE_ISSUES=air,tapwater,heat gave {got} — a new issue must be orderable at once")
    if dropped:
        fails.append(f"nothing should have been dropped, but {dropped} was")

# --- NODE_ISSUES parsing -------------------------------------------------------------------------
for declared, want_order, want_dropped in [
    ("air,heat,land,coast", ["air", "heat", "land", "coast"], []),
    ("heat,air", ["heat", "air"], []),
    (" heat , air ", ["heat", "air"], []),                       # a keeper's spaces
    ("air,watar,heat", ["air", "heat"], ["watar"]),              # a typo is dropped, never fatal
    ("air,air,heat", ["air", "heat"], []),                       # said twice, drawn once
    ("", sorted(DECL), []),                                       # empty falls back to the files' order
    ("watar", sorted(DECL), ["watar"]),                           # every name unknown: still a page
]:
    got, dropped = I.order(declared, DECL)
    if got != want_order:
        fails.append(f"NODE_ISSUES={declared!r} ordered {got}, expected {want_order}")
    if dropped != want_dropped:
        fails.append(f"NODE_ISSUES={declared!r} dropped {dropped}, expected {want_dropped}")

# --- the four distances have ONE vocabulary ---------------------------------------------------------------------
#
# A column headed YARD above a sentence reading "on the wall outside" is two names for one place on
# one screen, and English was the only language that had them: Decision 6 gave it the system's own
# words and gave the household's to the other two. Half of that is reversed — the headings are the
# sentence's nouns now, in all three — and this is what keeps them from drifting apart again.
#
# The API keys are deliberately NOT part of it. `room/yard/ring/region` are what /issues.distances
# publishes, what every stack is keyed on and what a pack's `where:` block overrides. Renaming them
# would be a wire break to fix a wording problem.
for _loc in I.LOCALES:
    if set(I.LABEL_WORDS.get(_loc, {})) != set(I.DISTANCES):
        fails.append(f"LABEL_WORDS[{_loc}] does not carry exactly the four distances")
        continue
    for _d in I.DISTANCES:
        _label, _noun = I.LABEL_WORDS[_loc][_d], I.NOUN_WORDS[_loc][_d]
        if not _label.strip():
            fails.append(f"LABEL_WORDS[{_loc}][{_d}] is blank")
        # The heading must be the noun the sentence uses, allowing the article the sentence needs
        # and the heading does not: "the street" -> "street", "la calle" -> "calle".
        if _label.lower() not in _noun.lower():
            fails.append(f"LABEL_WORDS[{_loc}][{_d}] is {_label!r} but the sentence says {_noun!r} — "
                         f"one place, two names, on one screen")
if set(I.DISTANCES) != {"room", "yard", "ring", "region"}:
    fails.append(f"the API keys changed to {I.DISTANCES}: that is a wire break, not a wording change")

print("\n".join(f"  x {f}" for f in fails) or
      f"  issues: {len(DECL)} declarations validate in {len(I.LOCALES)} locales; "
      f"{len(manifests)} packs all reach an issue or are named as not one; every line matches its "
      f"pack's SQL; a fifth issue is one file")
sys.exit(1 if fails else 0)
