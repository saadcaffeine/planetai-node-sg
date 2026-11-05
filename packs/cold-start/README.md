# cold-start

**The problem it solves.** The worst week of any sensing deployment is the first one: nothing to look at, nothing to
compare against, and no reason for anyone to keep the thing running. A node that already knows what normal looks like
at its coordinates is a node that survives to week two.

**What it adds** — three rules that need no hardware at all:

- `modelled_air_today` — an air-quality line from Copernicus CAMS at your coordinates, and says it is a model. Weekly at most: the daily reports carry the model reading now.
- `hotter_than_normal` — today against 40+ years of NASA POWER satellite climatology for this month, at this point.
- `sensor_vs_model` — once you *do* have an outdoor sensor, the weekly gap between it and the model. A big gap isn't an error; it's the local signal the global model can't see, which is the entire argument for hyperlocal nodes.

**Where the data comes from** — the `BOOTSTRAP` step on first start (92 days of CAMS hourly history, NASA POWER
monthly normals) plus the recurring `open-meteo` adapter and the CAMS one in `air-quality`. All free, all key-free, all global.

**When to delete it** — when your own sensors carry the story and the modelled line is noise. It is a scaffold, not a
foundation. Nothing here is ever eligible for a `live` Index cell, because none of it is a measurement of your place.
