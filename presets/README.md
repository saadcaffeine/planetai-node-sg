Site presets: coordinates, time zone, language, the city's open-data portal where it has a CKAN one, and the
issues the dashboard leads with (`NODE_ISSUES`). Four are Fab City Index pilots (Bali, Barcelona, Boston,
Santiago); Delhi and Menorca are not — Delhi is a worked example, Menorca is where node #2 runs.

    ./install.sh --preset barcelona --name lab-roof --airgradient ag1.local

Everything a preset sets can be overridden by a flag or edited in `.env` afterwards. Nowhere on this list? Run without a preset and pass `--lat --lon`. A node bootstraps from global sources at
any coordinates on earth, so nothing depends on being listed here.

Adding your city is one file and a pull request. Copy the closest one and change the five values and `NODE_ISSUES`;
leave out `BAD_ENABLED`, which only Bali's preset sets (the `bali-air-dispatch` pack is off everywhere else). If your city runs a CKAN portal, add it; test the URL first with
`https://<domain>/api/3/action/package_search?rows=0`.
