# index

Which Fab City Index place this node belongs to, and what the Index says about it.

**What it reads.** One public file from index.fab.city (`INDEX_URL`), for the one place in `INDEX_PLACE`, once every
`INDEX_REFRESH_HOURS` (24 by default). The Index is published under CC BY 4.0 by the Fab City Foundation; the list
of places is the registry's `places.yaml` in awesome-fabcity-data.

**What it sends.** Nothing about the node. The request names the place by its slug, so no coordinates, no node id and
no address leave the house. Picking the place happens here, from `places.json` and the node's own point, and the
household confirms it.

**The place list.** `places.json` holds the 61 places the Index tracks and an approximate centre for each. The centres
assert no border; they only decide which place to suggest, and a node more than 150 km from every centre gets no
suggestion. Regenerate it with `python3 tools/build_index_places.py`.

**Off by default.** The pack is on once `INDEX_PLACE` is set.
