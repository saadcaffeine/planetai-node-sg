#!/usr/bin/env bash
# `planetai remove` deletes readings nobody else has a copy of. The only thing worth testing about it is
# that it CANNOT do that by accident: it lists first, asks twice, and the second answer must be the
# node's own name typed out.
#
# Run against a throwaway node folder — never a real one, and never with a container runtime reachable.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"; fails=0
ok(){ echo "  ok   $1"; }; bad(){ echo "  FAIL $1"; fails=$((fails+1)); }

# A fake node: the files cmd_remove looks at, and nothing else.
mk() {
  D="$(mktemp -d)/planetai"; mkdir -p "$D/backups" "$D/bin"
  printf 'NODE_NAME=mahon1\nAPP_PORT=8080\n' > "$D/.env"
  printf 'v0.0.0-test\n' > "$D/VERSION"
  cp "$REPO/bin/planetai" "$D/bin/planetai"
  : > "$D/backups/old.sql.gz"
  # no docker on PATH: the same shape as the machine this matters on
  STUB="$(mktemp -d)"; printf '#!/bin/sh\nexit 1\n' > "$STUB/docker"; chmod +x "$STUB/docker"
}

# On a real terminal, because planetai reads every answer from /dev/tty — a pipe drives nothing.
run() { PATH="$STUB:/usr/bin:/bin:/usr/local/bin" PLANETAI_HOME="$D" \
        python3 "$REPO/tests/pty_run.py" "$@" -- bash "$D/bin/planetai" remove 2>&1; }

echo "remove: it cannot happen by accident"

mk; out="$(run n)"
if [[ -d "$D" ]]; then ok "answering no to the first question leaves the folder"; else bad "the folder went on a 'no'"; fi
grep -q "nothing was removed" <<<"$out" && ok "and says so" || bad "no confirmation that nothing happened"

mk; out="$(run y not-the-name)"
if [[ -d "$D" ]]; then ok "a wrong name leaves the folder"; else bad "the folder went on a wrong name"; fi
grep -q 'that is not "mahon1"' <<<"$out" && ok "and names what it wanted" || bad "no message about the wrong name"

mk; out="$(run y mahon1)"
if [[ -d "$D" ]]; then bad "the right name did NOT remove the folder"; else ok "the node's own name, typed out, removes it"; fi

echo "remove: it says what will go, before it goes"
mk; out="$(run n)"
for want in "This will remove" "$D" "readings" "backup(s)"; do
  grep -q -- "$want" <<<"$out" && ok "  lists: $want" || bad "  does not list: $want"
done
grep -q "Copy them out first" <<<"$out" && ok "  and warns the backups go with the folder" || bad "  no warning about the backups"

echo "remove: --keep-data"
mk; out="$(PATH="$STUB:/usr/bin:/bin:/usr/local/bin" PLANETAI_HOME="$D" \
      python3 "$REPO/tests/pty_run.py" n -- bash "$D/bin/planetai" remove --keep-data 2>&1)"
grep -q "kept" <<<"$out" && ok "  says the data is kept" || bad "  does not say the data is kept"
grep -q "deleted" <<<"$out" && bad "  still threatens to delete the readings" || ok "  and does not threaten the readings"

echo "remove: no terminal, no deletion"
# ---------------------------------------------------------------------------------------------------
# The shape a tester with a broken node actually uses: `curl … /remove | bash`. stdin is the pipe, the
# terminal is still right there, and the answers are read from /dev/tty. This used to print the whole
# list of what it would remove and then refuse — "no terminal here, so nothing was removed" — because
# the guard tested stdin instead of /dev/tty. It never removed anything for anybody who piped it.
echo "remove: piped in, with a terminal still attached"
mk
out="$(PATH="$STUB:/usr/bin:/bin:/usr/local/bin" PLANETAI_HOME="$D" \
       python3 "$REPO/tests/pty_run.py" y mahon1 -- \
       bash -c "printf '' | bash '$D/bin/planetai' remove" 2>&1)"
grep -q "no terminal here" <<<"$out" && bad "  still refuses when piped" || ok "  does not refuse for lack of a terminal"
if [[ -d "$D" ]]; then bad "  piped, it did not remove the folder"; else ok "  and removes the node"; fi

# ---------------------------------------------------------------------------------------------------
# With docker unreachable, `docker compose down -v` never runs. It used to delete the folder anyway and
# then print "gone. Nothing of this node is left on the machine" — while four named volumes stayed, with
# no compose file left anywhere to name them. A fresh install into the same folder then re-attached the
# db volume and came up carrying the old node's readings and name. That is what happened to a tester.
echo "remove: with docker down it does not pretend, and it hands over the names"
mk; out="$(run y mahon1)"
grep -q "docker is not running" <<<"$out" && ok "  says docker is not running" || bad "  silent about the daemon"
for v in db mosquitto reticulum ipfsdata; do
  grep -q "docker volume rm planetai_$v" <<<"$out" \
    && ok "  gives the command for planetai_$v" || bad "  no way to delete planetai_$v later"
done
grep -q "no containers, no volumes, no folder" <<<"$out" \
  && bad "  claims a clean machine it never checked" || ok "  and does not claim it is all gone"
grep -q "re-attaches a leftover volume" <<<"$out" \
  && ok "  and says why that matters for the next install" || bad "  does not say what the leftover does"

# ---------------------------------------------------------------------------------------------------
# The same thing against real docker, which is the only way to know the volumes actually go. Its own
# project name, never "planetai", so this can never reach a node somebody is running.
if docker info >/dev/null 2>&1; then
  echo "remove: against real docker, every volume it named is gone afterwards"
  PJ="pairm$$"
  RD="$(mktemp -d)/$PJ"; mkdir -p "$RD/bin"
  printf 'NODE_NAME=rmtest\nAPP_PORT=8099\n' > "$RD/.env"; printf 'v0.0.0-test\n' > "$RD/VERSION"
  cp bin/planetai "$RD/bin/planetai"
  cat > "$RD/docker-compose.yml" <<'YML'
services:
  db:
    image: alpine:3
    command: sleep 300
    volumes: [ "db:/a", "mosquitto:/b", "reticulum:/c", "ipfsdata:/d" ]
volumes:
  db: {}
  mosquitto: {}
  reticulum: {}
  ipfsdata: {}
YML
  ( cd "$RD" && docker compose up -d >/dev/null 2>&1 )
  before="$(docker volume ls -q | grep -cE "^${PJ}_(db|mosquitto|reticulum|ipfsdata)$" || true)"
  [[ "$before" == 4 ]] && ok "  four volumes exist to start with" || bad "  fixture made $before volumes, wanted 4"
  PLANETAI_HOME="$RD" python3 "$REPO/tests/pty_run.py" y rmtest -- bash "$RD/bin/planetai" remove >/tmp/rm-real.txt 2>&1
  after="$(docker volume ls -q | grep -cE "^${PJ}_(db|mosquitto|reticulum|ipfsdata)$" || true)"
  [[ "$after" == 0 ]] && ok "  and none of them are left" || bad "  $after volume(s) survived remove"
  cn="$(docker ps -aq --filter "label=com.docker.compose.project=$PJ" 2>/dev/null | wc -l | tr -d ' ')"
  [[ "$cn" == 0 ]] && ok "  no containers left" || bad "  $cn container(s) left"
  [[ ! -d "$RD" ]] && ok "  the folder is gone" || bad "  the folder is still there"
  grep -q "no containers, no volumes, no folder" /tmp/rm-real.txt \
    && ok "  and it says so only because it checked" || bad "  did not report a verified clean removal"
  # never leave the fixture behind, whatever happened above
  ( cd "$RD" 2>/dev/null && docker compose down -v >/dev/null 2>&1 ) || true
  docker volume ls -q | grep -E "^${PJ}_" | xargs -r docker volume rm >/dev/null 2>&1 || true
  rm -rf "$RD"
else
  echo "  --   real-docker removal not checked (no reachable daemon)"
fi

# No terminal at all, not just no stdin: `planetai remove` reads its answer from /dev/tty, so `</dev/null` alone
# still finds the terminal of whoever ran the suite. Run from a terminal (release.sh's `make test`, 6 Oct 2026)
# this waited, invisibly, for a node name. A new session has no controlling terminal, so /dev/tty cannot open,
# which is the case this checks, the same in a terminal, the pre-commit hook and CI.
mk; out="$(PATH="$STUB:/usr/bin:/bin" PLANETAI_HOME="$D" python3 -c 'import subprocess, sys
sys.exit(subprocess.call(sys.argv[1:], stdin=subprocess.DEVNULL, start_new_session=True))' \
      bash "$D/bin/planetai" remove 2>&1)"
if [[ -d "$D" ]]; then ok "with nothing to answer it, the folder stays"; else bad "it deleted with no terminal"; fi

[[ $fails -eq 0 ]] && { echo "remove tests pass"; exit 0; } || { echo "$fails failed"; exit 1; }
