#!/usr/bin/env bash
# Update a running node in place. Safe to re-run. Backs up first, migrates the schema, rebuilds, checks.
#   ./update.sh              update to whatever is in this folder / on this branch
#   ./update.sh --no-pull    skip git pull (use when you unpacked a tarball over the folder)
set -euo pipefail

# Bash reads a script as it runs. This script pulls new code, which rewrites the file bash is reading, and
# from that point it executes from a byte offset in a different file: steps skipped, steps garbled. So on first
# entry, copy to a temp file and run from there; the copy is immune to the pull.
if [[ -z "${PLANETAI_UPDATE_COPY:-}" ]]; then
  NODE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"          # the node folder, resolved BEFORE we leave it
  tmp="$(mktemp -t planetai-update.XXXXXX)"; cp "${BASH_SOURCE[0]}" "$tmp"
  PLANETAI_UPDATE_COPY="$NODE_DIR" exec bash "$tmp" "$@"
fi
COPY="${BASH_SOURCE[0]}"; trap 'rm -f "$COPY"' EXIT   # the temp copy, by name: an EXIT trap that reads BASH_SOURCE while a sourced file is on the stack deletes THAT file (v0.30 deleted .env)
cd "$PLANETAI_UPDATE_COPY"                 # back into the node folder; the copy lives in /tmp

say()  { printf '\033[1;32m>>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
ULOG="${ULOG:-$PWD/.planetai-update.log}"; : > "$ULOG"
# spin "label" cmd...  the long steps, with a spinner and elapsed time; output in $ULOG. Same shape as the CLI's.
spin() {
  local label="$1"; shift; local t0=$SECONDS rc=0
  if [[ ! -t 1 ]]; then "$@" >>"$ULOG" 2>&1 || rc=$?; [[ $rc -eq 0 ]] && printf '   ✓ %s (%ds)\n' "$label" $((SECONDS-t0)) || { printf '   ✗ %s\n' "$label"; tail -8 "$ULOG" | sed 's/^/      /'; }; return $rc; fi
  "$@" >>"$ULOG" 2>&1 & local pid=$! i=0 frames='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
  tput civis 2>/dev/null || true
  while kill -0 "$pid" 2>/dev/null; do printf '\r   \033[34m%s\033[0m %s \033[2m%ds\033[0m\033[K' "${frames:$((i%10)):1}" "$label" $((SECONDS-t0)); i=$((i+1)); sleep 0.1; done
  wait "$pid" || rc=$?; tput cnorm 2>/dev/null || true
  if [[ $rc -eq 0 ]]; then printf '\r   \033[32m✓\033[0m %s \033[2m%ds\033[0m\033[K\n' "$label" $((SECONDS-t0)); else printf '\r   \033[31m✗\033[0m %s\033[K\n' "$label"; tail -8 "$ULOG" | sed 's/^/      /'; fi
  return $rc
}

# Where the three files come from. The site serves them under /get; a GitHub Release serves them flat,
# at .../releases/download/<tag>/, because a release asset name cannot contain a slash. One variable, so
# this reads either without a second code path — see docs/UPDATING.md.
SITE="${PLANETAI_SITE:-https://planetai.fab.city/node0}"
GET="${PLANETAI_GET:-$SITE/get}"

# The signer this node trusts, as one line of ssh-keygen's allowed_signers format. A heredoc and not a
# file: this runs before there is a node to read a file from, and reading it out of the tarball would be
# asking the download to vouch for itself. `tools/allowed_signers` carries the same line, and
# tests/test_release_consistency.sh fails if the copies drift.
read -r -d '' ALLOWED_SIGNERS <<'SIGNERS' || true
fabcity ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINbgbaRosyOEVk7c4iBHc5iXn9H7F1s9QGwhXBGt+qay fabcity
SIGNERS

# Who built this tarball — which the checksum does not answer. SHA256 is served from the same origin as
# the tarball, so whoever can write one writes the other and the two agree: it catches a download that
# arrived corrupted, and nothing else. Every node takes what that origin serves on its next update.
# This is the half that names the sender, with a key that is not on the web server.
verify_signature() {
  local tgz="$1" d; d="$(dirname "$tgz")"
  if [[ "${PLANETAI_UNSIGNED:-0}" == 1 ]]; then
    printf '\033[1;31m!! PLANETAI_UNSIGNED=1 — installing a tarball nobody signed. Not for a node you rely on.\033[0m\n' >&2
    return 0
  fi
  command -v ssh-keygen >/dev/null || { rm -rf "$d"; die "no ssh-keygen on this machine, so it cannot be checked who built this download.
   Debian/Ubuntu:  sudo apt-get install -y openssh-client
   Arch:           sudo pacman -S openssh
   Then run the same line again. (macOS already has it.)"; }
  curl -fsSL "${GET}/planetai-node.tar.gz.sig" -o "$d/n.sig" \
    || { rm -rf "$d"; die "could not fetch ${GET}/planetai-node.tar.gz.sig, so it is not known who built this download. Nothing was installed."; }
  printf '%s\n' "$ALLOWED_SIGNERS" > "$d/allowed_signers"
  # -n planetai-node is the namespace: a valid signature made for anything else does not verify here.
  ssh-keygen -Y verify -f "$d/allowed_signers" -I fabcity -n planetai-node \
    -s "$d/n.sig" < "$tgz" >/dev/null 2>&1 \
    || { rm -rf "$d"; die "this download is not signed by the PLANETAI release key. Nothing was installed and nothing on this machine changed.
   Try again on a network you trust. If it says this twice, do not run it — tell us instead."; }
  say "signature verified"
}

# A wild pack is one `planetai packs add` fetched: packs/<id>/.wild says where from. If the version arriving ships a
# core pack with the same id (a wild pack promoted into the release, docs/decisions/2026-10-01-packs.md), the two
# collide. The tarball would unpack the core files over the wild copy and leave a folder that is neither; git refuses
# the pull and blames untracked files. So look first, and stop before anything moves, saying which folder to remove.
# The check is a command that succeeds when the arriving version has packs/<id>/pack.yaml; the id goes last.
core_in_dir() { [[ -f "$1/packs/$2/pack.yaml" ]]; }
core_in_ref() { git cat-file -e "$1:packs/$2/pack.yaml" 2>/dev/null; }
wild_collisions() {
  local f id hits=""
  for f in packs/*/.wild; do
    [[ -f "$f" ]] || continue
    id="$(basename "$(dirname "$f")")"
    if "$@" "$id"; then hits="$hits $id"; fi
  done
  [[ -n "$hits" ]] || return 0
  printf '\033[1;31mxx this version ships a core pack with the same name as a wild pack on this node:\033[0m\n' >&2
  for id in $hits; do
    printf '   packs/%s came from %s (commit %s) by planetai packs add\n' "$id" \
      "$(sed -n 's/^source=//p' "packs/$id/.wild" | head -1)" "$(sed -n 's/^commit=//p' "packs/$id/.wild" | head -1 | cut -c1-12)" >&2
  done
  printf '   Nothing was updated. Remove the wild copy, then run this again, and the core pack takes its place:\n' >&2
  for id in $hits; do printf '     rm -rf packs/%s\n' "$id" >&2; done
  printf '   Its settings in .env stay where they are.\n' >&2
  return 1
}

[[ -f .env ]] || die "no .env here — is this a node folder?"
# A space after `=` breaks the value docker compose reads. Name the line rather than fail later.
bad="$(grep -nE '^[A-Z_]+=[[:space:]]+[^[:space:]#]' .env || true)"
if [[ -n "$bad" ]]; then
  printf '\033[1;31mxx .env has a space after `=`:\033[0m\n' >&2
  printf '   %s\n' "$bad" >&2
  printf '   Remove the spaces so it reads NAME=value, then run this again.\n' >&2
  exit 1
fi
# .env is read key by key, never sourced: a value with spaces or `$(...)` (a pack's env: line, a sentence the
# wizard once wrote into NODE_KIND) would run as a command on the host.
# nodes installed before v0.14 have no admin token; the GUI needs one to change settings
rand_hex() { openssl rand -hex 16 2>/dev/null || head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
# judge the VALUE, not the line: a line like `ADMIN_TOKEN=   # comment` has text after = and no value
envval() { { grep -E "^$1=" .env || true; } | tail -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d '" '; }
APP_PORT="$(envval APP_PORT)"; BACKUP_DIR="$(envval BACKUP_DIR)"
if [[ -z "$(envval BACKUP_TOKEN)" ]]; then
  tok="$(rand_hex)"; [[ -n "$tok" ]] && { grep -q "^BACKUP_TOKEN=" .env && sed -i.bak "s|^BACKUP_TOKEN=.*|BACKUP_TOKEN=${tok}|" .env && rm -f .env.bak || echo "BACKUP_TOKEN=${tok}" >> .env; echo "   + BACKUP_TOKEN (read-only, for a NAS that collects backups)"; }
fi
if [[ -z "$(envval ADMIN_TOKEN)" ]]; then
  tok="$(rand_hex)"; [[ -n "$tok" ]] || die "could not generate a random token (no openssl, no /dev/urandom?)"
  if grep -q "^ADMIN_TOKEN=" .env; then sed -i.bak "s|^ADMIN_TOKEN=.*|ADMIN_TOKEN=${tok}|" .env && rm -f .env.bak; else echo "ADMIN_TOKEN=${tok}" >> .env; fi
  echo "   + ADMIN_TOKEN (for the GUI; planetai ui shows it)"
fi
PORT="${APP_PORT:-8080}"
PULL=1; [[ "${1:-}" == "--no-pull" ]] && PULL=0

# 1. back up before touching anything. If this fails, stop.
say "backing up the database first"
./backup.sh || die "backup failed — not updating. Fix the backup, then re-run."

FROM="$(docker compose exec -T db psql -U planetai -tAc "SELECT version FROM schema_version ORDER BY applied_at DESC, string_to_array(version,'.')::int[] DESC LIMIT 1" planetai 2>/dev/null || echo "pre-0.4")"
say "current schema: ${FROM}"

# 2. keep local edits from being silently clobbered
for f in config/rules.yml .env; do
  [[ -f "$f" ]] && cp -p "$f" "$f.before-update"     # -p: .env is 600; the copy must not be world-readable
done

# 3. get the new code
if [[ $PULL -eq 1 ]] && [[ ! -d .git ]] && [[ -f VERSION ]]; then
  # installed from the tarball (no repository access): fetch the current one and unpack over this folder
  say "updating from ${GET}"
  tmp="$(mktemp -d)"
  if curl -fsSL "${GET}/planetai-node.tar.gz" -o "$tmp/n.tar.gz"; then
    # The checksum is not optional — the same five lines the installer uses (`install`, fetch_tarball).
    # This said `if command -v shasum && curl …SHA256`, which failed open twice and silently: `shasum` is
    # macOS's name and Debian ships `sha256sum`, and any hiccup fetching the checksum skipped the check
    # too. Then `tar xzf` was the LEFT operand of an `&&` list, which `set -e` exempts, so a truncated
    # download extracted nothing and the script carried on to the schema step, the rebuild and the doctor
    # and exited 0 with six green rows and no new code installed. On a node nobody here can see, an update
    # that reports success it did not have is worse than one that fails.
    sum=""; command -v shasum >/dev/null && sum="shasum -a 256"; [[ -n "$sum" ]] || { command -v sha256sum >/dev/null && sum="sha256sum"; }
    [[ -n "$sum" ]] || { rm -rf "$tmp"; die "no shasum or sha256sum on this machine, so the download cannot be verified. Install one, then run this again."; }
    curl -fsSL "${GET}/SHA256" -o "$tmp/sha" || { rm -rf "$tmp"; die "could not fetch the published checksum, so the download cannot be verified."; }
    want="$(tr -d '[:space:]' < "$tmp/sha")"; got="$($sum "$tmp/n.tar.gz" | awk '{print $1}')"
    [[ "$want" == "$got" ]] || { rm -rf "$tmp"; die "the download does not match its published checksum. Try again; if it repeats, tell us."; }
    say "checksum verified"
    # Before the extract, which is the first thing here that touches the node. A node that cannot say who
    # built a download does not install it — the backup in step 1 is already taken and nothing else moved.
    verify_signature "$tmp/n.tar.gz"
    tar xzf "$tmp/n.tar.gz" -C "$tmp" || { rm -rf "$tmp"; die "the download is not a readable archive, so nothing was installed. Try again; if it repeats, tell us."; }
    wild_collisions core_in_dir "$tmp/planetai-node" || { rm -rf "$tmp"; exit 1; }
    ( cd "$tmp/planetai-node" && tar cf - . ) | tar xf - --exclude=.env
    # What `planetai doctor` reads months from now: whether the code this node is running was signed by
    # the key it publishes. A node that cannot answer that has to be asked, and nobody asks.
    printf '%s %s\n' "$([[ "${PLANETAI_UNSIGNED:-0}" == 1 ]] && echo unsigned || echo signed)" \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > .planetai-release
    say "now $(cat VERSION 2>/dev/null || echo '?')"
  else
    warn "could not reach the site; keeping the version you have"
  fi
  rm -rf "$tmp"
elif [[ $PULL -eq 1 ]] && [[ -d .git ]]; then
  say "pulling"
  # name the remote and branch explicitly: a clone repaired by hand may have no upstream set
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
  git branch --set-upstream-to="origin/$branch" "$branch" >/dev/null 2>&1 || true
  git fetch -q --tags origin 2>/dev/null || true      # pulling a named branch skips tags; version stamps need them
  find . -name .DS_Store -not -path './.git/*' -delete 2>/dev/null || true    # Finder litter blocks a pull if the repo ever had it
  # the fetch above may have failed quietly; then origin/$branch is what was fetched last, and the pull says so
  if git rev-parse -q --verify "origin/$branch" >/dev/null; then wild_collisions core_in_ref "origin/$branch" || exit 1; fi
  before="$(git rev-parse HEAD)"
  if ! spin "fetching the current version" git pull --ff-only origin "$branch"; then
    # The keeper's question is WHICH changes block the pull — name them, git's own error does not.
    # And name local commits too: with pull.rebase set, a clone carrying junk commits ("o", "www")
    # rebases them onto every update instead of refusing, and the dirt never surfaces.
    dirty="$(git status --short 2>/dev/null | head -10)"
    ahead="$(git log --oneline "origin/$branch..HEAD" 2>/dev/null | head -5)"
    [[ -n "$dirty" ]] && warn "git pull failed — these files have uncommitted changes:"$'\n'"$dirty"
    [[ -n "$ahead" ]] && warn "and these commits exist only here, not on origin/$branch:"$'\n'"$ahead"
    [[ -z "$dirty$ahead" ]] && warn "git pull failed; the lines above are git's reason."
    warn "Commit, stash or remove them and run this again. If they are the node's own operational files (.planetai-*, .env.before-*): they are in .gitignore now — untrack them, never commit them."
    exit 1
  fi
  if [[ "$(git rev-parse HEAD)" == "$before" ]]; then
    # Nothing moved. Either there is genuinely nothing new, or a release is on the channel but its
    # commit has not landed on this branch yet — from "updated" silence the keeper cannot tell the
    # two apart (node #1 ran three no-op updates in a day chasing a release that was still shipping).
    # Ask the channel and say which one it is.
    here="$(git describe --tags --always 2>/dev/null || echo '?')"
    latest="$(curl -fsSL -m 10 "${GET}/VERSION" 2>/dev/null || true)"
    if [[ -z "$latest" ]]; then
      say "already at the newest commit on $branch ($here); the channel could not be asked, so a newer release could be out there"
    elif git rev-parse -q --verify "$latest" >/dev/null 2>&1 && ! git merge-base --is-ancestor "$latest" HEAD 2>/dev/null; then
      warn "already at the newest commit on $branch ($here), but the channel serves $latest, which has not landed on this branch yet — it is still shipping; try again shortly"
    else
      say "already at the newest commit on $branch ($here)"
    fi
  fi
fi

# 4. apply the schema to the EXISTING database. init.sql only runs on a fresh volume; this is the other half.
say "applying schema (idempotent)"
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U planetai planetai < init.sql >/dev/null \
  || die "schema failed to apply — your data is untouched and the backup is in ${BACKUP_DIR:-./backups}"

# 5. new settings keys, without overwriting anything you set
say "checking .env for new settings"
NEW=0; HDR=0
while IFS= read -r line; do
  k="${line%%=*}"
  [[ "$k" =~ ^[A-Z_]+$ ]] || continue
  if ! grep -q "^${k}=" .env; then
    # new keys go under their own dated marker, not silently under whatever heading happens to be last
    [[ $HDR -eq 0 ]] && { printf '\n# ---- added by update on %s (see .env.example for what each does) ----\n' "$(date +%F)" >> .env; HDR=1; }
    echo "$line" >> .env; echo "   + ${k}"; NEW=$((NEW+1))
  fi
done < .env.example
[[ $NEW -eq 0 ]] && echo "   nothing new" || warn "${NEW} new setting(s) added with defaults — review .env"

# 6. rebuild and restart
say "rebuilding"
spin "building the image (pip installs; a minute or two)" docker compose build app || die "the image did not build; the node keeps running the version it had. See $ULOG"
# stamp the version the node now runs, so /health and planetai status report it: from git in a clone, from the
# VERSION file the tarball carries otherwise. After the build, not
# before: a failed build must not leave .env claiming a version the containers never ran.
VER="$(git describe --tags --always 2>/dev/null || cat VERSION 2>/dev/null || echo dev)"
if grep -q "^NODE_VERSION=" .env; then sed -i.bak "s|^NODE_VERSION=.*|NODE_VERSION=${VER}|" .env && rm -f .env.bak; else echo "NODE_VERSION=${VER}" >> .env; fi
spin "restarting the containers" docker compose up -d || die "the containers did not start; see $ULOG"

# 7. verify
sleep 8
TO="$(docker compose exec -T db psql -U planetai -tAc "SELECT version FROM schema_version ORDER BY applied_at DESC, string_to_array(version,'.')::int[] DESC LIMIT 1" planetai 2>/dev/null || echo "?")"
ok=1
chk(){ if eval "$2" >/dev/null 2>&1; then echo "  ✓ $1"; else echo "  ✗ $1"; ok=0; fi; }
echo "doctor:"
chk "all modules in image" "[ \"\$(ls app/*.py | wc -l)\" -eq \"\$(docker compose exec -T app sh -c 'ls /app/*.py | wc -l')\" ]"
chk "db healthy"        "docker compose exec -T db pg_isready -U planetai"
chk "app answering"     "curl -sf localhost:${PORT}/health"
chk "readings intact"   "[ \$(docker compose exec -T db psql -U planetai -tAc 'SELECT count(*) FROM readings' planetai) -gt 0 ]"
# The doctor asks the node's own API over the published port, so the container sees the Docker bridge gateway
# rather than loopback — a LAN client, as far as SHARE_LEVEL is concerned. At the v0.43 default (`off`) an
# unauthenticated /stats and /packs are refused, and an update on a node that was working perfectly ended
# "xx something is off" with two red ticks. The node's own maintenance carries the node's own token.
# /health needs none: it is on every level's allowlist, which is why "app answering" stayed green and hid this.
AUTH="$(envval ADMIN_TOKEN)"; AUTH="${AUTH:+-H \"Authorization: Bearer ${AUTH}\"}"
chk "views rebuilt"     "curl -sf $AUTH localhost:${PORT}/stats"
chk "packs loaded"      "curl -sf $AUTH localhost:${PORT}/packs"
echo
if grep -qE 'api\.telegram\.org/bot[0-9]+:' <<< "$(docker compose logs app 2>/dev/null)"; then
  warn "a Telegram bot token is visible in this node's container logs (logged by versions before v0.4.3)."
  warn "Revoke it via @BotFather /revoke, update .env, then: docker compose down && docker compose up -d"
fi
say "schema ${FROM} → ${TO}"
# An update can bring a new code pack, or new libraries for one already here. It does not install them:
# app/requirements-packs.txt is gitignored and only `planetai packs install` writes it. Node #1 updated into
# v0.33, ran `planetai run earth fetch` and got ModuleNotFoundError nine times (7 Sep 2026). Say it here, once,
# rather than leaving it to be discovered. `planetai packs` owns the decision; this only relays it.
if grep -q "planetai packs install" <<< "$(./bin/planetai packs 2>/dev/null)"; then
  warn "a pack here declares Python libraries or settings this image does not have yet."
  warn "Run:  planetai packs install     (a rebuild, a few minutes)  then  planetai restart"
fi
if [[ -f config/rules.yml.before-update ]] && ! diff -q config/rules.yml config/rules.yml.before-update >/dev/null 2>&1; then
  warn "config/rules.yml changed in this update. Your previous copy: config/rules.yml.before-update"
  warn "If you had edited thresholds, re-apply them — or better, move them into a pack (docs/PACKS.md)."
fi
[[ $ok -eq 1 ]] || die "something is off: docker compose logs app | tail -40"
say "updated. Nothing was lost: $(docker compose exec -T db psql -U planetai -tAc 'SELECT count(*) FROM readings' planetai | tr -d ' ') readings, $(docker compose exec -T db psql -U planetai -tAc 'SELECT count(*) FROM alerts' planetai | tr -d ' ') alerts, $(docker compose exec -T db psql -U planetai -tAc 'SELECT count(*) FROM actions' planetai | tr -d ' ') actions."
