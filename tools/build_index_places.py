#!/usr/bin/env python3
"""Regenerate packs/index/places.json: the places the Fab City Index tracks, with where each one is.

Dev tool, not run on a node (PyYAML is here, not in the node's Python):

  python3 tools/build_index_places.py [--registry ../awesome-fabcity-data] [--centres ../fci-3-prototype]

The list is the registry's places.yaml as it is on origin/main (the working tree of that checkout can lag it, so it
is read from the ref). The centres are the prototype's data/coordinates.json, keyed by the same slugs and written
[lat, lng]. A place with no centre is kept, with null, so the list stays the registry's and a suggestion never
names a place it cannot place.
"""
import argparse
import datetime
import json
import os
import subprocess

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(repo, *a):
    return subprocess.check_output(["git", "-C", repo, *a], text=True).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default=os.path.join(ROOT, "..", "awesome-fabcity-data"))
    ap.add_argument("--centres", default=os.path.join(ROOT, "..", "fci-3-prototype"))
    a = ap.parse_args()

    reg = git(a.registry, "show", "origin/main:places.yaml")
    reg_sha = git(a.registry, "rev-parse", "--short", "origin/main")
    coords_rel = "data/coordinates.json"
    centres = json.loads(git(a.centres, "show", "HEAD:" + coords_rel))["coordinates"]
    centres_sha = git(a.centres, "log", "-1", "--format=%h", "--", coords_rel)

    places = []
    for p in sorted(yaml.safe_load(reg)["places"], key=lambda p: p["slug"]):
        lat, lon = centres.get(p["slug"], (None, None))
        places.append({"slug": p["slug"], "name": p["name"], "country": p["country"], "lat": lat, "lon": lon})

    out = {
        "generated": datetime.date.today().isoformat(),
        "from": [
            "awesome-fabcity-data places.yaml @ origin/main " + reg_sha,
            "fci-3-prototype " + coords_rel + " @ " + centres_sha,
        ],
        "note": "centres are approximate (fci-3-prototype v0, from citiesmap) and assert no border",
        "places": places,
    }
    path = os.path.join(ROOT, "packs", "index", "places.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("%d places, %d with a centre -> %s" % (len(places), sum(p["lat"] is not None for p in places), path))


if __name__ == "__main__":
    main()
