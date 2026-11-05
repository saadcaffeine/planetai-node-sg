"""Offline sanity checks on init.sql and the Dockerfile. Not a Postgres parser — it catches the specific mistakes that have
actually bitten us: unbalanced parens (a comment inside an expression), and non-idempotent statements
(which break updating a running node, because init.sql is applied to live databases)."""
import re
import sys

sql = open("init.sql").read()
errs = []

for stmt in [s.strip() for s in sql.split(";") if s.strip()]:
    code = re.sub(r"--.*$", "", stmt, flags=re.M)
    if code.count("(") != code.count(")"):
        errs.append(f"unbalanced parens (a comment inside an expression?): {stmt.splitlines()[0][:80]}")
    head = " ".join(code.split()[:3]).upper()
    up = code.upper()
    if head.startswith("CREATE TABLE") and "IF NOT EXISTS" not in up:
        errs.append(f"not idempotent: {head}")
    if head.startswith(("ALTER TABLE", "CREATE INDEX")) and "IF NOT EXISTS" not in up:
        # ADD CONSTRAINT has no IF NOT EXISTS in Postgres; it is idempotent when the same constraint is dropped
        # with IF EXISTS just before. DROP ... IF EXISTS is idempotent on its own — which the comment has said
        # since it was written, though only the CONSTRAINT spelling was ever matched. DROP COLUMN IF EXISTS is
        # the same guarantee and was reported as non-idempotent until v0.51 needed one.
        if re.search(r"DROP (CONSTRAINT|COLUMN) IF EXISTS", up):
            pass
        elif "ADD CONSTRAINT" in up:
            name = re.search(r"ADD CONSTRAINT\s+(\w+)", up)
            if not (name and re.search(rf"DROP CONSTRAINT IF EXISTS\s+{name.group(1)}", sql.upper())):
                errs.append(f"not idempotent: {head} (ADD CONSTRAINT needs a matching DROP CONSTRAINT IF EXISTS first)")
        else:
            errs.append(f"not idempotent: {head}")
    if head.startswith("CREATE VIEW"):
        name = code.split()[2]
        if f"DROP VIEW IF EXISTS {name}" not in sql:
            errs.append(f"view {name} has no preceding DROP VIEW IF EXISTS (CREATE OR REPLACE cannot reorder columns)")

for line in sql.splitlines():
    if "--" in line and re.search(r"\([^)]*--", line):
        errs.append(f"comment inside parentheses: {line.strip()[:80]}")

# the Dockerfile must not enumerate modules: a list goes stale the moment a module is added
dockerfile = open("app/Dockerfile").read()
for line in dockerfile.splitlines():
    if line.startswith("COPY") and line.endswith(("./", "/app/")) and ".py" in line and "*.py" not in line:
        errs.append(f"app/Dockerfile enumerates modules — use COPY *.py ./ : {line.strip()}")

# every bind mount in docker-compose.yml must point at something the repo ships. Docker creates a missing
# source as an EMPTY directory without complaint, so a forgotten config file becomes a container running
# with no config at all (this happened with mosquitto in v0.8).
import subprocess
compose = open("docker-compose.yml").read()
tracked = set(subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split())
# config/reticulum: `planetai reticulum` copies the bridge's config.tpl there before it adds the profile
runtime_created = {"config/mosquitto/passwd", "config/reticulum", "config/ee-key.json", "app/requirements-packs.txt"}
for m in re.finditer(r"^\s*-\s*\./([^:\s]+):", compose, re.M):
    src = m.group(1).rstrip("/")
    if src in runtime_created or src.startswith(("backups", "packs", "out", "exports")):
        continue
    if not any(f == src or f.startswith(src + "/") for f in tracked):
        errs.append(f"docker-compose.yml mounts ./{src} but the repo ships nothing there (Docker would mount an empty dir)")

# `producer | grep -q` under pipefail is a race: grep exits on the first match, the producer gets SIGPIPE, the
# pipeline "fails" on good input. It made a valid dump read as "no readings table" (5 Sep). Capture first, then grep.
for f in ("backup.sh", "update.sh", "install.sh", "bin/planetai"):
    s = open(f).read()
    if "pipefail" in s:
        for i, line in enumerate(s.splitlines(), 1):
            if re.search(r"\|\s*grep\s+-[a-zA-Z]*q", line) and "<<<" not in line:
                errs.append(f"{f}:{i}: `| grep -q` under pipefail races on large output; use grep -q ... <<< \"$(producer)\"")

# a logged exception from a Telegram call prints the bot token (httpx puts it in the URL). Log its type, never its text.
for f in ("app/main.py", "app/agent_loop.py"):
    s = open(f).read()
    for i, line in enumerate(s.splitlines(), 1):
        if "log.warning" in line and "telegram" in line.lower() and re.search(r'%s", *e\)|\{e\}', line):
            errs.append(f"{f}:{i}: logs a telegram exception's text; use type(e).__name__ (the URL holds the bot token)")

# nothing tracked may be OS litter or a cache: .DS_Store committed once and blocked planetai update on the node
tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
for f in tracked:
    if f.endswith((".DS_Store", ".pyc")) or "__pycache__" in f or f.endswith("~"):
        errs.append(f"{f} is tracked; it is OS or editor litter")

print("\n".join(f"  x {e}" for e in errs) or "  init.sql + Dockerfile + compose mounts + no litter ok")
sys.exit(1 if errs else 0)
