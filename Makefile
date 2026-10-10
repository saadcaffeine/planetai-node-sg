PORT := $(or $(shell grep "^APP_PORT=" .env 2>/dev/null | cut -d= -f2),8080)
.PHONY: up update bootstrap down restart logs health stats alerts cells rho backup lint test ship released check-floors docs learn
up:      ; ./install.sh
update:  ; ./update.sh
bootstrap: ; docker compose exec -T app python -c "import os,main,bootstrap,httpx; print(bootstrap.run(main.db(), httpx.Client(timeout=60), float(os.environ['NODE_LAT']), float(os.environ['NODE_LON'])))"
down:    ; docker compose down
restart: ; docker compose up -d --force-recreate app   # apply .env changes
logs:    ; docker compose logs -f app
health:  ; curl -s localhost:$(PORT)/health | python3 -m json.tool
stats:   ; curl -s localhost:$(PORT)/stats  | python3 -m json.tool
alerts:  ; curl -s localhost:$(PORT)/alerts | python3 -m json.tool
cells:   ; curl -s localhost:$(PORT)/cells  | python3 -m json.tool
rho:     ; curl -s localhost:$(PORT)/rho    | python3 -m json.tool
backup:  ; ./backup.sh
# A merge is not a release: install.sh and bin/planetai reach a tester inside the tarball, which only
# changes when somebody rebuilds it. `released` asks whether the site is behind; `ship` fixes it.
# `released` exits 1 when behind, so a script can gate on it — make prints its own error line then.
# Every version floor the installer asserts, with the vendor URL and the date somebody read it.
# Fails when an entry is older than 180 days: a moved floor should be a red build, not a wasted evening.
check-floors: ; @python3 tools/check_floors.py
# The documentation site: docs/site/*.md plus the docs/ pages the sidebar lists, rendered on the dashboard's own tokens
# into the site repo. Needs `pip install markdown` on the dev machine; a node never runs this.
docs:    ; python3 tools/build_learn.py && python3 tools/build_docs.py --out ../planetai/docs
# The learn layer's marks, cut out of docs/site. `make docs` runs it; lint checks it did.
learn:   ; python3 tools/build_learn.py
released: ; @tools/ship.sh --check
ship:    ; tools/ship.sh
# Import the app the way uvicorn does. Catches module-level errors that pass every static check —
# a function called as if it were a string took the node down for an hour (5 Sep). Needs the app's deps installed.
import-check:
	@cd app && DATABASE_URL=postgresql://x:x@127.0.0.1:1/x NODE_NAME=t NODE_CITY=bali NODE_LAT=-8.8 NODE_LON=115.1 PACKS_DIR=../packs \
	  timeout 60 python3 -c "import main; assert len(main.app.routes) > 15; print('  app imports,', len(main.app.routes), 'routes')" > /tmp/planetai-import.log 2>&1; rc=$$?; \
	  grep -vE "bootstrap failed|Is the server|connection to server|Connection refused|GSSAPI|^ *$$" /tmp/planetai-import.log; exit $$rc
# data/vendor.sha256: the two vendored drawing libraries (docs/SPEC_dashboard_figures.md §4.1). Replacing one is a
# deliberate act: fetch the new version, rewrite its line, and say why in the commit.
lint:    ; bash -n install install.sh backup.sh update.sh bin/planetai tools/preflight.sh tools/ship.sh tools/session.sh && python3 tools/check_floors.py && python3 tools/gen_floors.py --check && python3 tools/gen_defaults.py --check && python3 tools/render_platforms.py --check && python3 tools/extract_strings.py --check && python3 tools/check_sql.py && python3 tools/check_cli_python.py && python3 tools/check_docs.py && python3 tools/check_registry.py && python3 tools/check_ui.py && python3 tools/build_learn.py --check && python3 tools/build_docs.py --check && python3 tools/check_site.py && python3 tools/check_wire.py && python3 tools/check_theme.py && shasum -a 256 -c --quiet data/vendor.sha256 && bash tools/check_requirements.sh && (if python3 -c 'import sqlglot' 2>/dev/null; then python3 tools/check_rules.py; else echo '  - rule check skipped (pip install sqlglot)'; fi) && python3 -m py_compile app/*.py app/issues/*.py && (python3 -c 'import pyflakes' 2>/dev/null && python3 -m pyflakes app/*.py app/issues/*.py packs/*/*.py | grep -v 'imported but unused' | grep . && exit 1 || true) && python3 -c "import yaml;yaml.safe_load(open('config/rules.yml'));c=yaml.safe_load(open('docker-compose.yml'));[yaml.safe_load(open(w)) for w in __import__('glob').glob('.github/workflows/*.yml')];b=[n for n,v in c['services'].items() if 'env_file' in v and n not in ('app','agent')];assert not b, 'env_file: .env hands a container every secret the node holds. Only app and agent may: '+', '.join(b)+'. List the keys it reads under environment: instead';print('  only app and agent are handed the whole .env')" && python3 -c "import re,glob;e=open('.env.example').read();assert not re.search(r'^[A-Z_]+=[ \t]+#', e, re.M), 'a comment after a key that ships blank becomes its value: move it above the key';u=[f for f in sorted(glob.glob('packs/*/*.py')) if 'httpx.Client()' in open(f).read()];assert not u, 'httpx.Client() with no timeout, and httpx has no read timeout by default: '+', '.join(u);print('  .env.example comments are above their keys; every pack http client has a timeout')" && (if python3 -c 'import fastapi' 2>/dev/null; then $(MAKE) -s import-check; else echo '  - import check skipped (pip install -r app/requirements.txt to enable)'; fi) && echo ok
# Every suite, one line each, with a count at the end — and a non-zero exit when a check skipped that
# nobody declared. The old form was a chain of `&&`, so the first failure hid the rest.
test:    ; bash tests/all
