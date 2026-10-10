"""The wind over this node's square, now:   planetai run forecast windfield

Open-Meteo's hourly 10 m wind for the next day at FORECAST_WIND_N × FORECAST_WIND_N points (default 8 × 8) over a
square FORECAST_WIND_KM each side of the node (default 30 km), written to out/ground/wind.json for the map to draw
moving. The forecast pack refreshes it on every poll; this asks now. It uses Open-Meteo, so it runs only with
FORECAST_OPENMETEO=1: the free tier is non-commercial, and that is the operator's decision. Open-Meteo learns the
square, as it already learns the node's point from the forecast.
"""
import os
import sys

import httpx

sys.path.insert(0, os.path.dirname(__file__))
import adapter as A  # noqa: E402

if os.getenv("FORECAST_OPENMETEO", "0") != "1":
    sys.exit("forecast: Open-Meteo is off on this node (FORECAST_OPENMETEO=0). Its free tier is non-commercial; "
             "turning it on is your decision: set FORECAST_OPENMETEO=1 in Set up, then run this again.")
f = A.write_wind_field(httpx.Client(timeout=60), float(os.environ["NODE_LAT"]), float(os.environ["NODE_LON"]))
print(f"forecast: wind field {f['n']}×{f['n']} over ±{f['km']:.0f} km, {len(f['times'])} hours from {f['times'][0]}. "
      f"Served at /ground/wind.")
