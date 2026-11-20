"""The Place report's reading (docs/SPEC_place_report.md §11): the facts it may rest on, the rules that write it, the
check a model's text must pass, and the two routes. app/reading.py is imported as it is; the model is a stub and the
database a fake cursor, so nothing here needs Postgres, a network or a model.

Run: PYTHONPATH=app python3 tests/test_reading.py
"""
import json
import re
import sys
from datetime import date

import reading

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


TODAY = date(2026, 11, 17)
# node #1 as it stood on 17 Nov 2026: the place pack's last poll, one stale distance, the surface and the terrain
N1 = {"buildings": (2459.0, "2026-11-14"), "sat_buildings": (5994.0, "2026-11-14"), "osm_building_coverage": (0.41, "2026-11-14"),
      "built_share": (0.076, "2026-11-14"), "green_share": (0.341, "2026-11-14"), "commercial_share": (0.0, "2026-11-14"),
      "businesses_per_km2": (6.048, "2026-11-14"), "roads_km": (58.48, "2026-11-14"),
      "poi_food": (10.0, "2026-11-14"), "poi_retail": (3.0, "2026-11-14"), "poi_education": (0.0, "2026-11-14"),
      "poi_health": (0.0, "2026-11-14"), "poi_worship": (0.0, "2026-11-14"), "poi_lodging": (5.0, "2026-11-14"),
      "poi_services": (1.0, "2026-11-14"), "nearest_health_m": (948.305, "2026-11-14"),
      "lst_delta": (0.58, "2026-11-06"), "terrain_upslope_ha": (0.09, "2026-10-23")}
HYDRO = {"lat": -8.81961234, "lon": 115.16412345, "nearest": {"dist_m": 3555, "dis_av_cms": 0.125},
         "basin": {"level12": {"up_area": 318.6, "sub_area": 318.6, "endo": 0}, "level4": {"sub_area": 140534.8}}}
ENERGY = {"grid": "bali", "kind": "estimated", "share": {"low": 0.8419, "high": 0.9908927631259593},
          "sources": [{"name": "GIS Bandara", "km": 4.06, "lat": -8.74, "lon": 115.16}]}
INDEX = {"chosen": "bali", "place": {"name": "Bali", "slug": "bali"}, "read": {"ok": True, "at": "2026-11-16T08:41:54.129Z"},
         "score": {"status_label": "Partial", "cells_measured": 1, "cells_total": 20, "fci": 0.037}}
YEARLY = [(2016, 3105.0), (2019, 4410.0), (2023, 5994.0)]


def n1(**over):
    a = dict(latest=N1, hydro=HYDRO, energy=ENERGY, index=INDEX, labs=[3.4, 21.0], labs_radius_km=50, air=(12, 45), held=2, yearly=YEARLY, today=TODAY)
    a.update(over)
    return reading.shape(**a)


# ---------------------------------------------------------------- the facts
doc = n1()
F = doc["facts"]
check(F["clinic_km"] == {"v": 1, "at": "2026-11-14"}, f"a distance from the node's point is whole kilometres: {F.get('clinic_km')}")
# The place pack writes nearest_* only when it finds one, so an older run's distance outlives the run that found none
# (node #1: a clinic at 948 m on 6 Sep, poi_health 0 on 14 Nov). A distance older than the pack's last run is not held.
gone = n1(latest={**N1, "nearest_health_m": (948.305, "2026-09-06")})
check(gone["facts"]["clinic_km"] is None, f"a distance from an older run than the pack's last is not held: {gone['facts']['clinic_km']}")
check(not [k for k in F if k.endswith("_m")], "no fact is in metres from the node's point")
check(F["poi_health"] == {"v": 0, "at": "2026-11-14"}, f"a zero the node holds is held, not missing: {F.get('poi_health')}")
check(F["school_km"] is None and doc["fill"]["school_km"], "a fact the node does not hold is None, with what fills it")
check(F["river_km"]["v"] == 4 and F["basin_km2"]["v"] == 319 and F["bioregion_km2"]["v"] == 140535, f"hydro: {F.get('river_km')}, {F.get('basin_km2')}")
check(F["fossil_low_pct"]["v"] == 84 and F["fossil_high_pct"]["v"] == 100 and F["grid"]["v"] == "Bali", f"energy: the low end is rounded down and the high end up: {F.get('fossil_low_pct')} {F.get('fossil_high_pct')}")
check(n1(energy={**ENERGY, "share": {"low": 0.846, "high": 0.846}})["facts"]["fossil_low_pct"]["v"] == 84, "'at least 85%' is never printed for 84.6")
check(F["index_place"]["v"] == "Bali" and F["index_label"]["v"] == "Partial" and F["index_measured"]["v"] == 1 and F["index_cells"]["v"] == 20, "the Index place")
check(F["labs_near"]["v"] == 2 and F["lab_km"]["v"] == 3 and F["labs_radius_km"]["v"] == 50, f"labs: {F.get('labs_near')}, {F.get('lab_km')}")
none_near = n1(labs=[], labs_radius_km=30)
check(none_near["facts"]["labs_near"]["v"] == 0 and none_near["facts"]["labs_radius_km"]["v"] == 30 and none_near["facts"]["lab_km"] is None,
      "the make pack on and no lab in its radius is a held zero, within the radius it looked in")
check(n1(labs=None)["facts"]["labs_near"] is None and "labs_near" in n1(labs=None)["fill"], "the make pack off is a gap")
check(F["air_days_over"]["v"] == 12 and F["air_days"]["v"] == 45, "the air figure, with 30 measured days or more")
check(n1(air=(12, 20))["facts"]["air_days_over"] is None, "under 30 measured days the node does not state the air figure")
check(F["buildings_then"]["v"] == 3105 and F["buildings_then_year"]["v"] == 2016 and F["buildings_now_year"]["v"] == 2023 and F["cells_held"]["v"] == 2,
      "the yearly count with both its years, and the cells")
check(F["basin_ends"]["v"] == "the sea" and n1(hydro={**HYDRO, "basin": {**HYDRO["basin"], "level12": {"up_area": 318.6, "endo": 2}}})["facts"]["basin_ends"]["v"] == "a closed basin",
      "where the basin ends is hydro's to say")
check(F["place_radius_km"]["v"] == 1 and n1(radius_m=2000)["facts"]["place_radius_km"]["v"] == 2, "the radius the place pack counted in")
# a yearly source is stamped mid-year of its last complete year, and the ground does not move: neither goes stale at 400 days
slow = n1(latest={**N1, "tree_frac": (0.22, "2025-07-01"), "crop_frac": (0.1, "2025-07-01"), "terrain_upslope_ha": (0.09, "2024-01-05")})
check(slow["facts"]["tree_share"] is not None and slow["facts"]["upslope_ha"] is not None, "a yearly source and the terrain outlive 400 days")
check(n1(latest={**N1, "tree_frac": (0.22, "2023-07-01")})["facts"]["tree_share"] is None, "a yearly source two years behind is not held")
check(n1(latest={**N1, "green_share": (1.34, "2026-11-14")})["facts"]["green_share"] is None, "a share outside 0 to 1 is not a share (overlapping polygons): not held")
old = n1(latest={**N1, "green_share": (0.341, "2025-09-01")})
check(old["facts"]["green_share"] is None and "green_share" in old["fill"], "a figure older than 400 days counts as not held")
bare = n1(hydro=None)
check(all(bare["facts"][k] is None for k in ("river_km", "basin_km2", "bioregion_km2")) and bare["fill"]["basin_km2"] == "planetai run hydro fetch",
      "with no hydro every hydro fact is None, and the fill is the pack's own command")
J = json.dumps(doc)
check(not re.search(r"-?\d+\.\d{4,}", J), f"no coordinate, and nothing finer than three decimals, in the facts: {re.findall(r'-?[0-9]+[.][0-9]{4,}', J)[:3]}")
check(not re.search(r"lat|lon|sensor|GIS Bandara", J), "no point, no sensor and no named source in the facts")
check(set(doc["fill"]) == {k for k, v in F.items() if v is None}, "fill names exactly the facts that are missing")
check(reading.say("green_share", 0.341) == "34%" and reading.say("buildings", 2459.0) == "2459" and reading.say("heat_delta_c", 0.58) == "0.6"
      and reading.say("clinic_km", 1) == "1" and reading.say("grid", "Bali") == "Bali", "one formatter turns a fact into text")
empty = reading.shape(latest={}, hydro=None, energy=None, index=None, labs=None, labs_radius_km=50, air=None, held=None, yearly=[], today=TODAY)
check(reading.credits(doc, [{"id": "hydro", "attribution": "HydroSHEDS, CC-BY"}, {"id": "energy", "attribution": ["OSM, ODbL", "Ember, CC BY"]}, {"id": "fire", "attribution": "FIRMS"},
                            {"id": "place", "attribution": "© OpenStreetMap contributors"}, {"id": "surface-heat"}]) == ["HydroSHEDS, CC-BY", "OSM, ODbL", "Ember, CC BY", "© OpenStreetMap contributors"]
      and reading.credits(empty, [{"id": "hydro", "attribution": "HydroSHEDS, CC-BY"}]) == [], "the reading credits the packs whose figures it holds, and no other")
check(all(v is None for v in empty["facts"].values()) and set(empty["fill"]) == set(empty["facts"]), "a node that holds nothing has every fact None")
# node #1, 18 Nov 2026: the yearly series read 128 buildings in the circle where the footprints count 5994
off = n1(yearly=[(2016, 86.4), (2019, 106.6), (2023, 127.7)])
check(all(off["facts"][k] is None and k in off["fill"] for k in ("buildings_then", "buildings_then_year", "buildings_now", "buildings_now_year"))
      and off["facts"]["sat_buildings"]["v"] == 5994, "a yearly count several times off the satellite's footprints is a misread, and is not held")
check("128" not in json.dumps(reading.rules(off)) and "86" not in json.dumps(reading.rules(off)), "and the reading does not print it")
check(n1(latest={k: v for k, v in N1.items() if k != "sat_buildings"})["facts"]["buildings_now"]["v"] == 5994, "with no footprints to hold it against, the yearly count stands")
print(f"  reading: the facts ({len(F)} keys), whole kilometres, zeros held, stale and missing ones named with what fills them")

# ---------------------------------------------------------------- the rules
NAMES = re.compile(r"mumford|mcharg|papanek|meadows|jacobs", re.I)
R = reading.rules(doc)
sec = {s["id"]: s for s in R["sections"]}
check([s["id"] for s in R["sections"]] == [i for i, _ in reading.SECTIONS] and [s["heading"] for s in R["sections"]] == [h for _, h in reading.SECTIONS],
      "five sections, in the frame's order, with its headings")
check(all(s["lines"] and s["lines"] != [reading.NOTHING] for s in R["sections"]), f"on node #1 every section has something to say: {[(s['id'], len(s['lines'])) for s in R['sections']]}")
street, system = " ".join(sec["street"]["lines"]), " ".join(sec["system"]["lines"])
check("within a kilometre" in street and "as far as the public map goes" in street, f"the street is read within a kilometre, and a thin map is said to be thin: {street}")
check("41%" in system and "What is not drawn is not planned for." in system, f"the system section reads the gap in the map: {system}")
check("in this cell" not in json.dumps(R), "the place pack reads a kilometre round the point, never 'this cell'")
land, region, needs = (" ".join(sec[i]["lines"]) for i in ("land", "region", "needs"))
check("34% of the ground within a kilometre is green, and 8% is built on, as far as the public map goes." in land, f"the green and built line rests on the public map and says so: {land}")
check("The satellite counted 5994 buildings here in 2023, up from 3105 in 2016." in system, f"the yearly count is said with its year, never as today's: {system}")
check("a basin of 319 km² that ends in the sea" in region and "Bali is on the Fab City Index as Partial, with 1 of 20 cells measured." in region
      and "is about 3 km away, one of 2 within 50 km" in region, f"the region: {region}")
check("The nearest clinic or pharmacy drawn is about 1 km away" in needs, f"a health place is a clinic or a pharmacy: {needs}")
# what every node prints must hold on every node: no Balinese word, no season, no fuel the pack does not know, nothing the node cannot see
for word in ("banjar", "dry season", "coal", "somewhere else", "smoke"):
    check(word not in json.dumps(R) + json.dumps(reading.rules(empty)), f"'{word}' is in a rule every node runs")
A = R["avenues"]
check(4 <= len(A) <= 6, f"{len(A)} avenues, not four to six")
check(all(a["layer"] in reading.LAYERS and a["action"] in reading.ACTIONS and a["signal"] in reading.SIGNALS for a in A), "every avenue sits in the frame")
check(all(a["title"] and a["first_step"] and re.search(r"\d", a["why"]) for a in A), f"on node #1 every avenue has a first step and rests on a figure: {[a['why'] for a in A if not re.search(chr(92) + 'd', a['why'])]}")
check(any(a["with"] == "the lab about 3 km away" for a in A) and all(a["with"] is None for a in A if a["action"] == "Map and research"), f"an experiment names the lab's distance: {[a['with'] for a in A]}")
check(not NAMES.search(json.dumps(R)), "the reading names nobody")
check(R["blind"] and all(b["what"] and b["command"] for b in R["blind"]) and [b["what"] for b in R["blind"]] == ["trees and farmed land from the satellite"],
      f"what it cannot see, each with what fills it, and nothing it does see: {R['blind']}")
# a gap is named for what is missing, with the command that fills that and nothing else
nosat = reading.rules(n1(latest={k: v for k, v in N1.items() if k not in ("sat_buildings", "osm_building_coverage")}, yearly=[]))
check([b for b in nosat["blind"] if "satellite counts" in b["what"]] and all("place pack" not in b["command"] for b in nosat["blind"]),
      f"with the place pack on and no satellite counts, the gap is the satellite's, not the place pack's: {nosat['blind']}")
noclinic = reading.rules(gone)
nc = " ".join({x["id"]: x for x in noclinic["sections"]}["needs"]["lines"])
check("No clinic or pharmacy is drawn within a kilometre, as far as the public map goes." in nc and "No school is drawn within a kilometre" in nc
      and not any("clinic" in b["what"] or "school" in b["what"] for b in noclinic["blind"]),
      f"none drawn within the radius is a finding, not a gap: {nc} / {[b['what'] for b in noclinic['blind']]}")
check(any(a["title"].startswith("Ask who walks to the clinic") and "0" in a["why"] for a in reading.rules(n1(latest={**N1, "nearest_health_m": (948.305, "2026-09-06"),
      "lst_delta": (0.1, "2026-11-06"), "poi_lodging": (0.0, "2026-11-14"), "businesses_per_km2": (60.0, "2026-11-14")}, energy=None, index=None, yearly=[], held=7))["avenues"]),
      "and it opens an avenue")
far = json.dumps(reading.rules(n1(radius_m=2000)))
check("within 2 km" in far and "within a kilometre is green" not in far, "the radius in a sentence is the one the place pack counted in")
closed = reading.rules(n1(hydro={**HYDRO, "basin": {**HYDRO["basin"], "level12": {"up_area": 318.6, "endo": 2}}}))
check("the sea" not in json.dumps(closed) and "the coast" not in json.dumps(closed) and "a closed basin" in json.dumps(closed), "a closed basin is never walked to the sea")
gram = json.dumps(reading.rules(n1(labs=[3.4], held=0, index={**INDEX, "score": {**INDEX["score"], "cells_measured": 5}})))
check("the only one within 50 km" in gram and "one of 1" not in gram and "in none of its 7 cells" in gram and "0 of its 7" not in gram
      and "5 of the 20 cells of Bali on the Fab City Index are measured" in gram, "one lab, no held cell and five measured cells each read as a sentence")
nolab = reading.rules(none_near)
check("No fab lab is listed within 30 km." in " ".join({x["id"]: x for x in nolab["sections"]}["region"]["lines"]) and not any("make and fix" in b["what"] for b in nolab["blind"]),
      "the make pack on with no lab in its radius says so, within that radius, and is no gap")
print(f"  reading: node #1 reads as five sections and {len(A)} avenues, each in the frame, and says what it cannot see")

E = reading.rules(empty)
check(all(s["lines"] == [reading.NOTHING] for s in E["sections"]) and reading.NOTHING == "The node holds nothing yet that speaks to this.", "a section with nothing held says so in one line")
check(len(E["avenues"]) == 4 and all(a["action"] == "Map and research" and a["with"] is None for a in E["avenues"]), f"a node that holds nothing gets four avenues to map and research: {[a['title'] for a in E['avenues']]}")
check(all(any(c in a["first_step"] for c in set(reading.FILL.values())) for a in E["avenues"]), "each of them starts with the command that fills the gap")
check({k for b in E["blind"] for k in b["facts"]} == set(reading.FILL), f"everything missing is in the blind list: {set(reading.FILL) - {k for b in E['blind'] for k in b['facts']}}")
check("undefined" not in json.dumps(E) and "None" not in json.dumps(E), "nothing unfilled leaks into the text")
zero = reading.rules(n1(latest={**N1, **{k: (0.0, "2026-11-14") for k in N1 if k.startswith("poi_")}}))
zs = " ".join({s["id"]: s for s in zero["sections"]}["street"]["lines"])
check("0 kinds" not in zs and "house visitors" not in zs and "No shop" in zs, f"a place with nothing drawn says so, and divides by nothing: {zs}")
one = reading.rules(n1(labs=[0.3, 9.0], hydro={**HYDRO, "nearest": {"dist_m": 300}}))
check("A river runs within a kilometre." in json.dumps(one) and "the lab within a kilometre" in json.dumps(one) and not re.search(r"\b0 km", json.dumps(one)),
      "a distance under a kilometre is said in words, never as 0 km")
print("  reading: an empty node gets four avenues from its gaps; zeros and short distances read as sentences")

# ---------------------------------------------------------------- a model's text: kept only if its numbers are the node's
ALL = "\n".join(l for s in R["sections"] for l in s["lines"]) + "\n" + "\n".join(a["title"] + " " + a["why"] + " " + a["first_step"] + " " + (a["with"] or "") for a in A)
check(reading.stray_numbers(ALL, doc) == [], f"the rules print every number as the check reads it: {reading.stray_numbers(ALL, doc)}")
for ok_text in ("2,459 buildings are drawn, and 5,994 seen.", "34% of the ground is green", "34 % green", "a share of 0.34", "0.341 of the ground",
                "up from 3105 in 2016", "in 2 of its 7 cells", "three or 4 avenues, 1 to 7 of them", "140,535 km² and 140535 km²", "0.6 °C hotter", "within 50 km"):
    check(reading.stray_numbers(ok_text, doc) == [], f"'{ok_text}' holds only the node's numbers, yet {reading.stray_numbers(ok_text, doc)} strayed")
for bad_text, n in (("35% of the ground is green", "35"), ("about 2,500 buildings", "2500"), ("9 avenues", "9"), ("in 2021 it changed", "2021"), ("0.7 °C hotter", "0.7")):
    got = reading.stray_numbers(bad_text, doc)
    check(got and (n is None or n in got), f"'{bad_text}' strays, and the check said {got}")

# A small count passes as a count and never as a measurement: on a node that holds nothing, an invented figure with a
# unit is caught (final review, 17 Nov: "5 °C hotter, 50% missing, the clinic 7 km away" was kept, under "the node
# checked its numbers").
invented = "The surface here runs 5 °C hotter than the land around it, 50% of the buildings are missing from the map and the clinic is 7 km away."
check(reading.stray_numbers(invented, empty) == ["5", "50", "7"], f"invented measurements are caught on a node with no facts: {reading.stray_numbers(invented, empty)}")
check(reading.stray_numbers("3 avenues, 2 of its 7 cells, in 4 steps, 15 µg/m³ for a day", empty) == [] and reading.stray_numbers("15% of it, 3 ha, 6 m wide, 2%", empty) == ["15", "3", "6", "2"],
      "a bare small count and the guideline's own figure pass; the same digits before a unit do not")
cool = n1(latest={**N1, "lst_delta": (-1.2, "2026-11-06")})
for ok_text in ("1.2 °C cooler than the land around it", "-1.2 °C", "−1.2 °C"):
    check(reading.stray_numbers(ok_text, cool) == [], f"a negative fact can be cited: '{ok_text}' gave {reading.stray_numbers(ok_text, cool)}")

GOOD = {"sections": {i: f"A paragraph on {h.lower()}, resting on 34% of green ground and 5,994 buildings." for i, h in reading.SECTIONS},
        "avenues": [{"title": f"Avenue {k}", "why": "84% of the power is burned.", "first_step": "Count ten roofs.", "layer": reading.LAYERS[k],
                     "action": reading.ACTIONS[k % 3], "signal": reading.SIGNALS[k % 3]} for k in range(4)]}
w, why = reading.accept(json.dumps(GOOD), doc)
check(w is not None and why == "" and set(w["sections"]) == {i for i, _ in reading.SECTIONS} and len(w["avenues"]) == 4 and w["avenues"][0]["with"] is None, f"a good answer is kept: {why}")
check(reading.accept("```json\n" + json.dumps(GOOD) + "\n```", doc)[0] is not None, "a fenced answer is kept")
check(reading.accept("Here is the reading:\n" + json.dumps(GOOD) + "\nI hope it helps.", doc)[0] is not None, "prose round the answer is dropped")
check(reading.accept('<think>The shape is {"sections": {...}} so I will fill it.</think>\n' + json.dumps(GOOD), doc)[0] is not None, "a thinking block with a brace in it is dropped")
check(reading.accept(json.dumps(GOOD) + "\nNote: I kept {layer} from the frame.", doc)[0] is not None, "prose with a brace after the answer is dropped")
cased = json.loads(json.dumps(GOOD)); cased["avenues"][0].update(layer="place-based Interventions", action="map and research", signal="Asset")
w2, why2 = reading.accept(json.dumps(cased), doc)
check(w2 is not None and (w2["avenues"][0]["layer"], w2["avenues"][0]["action"], w2["avenues"][0]["signal"]) == ("Place-based interventions", "Map and research", "asset"),
      f"the frame's words are matched whatever their capitals, and kept as the frame writes them: {why2}")
meadow = json.loads(json.dumps(GOOD)); meadow["sections"]["land"] = "Water meadows and rice fields lie below, with 34% of the ground green."
check(reading.accept(json.dumps(meadow), doc)[0] is not None, "a meadow is not a person")


def bad(change, want):
    g = json.loads(json.dumps(GOOD)); change(g)
    got, reason = reading.accept(json.dumps(g), doc)
    check(got is None and want in reason, f"expected a refusal saying '{want}', got {reason!r}")
    return reason


reasons = {bad(lambda g: g["sections"].pop("land"), "section"), bad(lambda g: g["sections"].update(extra="x"), "section"),
           bad(lambda g: g["avenues"].pop(), "avenues"), bad(lambda g: g["avenues"].extend(g["avenues"][:3]), "avenues"),
           bad(lambda g: g["avenues"][0].update(layer="Energy"), "layer"), bad(lambda g: g["avenues"][1].update(action="Build"), "action"),
           bad(lambda g: g["sections"].update(land="Of the ground, 51% is green."), "51"),
           bad(lambda g: g["sections"].update(street="As Jane Jacobs would say, the street lives."), "names a person"),
           bad(lambda g: g["avenues"][2].update(why="MUMFORD saw 84% of this."), "names a person"),
           bad(lambda g: g["sections"].update(region=""), "empty"), bad(lambda g: g["sections"].update(region="word " * 200), "too long"),
           bad(lambda g: g["sections"].update(region="w" * 800), "too long"),
           bad(lambda g: g["sections"].update(land="Half of the ground is green, twice what it was."), "in words"),
           bad(lambda g: g["avenues"][0].update(why="It matters to everyone here."), "no figure"),
           bad(lambda g: g["sections"].update(system="Donella Meadows would see a loop here."), "names a person"),
           bad(lambda g: g["avenues"][3].update(first_step="Count the roofs. " * 20), "too long")}
check(len(reasons) >= 11, f"each kind of refusal says its own reason: {reasons}")
for junk in ("not json", "", "[1, 2]", '{"sections": "x"}', '{"sections": {}, "avenues": null}'):
    got, reason = reading.accept(junk, doc)
    check(got is None and reason, f"{junk!r} is refused with a reason, never an exception")
# node #1, 18 Nov 2026: the model gave the node's own reading back word for word, and the node kept it as a model's
OWN = {s["id"]: " ".join(s["lines"]) for s in R["sections"]}
got, reason = reading.accept(json.dumps({**GOOD, "sections": OWN}), doc, R)
check(got is None and "the node's own sentences" in reason, f"a model that gives the node's reading back is refused: {reason!r}")
got, reason = reading.accept(json.dumps({**GOOD, "sections": {**GOOD["sections"], "land": OWN["land"] + " And so the ground is hard."}}), doc, R)
check(got is None and "land" in reason and "the node's own sentences" in reason, f"one section copied with a line added is refused too: {reason!r}")
one = sec["land"]["lines"][0]
check(reading.accept(json.dumps({**GOOD, "sections": {**GOOD["sections"], "land": one + " The rest is the model's own."}}), doc, R)[0] is not None
      and reading.accept(json.dumps(GOOD), doc, R)[0] is not None, "one sentence of the node's in a text of its own is kept")
bare_av = [{**a, "title": "Fill the gap", "why": "Nothing is held in 2 of its 7 cells."} for a in GOOD["avenues"]]
check(reading.accept(json.dumps({"sections": {i: reading.NOTHING for i, _ in reading.SECTIONS}, "avenues": bare_av}), empty, E)[0] is not None,
      "where the node holds nothing, saying so in its words is not a copy")
P = reading.prompt(doc, R)
check("Do not give its sentences back" in P and json.dumps(OWN["region"], ensure_ascii=False) not in P and all(l in P for l in sec["region"]["lines"]),
      "the prompt hands the node's reading as findings, line by line, never in the shape of the answer, and asks for more than them")
check(all(h in P for _, h in reading.SECTIONS) and all(x in P for x in reading.LAYERS + reading.ACTIONS + reading.SIGNALS) and "name no person" in P.lower()
      and '"green_share"' in P and "60 to 120 words" in P and "in digits" in P, "the prompt carries the frame, the facts, the ban on names and figures in digits")
check(len(NAMES.findall(P)) == 5, "the five names live in the prompt, once each, and nowhere else")
print("  reading: a model's text is kept only with the frame's ids, the node's numbers and no person named")

# ---------------------------------------------------------------- kept on the node, read by the household, written on a button
# Driven through the app with the database and the model faked, as tests/test_cells.py drives its routes.
import logging  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

logging.disable(logging.WARNING)
os.environ.update(ADMIN_TOKEN="admin-tok", ACT_TOKEN="act-tok", DATABASE_URL="postgresql://unused/never-connected")
import settings  # noqa: E402
settings._cache = {"at": time.time() + 1e9, "rows": {"SHARE_LEVEL": "open", "BACKUP_TOKEN": "backup-tok"}}
import agent_loop  # noqa: E402
import auth  # noqa: E402
import main  # noqa: E402 — importing the app starts nothing
from fastapi.testclient import TestClient  # noqa: E402

online = agent_loop.Rung("online", "https://api.anthropic.com/v1", "claude", "key")
home = agent_loop.Rung("remote", "http://100.72.1.5:8080/v1", "qwen3.5:122b")
away = agent_loop.Rung("remote", "https://gpu.example.org/v1", "big")
small = agent_loop.Rung("local", "http://host.docker.internal:11434/v1", "qwen3:4b", small=True)
check(reading.pick([online, home, small]) is home and reading.pick([online, small]) is None and reading.pick([away, small]) is None and reading.pick([]) is None,
      "the writer is the first model that is neither small nor off the house's network")


class Cur:
    """place_readings in a list; every other read answers nothing, which is a node that holds nothing."""
    def __init__(self):
        self.rows, self._last = [], []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, q, params=()):
        u = " ".join(q.split())
        if u.startswith("INSERT INTO place_readings"):
            self.rows.append({"id": len(self.rows) + 1, "ts": datetime.now(timezone.utc), "state": "writing", "rung": params[0], "model": params[1],
                              "wherefrom": params[2], "facts": params[3], "text": None, "refused": None})
            self._last = [{"id": len(self.rows)}]
        elif u.startswith("UPDATE place_readings"):
            row = next(r for r in self.rows if r["id"] == params[3])
            row.update(state=params[0], text=getattr(params[1], "obj", params[1]), refused=params[2])
        elif "FROM place_readings" in u:
            self._last = sorted(self.rows, key=lambda r: -r["id"])
        elif "FROM readings_1h" in u:
            self._last = [{"over": 0, "days": 0}]
        else:
            self._last = []

    def fetchall(self):
        return self._last

    def fetchone(self):
        return self._last[0] if self._last else None


class Con:
    def __init__(self, cur):
        self.cur = cur

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def transaction(self):
        return self

    def cursor(self):
        return self.cur


cur = Cur()
src_reading = open("app/reading.py").read()
reading._db = lambda: Con(cur)
reading._held = lambda c: (HYDRO, ENERGY, INDEX, 2)        # what the packs and the cells hold, read in process on a node
started, asked = [], []
reading._spawn = lambda fn, *a: started.append((fn, a))
reading._rungs = lambda: [online, home, small]
c = TestClient(main.app)
local = TestClient(main.app, client=("127.0.0.1", 51000))
ACT, ADMIN = {"Authorization": "Bearer act-tok"}, {"Authorization": "Bearer admin-tok"}

for level in ("off", "open"):
    exact, prefixes = auth._SHARE[level]
    check("/place/reading" not in exact and not any("/place/reading".startswith(pre) for pre in prefixes), f"/place/reading is on no SHARE_LEVEL allowlist ({level})")
check(c.get("/place/reading").status_code in (401, 403) and c.post("/place/reading").status_code in (401, 403), "a caller with no token reads and writes nothing")
check(c.get("/place/reading", headers={"Authorization": "Bearer backup-tok"}).status_code == 401, "the backup token is refused here")
check(c.post("/place/reading", headers=ACT).status_code in (401, 403) and not cur.rows, "the act token reads the reading and may not ask for one")
g = c.get("/place/reading", headers=ACT)
b = g.json() if g.status_code == 200 else {}
check(g.status_code == 200 and b.get("state") == "none" and b.get("written") is None and b.get("by") == "node" and b.get("can_write") is False
      and [x["id"] for x in b["rules"]["sections"]] == [i for i, _ in reading.SECTIONS], f"the act token reads the node's own reading: {g.status_code} {str(b)[:200]}")
check("Bali" in json.dumps(b) and "84%" in json.dumps(b), "it rests on what the node's packs hold")
check(isinstance(b.get("credits"), list), "and carries the credits those figures owe, for the sources page")
check("r.sensor_id = ANY(%s)" in src_reading and "r.ts <= now()" in src_reading and "place-point" in src_reading and "ee-point" in src_reading,
      "the latest figures are read from the place-scale sensors only, and never from a row dated in the future")
check("127.0.0.1" not in src_reading and "httpx.get" not in src_reading, "the packs are read in process, not over the node's own port")
check(not re.search(r'"(lat|lon|sensor[a-z_]*)"\s*:', json.dumps(b)) and not re.search(r"-?\d+\.\d{4,}", json.dumps(b)), "no point and no sensor in the answer")
check(c.get("/place/reading", headers=ADMIN).json().get("can_write") is True and local.get("/place/reading").json().get("can_write") is False,
      "only the admin token is offered the button")

reading._rungs = lambda: [online, small]
r = c.post("/place/reading", headers=ADMIN)
check(r.status_code == 409 and r.json().get("detail") == "No model on this house's network can write this. The reading above is the node's own." and not cur.rows,
      f"with no model at home that is not small, 409 and the sentence: {r.status_code} {r.text[:120]}")
check(c.get("/place/reading", headers=ADMIN).json().get("can_write") is False, "and no button")
reading._rungs = lambda: [online, home, small]

r1, r2 = c.post("/place/reading", headers=ADMIN), c.post("/place/reading", headers=ADMIN)
check(r1.status_code == 202 and r2.status_code == 202 and r1.json() == r2.json() == {"state": "writing", "id": 1} and len(started) == 1 and len(cur.rows) == 1,
      f"a second press while one is writing starts nothing: {r1.status_code} {r1.text} {r2.text} started {len(started)}")
check(cur.rows[0]["rung"] == "remote" and cur.rows[0]["model"] == "qwen3.5:122b" and cur.rows[0]["wherefrom"] == "your network", f"the row says who writes: {cur.rows[0]}")
check(c.get("/place/reading", headers=ACT).json().get("state") == "writing", "another screen sees it being written")
reading._ask = lambda rung, system: asked.append((rung.model, system)) or "Sorry, I cannot."
fn, a = started.pop()
fn(*a)
b = c.get("/place/reading", headers=ADMIN).json()
check(len(asked) == 2 and "FACTS" in asked[0][1] and asked[1][1].startswith(asked[0][1]) and "Your last answer was refused: not the JSON it was asked for" in asked[1][1],
      f"a refused text is asked for once more, with the reason: {len(asked)} asked")
check(cur.rows[0]["state"] == "refused" and b["state"] == "refused" and b["refused"] and b["written"] is None
      and b["by"] == "node" and b["rules"]["avenues"], f"a text that does not hold is refused with its reason, and the node's reading stands: {b.get('refused')}")

# the fake database holds no reading of the place pack, so this text rests only on what the routes answered
HELD = {"sections": {i: f"A paragraph on {h.lower()}: at least 84% of the power on the Bali grid is burned." for i, h in reading.SECTIONS}, "avenues": [{**a, "title": "Count the roofs"} for a in GOOD["avenues"]]}
# node #1, 18 Nov 2026: half of the model's first answers tripped on 'half' or a figure it worked out; told why, it writes again
answers = [json.dumps({**HELD, "sections": {**HELD["sections"], "land": "More than half of the ground is bare."}}), json.dumps(HELD)]
reading._ask = lambda rung, system: answers.pop(0)
check(c.post("/place/reading", headers=ADMIN).json() == {"state": "writing", "id": 2} and len(started) == 1, "after a refusal the button writes again")
fn, a = started.pop()
fn(*a)
b = c.get("/place/reading", headers=ACT).json()
check(b["state"] == "written" and b["written"]["sections"]["land"] == HELD["sections"]["land"] and b["by"] == {"model": "qwen3.5:122b", "where": "your network"}
      and b["written_at"] and b["refused"] is None and not answers, f"a second answer that holds is kept, with who wrote it and when: {str(b)[:200]}")


def boom(rung, system):
    raise TimeoutError("the model went away")


reading._ask = boom
c.post("/place/reading", headers=ADMIN)
fn, a = started.pop()
fn(*a)
b = c.get("/place/reading", headers=ACT).json()
check(cur.rows[2]["state"] == "refused" and "TimeoutError" in cur.rows[2]["refused"] and b["state"] == "refused" and b["written"]["sections"]["land"] == HELD["sections"]["land"],
      "a model that fails is a refusal, and the last text that held is still shown")
c.post("/place/reading", headers=ADMIN)
started.pop()
cur.rows[3]["ts"] = datetime.now(timezone.utc) - timedelta(minutes=11)
b = c.get("/place/reading", headers=ADMIN).json()
check(b["state"] == "refused" and b["refused"] == "took too long" and b["can_write"] is True, f"a writing older than ten minutes no longer holds the button: {b.get('state')} {b.get('refused')}")
check(c.post("/place/reading", headers=ADMIN).json() == {"state": "writing", "id": 5} and len(started) == 1, "and a new press starts a new one")
init = open("init.sql").read()
check("CREATE TABLE IF NOT EXISTS place_readings" in init and init.rstrip().endswith("INSERT INTO schema_version (version) VALUES ('0.66') ON CONFLICT DO NOTHING;"),
      "the table is in init.sql, at schema 0.66")
print("  reading: the routes are the household's, the admin token alone may ask a model at home, one writing at a time, and a refusal keeps the node's reading")

# ---------------------------------------------------------------- the two pages (app/static/doors-sheet.js reportPages)
# The rules' own output goes to the page's own function under node, through stdin (Linux CI caps argv at 128 KB).
import subprocess  # noqa: E402

PAGES = r"""
const fs = require('fs'); globalThis.esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const S = require('./app/static/doors-sheet.js'), I = JSON.parse(fs.readFileSync(0, 'utf8'));
const D = { node: { name: 'bayu-ungasan' }, health: { version: 'v0.92.0', cell: { id: '8895a4c855fffff' } } };
const base = { date: '2026-11-17', figures: '<p>figures</p>', cake: [], change: null, credits: ['Natural Earth'] };
const out = {}; for (const k in I) out[k] = S.reportPages(D, { ...base, credits: [...base.credits, ...((I[k] && I[k].credits) || [])], reading: I[k] });
console.log(JSON.stringify(out));
"""
ruled = {"facts_at": "2026-11-17", "rules": R, "written": None, "written_at": None, "by": "node", "state": "none", "refused": None, "can_write": False,
         "credits": ["Copernicus WorldDEM-30 © DLR e.V. 2010-2014", "Natural Earth"]}
model = {**ruled, "written": {"sections": {i: f"The model on {i}." for i, _ in reading.SECTIONS}, "avenues": [{**a, "title": "Model: " + a["title"], "with": None} for a in A[:4]]},
         "written_at": "2026-11-17T03:04:05+00:00", "by": {"model": "qwen3.5:122b", "where": "your network"}, "state": "written"}
bare = {**ruled, "rules": E}
pg = json.loads(subprocess.run(["node", "-e", PAGES], input=json.dumps({"ruled": ruled, "model": model, "bare": bare, "none": None}),
                               capture_output=True, text=True, check=True).stdout)
arts = lambda h: re.findall(r'<article class="rpage"[^>]*>(.*?)</article>', h, re.S)  # noqa: E731
P0, PR_, PM, PB = arts(pg["none"]), arts(pg["ruled"]), arts(pg["model"]), arts(pg["bare"])
check(len(P0) == 3 and "reading of this place" not in pg["none"] and "Full Stack" not in pg["none"], f"with no reading the report is what it was: {len(P0)} pages")
check(len(PR_) == 5 and "a reading of this place" in PR_[0] and "ways to improve it" in PR_[1] and "<p>figures</p>" in PR_[2],
      f"the reading and the avenues are the first two pages after the sheet, before the figures: {len(PR_)}")
check(all(f"page {i + 1} of 5" in a for i, a in enumerate(PR_)), "the head lines count the pages that are there")
WHO = "Written by this node from its own figures, 17 November 2026."
check(WHO in PR_[0] and WHO in PR_[1], "under each title, who wrote it and when")
check(all(esc_h in PR_[0] for esc_h in ("The region it belongs to", "What the land allows", "What people here need", "How the place behaves", "The life of the street"))
      and "Rain that falls here leaves by a basin of 319 km²" in PR_[0], "the five headings with the rules' sentences")
check(all(f"{a['layer']} · {a['action']}" in PR_[1] and a["title"] in PR_[1] and a["first_step"] in PR_[1] for a in A) and "the lab about 3 km away" in PR_[1]
      and PR_[1].count('class="av"') == len(A), "every avenue with its layer, its key action, its first step and the lab")
check("what this reading cannot see" in PR_[1] and all(b["what"] in PR_[1] for b in R["blind"]), "what the reading cannot see closes the second page")
MWHO = "Written by a language model on your network (qwen3.5:122b) from the node’s figures, 17 November 2026. The node checked its numbers."
check(MWHO in PM[0] and MWHO in PM[1] and "The model on land." in PM[0] and "Rain that falls here" not in PM[0] and "Model: " in PM[1] and PM[1].count('class="av"') == 4,
      f"a model's text takes the place of the rules', and says a model wrote it: {PM[0][:300]}")
check("what this reading cannot see" in PM[1] and all(b["what"] in PM[1] for b in R["blind"]) and len(PM) == 5, "what is missing is still the rules' to say")
six = {**model, "written": {**model["written"], "avenues": [{**a, "with": None} for a in A]}}
P6 = arts(json.loads(subprocess.run(["node", "-e", PAGES], input=json.dumps({"six": six}), capture_output=True, text=True, check=True).stdout)["six"])
check(len(P6) == 6 and P6[1].count('class="av"') == 4 and "cannot see" not in P6[1] and "ways to improve it, continued" in P6[2] and P6[2].count('class="av"') == 2
      and "<b>5</b>" in P6[2] and "cannot see" in P6[2] and "page 3 of 6" in P6[2], "past four, a model's avenues go on a page of their own, with what is missing")
check(len(PB) == 5 and PB[1].count('class="av"') == 4 and PB[0].count(reading.NOTHING) == 5 and not re.search(r"undefined|null|NaN", PB[0] + PB[1]),
      "a node that holds nothing still draws both pages, with four avenues and nothing unfilled")
check("The avenues follow the Fab City Full Stack: fab.city." in PR_[-1] and not NAMES.search(pg["ruled"] + pg["model"] + pg["bare"]), "the sources page names the frame, and no page names a person")
check("Copernicus WorldDEM-30 © DLR e.V. 2010-2014" in PR_[-1] and PR_[-1].count("Natural Earth") == 1, "the sources page carries the credits the reading owes, each once")
check("...((RD && RD.credits) || [])" in open("app/static/doors-place.js").read(), "and the page hands them to the sources page")
sheet_js = open("app/static/doors-sheet.js").read()
check(not NAMES.search(sheet_js) and not NAMES.search(open("app/static/doors-place.js").read()), "nor does the page's code")
html = open("app/static/doors.html").read()
check('id="prwrite"' in html and re.search(r"\.rpage \.av\{[^}]*break-inside:avoid", html), "the bar has the button, and an avenue is never split across pages")
print("  reading: two pages after the sheet, who wrote them under each title, a model's text in place of the rules' when one held")

# The foot of Place carries one line on who wrote the reading and when (SPEC_place_report §12), and its second
# paragraph says the report has a reading in it.
FOOT = r"""
const fs = require('fs'); globalThis.esc = s => String(s);
const S = require('./app/static/doors-sheet.js'), I = JSON.parse(fs.readFileSync(0, 'utf8'));
console.log(JSON.stringify(Object.fromEntries(Object.entries(I).map(([k, v]) => [k, S.readingFoot(v)]))));
"""
ft = subprocess.run(["node", "-e", FOOT], input=json.dumps({"ruled": ruled, "model": model}), capture_output=True, text=True)
ft = json.loads(ft.stdout) if ft.returncode == 0 else {}
check(ft.get("ruled") == "Reading written 17 November 2026 by this node"
      and ft.get("model") == "Reading written 17 November 2026 by a language model on your network", f"the foot's line says who wrote the reading and when: {ft}")
place_js = open("app/static/doors-place.js").read()
foot_html = html[html.index('id="preportfoot"'):html.index('id="preport"')]
check("A plan of the map as you have it on screen. A reading of the place, with ways to improve it." in foot_html, "the foot says the report reads the place")
check(re.search(r"function pages\(RD\) \{[^}]*footWho\(RD\)", place_js, re.S) and "if (PWHO || !DOORS_TOKEN()) return" in place_js
      and not NAMES.search(foot_html), "the line is asked for once, on a screen holding the token, and a new reading rewrites it")
print("  reading: the foot of Place says who wrote the reading and when")

# ---------------------------------------------------------------- what describes the report names nobody either
# Tomas, 17 Nov 2026: "it is for consumption, so do not mention the names of experts behind it". The prompt in
# app/reading.py is the one place they live; the layer list's own docs keep McHarg, by his ruling of 4 Nov.
for path, start, end in (("docs/site/place.md", "### The reading, and ways to improve the place", "## Folding"),
                         ("docs/site/api.md", "### GET /place/reading", "### POST /area"),
                         ("docs/SPEC_place_report.md", "## 11 · The reading", None),
                         ("CHANGELOG.md", "**The Place report reads the place.**", "\n\n- **")):
    text = open(path).read()
    check(start in text, f"{path} has no '{start}'")
    if start in text:
        part = text[text.index(start):]
        part = part[:part.index(end, len(start))] if end and end in part[len(start):] else part
        check(len(part) > 300 and not NAMES.search(part), f"{path}: the part on the reading names a person, or is missing")
src = open("app/reading.py").read()
held_in = src[src.index("MANNER = ("):src.index("UNITS = re.compile")]
check(len(NAMES.findall(held_in)) >= 10 and not NAMES.search(src.replace(held_in, "")), "in app/reading.py the names are in the prompt's manner and the refusal's pattern, and nowhere else")
print("  reading: the docs, the API page, the spec and the changelog describe it without naming anybody")

if fails:
    print("\n".join("  x " + f for f in fails))
    sys.exit(1)
print("reading: every check passed")
