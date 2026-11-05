FROM python:3.12-slim
# pip in a container runs as root by design; its warnings about that, and about its own new versions, are noise
# that shows up red in `planetai update` and hides the lines that matter.
ENV PIP_ROOT_USER_ACTION=ignore PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# rasterio's wheel carries its own GDAL but links libexpat, which manylinux assumes the system provides and
# python:3.12-slim does not. Without it `pip install rasterio` succeeds and `import rasterio` fails, so
# `planetai packs install` reports success and the earth pack dies on its first run. 436 kB.
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 \
 && rm -rf /var/lib/apt/lists/*
COPY requirements*.txt ./
# requirements-packs.txt is written by `planetai packs` from the `pip:` lists of code packs (gitignored)
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ -s requirements-packs.txt ]; then pip install --no-cache-dir -r requirements-packs.txt; fi
# every module, not a list — a list silently omits new files and the app dies on import (v0.4.1)
COPY *.py ./
# app/ is not volume-mounted (docker-compose.yml mounts config, packs, out, backups, exports only),
# so a package directory reaches the image only by being named here. `COPY *.py` does not see it,
# and neither does it see the engine's fixtures. (The issues themselves are declared in packs/<id>/issue.yml, mounted.)
COPY issues ./issues
COPY static ./static
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
