#!/usr/bin/env bash
# `planetai packs add`, run for real against a throwaway node folder. curl and docker are stubs on PATH: curl
# serves a wild list, GitHub's commit lookups and real tar.gz archives built here from fixture folders, shaped the
# way codeload.github.com shapes them (one top folder, <repo>-<commit>). So the test is offline, and what is under
# test is the command: pinning, the folder it extracts, the ids it refuses, the marker it writes, and the listing.
set -uo pipefail
cd "$(dirname "$0")/.."
fails=0
ok()  { echo "  ok   $*"; }
bad() { echo "  FAIL $*"; fails=$((fails + 1)); }
d="$(mktemp -d)"; trap 'rm -rf "$d"' EXIT

S1=1111111111111111111111111111111111111111   # someone/rain at HEAD
S1B=1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b1b  # someone/rain, a later commit
S2=2222222222222222222222222222222222222222   # fabcity/planetai-wild-packs at HEAD
S3=3333333333333333333333333333333333333333   # the other fixtures

# ---------------------------------------------------------------- fixtures: archives the way GitHub builds them
mk() { # mk <repo> <sha> <path-inside-repo> <id>  -> a pack folder; the caller adds files
  local p="$d/src/$1-$2${3:+/$3}"; mkdir -p "$p"
  printf 'id: %s\nname: %s\ndescription: a test pack\n' "$4" "$4" > "$p/pack.yaml"; echo "$p"
}
p="$(mk rain "$S1" "" rain-gauge)"; echo "def fetch(hc): return [], []" > "$p/adapter.py"; echo v1 > "$p/README.md"
printf 'env:\n  - "# rain-gauge: where the gauge answers"\n  - "RAIN_URL="\n' >> "$p/pack.yaml"
p="$(mk rain "$S1B" "" rain-gauge)"; echo "def fetch(hc): return [], []" > "$p/adapter.py"; echo v2 > "$p/README.md"
p="$(mk planetai-wild-packs "$S2" packs/tide tide)"; echo "[]" > "$p/rules.yml"
mk planetai-wild-packs "$S2" packs/other other >/dev/null                        # a neighbour that must not come along
mk liar "$S3" "" not-liar >/dev/null                                              # the list says liar, the pack says not-liar
mk heatclone "$S3" "" heat >/dev/null                                             # wants to replace a core pack
mk underscored "$S3" "" under_score >/dev/null
p="$(mk links "$S3" "" links)"; ln -s /etc/hosts "$p/rules.yml"
mkdir -p "$d/src/nopack-$S3"; echo "just a readme" > "$d/src/nopack-$S3/README.md"
p="$(mk future "$S3" "" future)"; printf 'requires: { node: ">=99.0.0" }\n' >> "$p/pack.yaml"             # written for a node far ahead
p="$(mk blockfuture "$S3" "" block-future)"; printf 'requires:\n  node: ">=99.0.0"\n' >> "$p/pack.yaml"  # the same, block form
p="$(mk synop "$S3" "" synop)"; echo "def fetch(hc): return [], []" > "$p/adapter.py"                  # deps and a setting, like bmkg-synop
printf 'pip:\n  - pybufrkit\n  - bitstring\nenv:\n  - "SYNOP_STATION="\n' >> "$p/pack.yaml"
# for `packs pending`: listed packs hosted in the wild repository, one of them with libraries to build
mk planetai-wild-packs "$S2" packs/ebb ebb >/dev/null
mk planetai-wild-packs "$S2" packs/flow flow >/dev/null
p="$(mk planetai-wild-packs "$S2" packs/deps deps)"; echo "def fetch(hc): return [], []" > "$p/adapter.py"; printf 'pip:\n  - cowsay\n' >> "$p/pack.yaml"
mkdir -p "$d/tgz"
for top in "$d"/src/*; do n="$(basename "$top")"; tar czf "$d/tgz/$n.tgz" -C "$d/src" "$n"; done

cat > "$d/packs.json" <<J
[{"id": "tide", "source": "fabcity/planetai-wild-packs/packs/tide", "status": "listed"},
 {"id": "liar", "source": "someone/liar", "commit": "$S3", "status": "reviewed"},
 {"id": "ebb", "source": "fabcity/planetai-wild-packs/packs/ebb", "status": "listed"},
 {"id": "flow", "source": "fabcity/planetai-wild-packs/packs/flow", "status": "listed"},
 {"id": "deps", "source": "fabcity/planetai-wild-packs/packs/deps", "status": "listed"}]
J

# ---------------------------------------------------------------- the stubs
mkdir -p "$d/bin"
cat > "$d/bin/curl" <<STUB
#!/bin/bash
out=""; url=""; body=""
while [ \$# -gt 0 ]; do case "\$1" in -o) out="\$2"; shift 2;; -d) body="\$2"; shift 2;; -H|-w|-X) shift 2;; -*) shift;; *) url="\$1"; shift;; esac; done
echo "\$url" >> "$d/curl.log"
case "\$url" in
  *localhost:*/settings) [ -f "$d/node-up" ] || exit 7
    if [ -n "\$body" ]; then echo "\$body" >> "$d/put.log"; printf '{}\n200'; else cat "$d/settings-api.json"; fi ;;
  *localhost:*/packs) [ -f "$d/node-up" ] && cat "$d/packs-api.json" || exit 7 ;;
  *localhost:*) exit 7 ;;
  https://raw.githubusercontent.com/fabcity/planetai-wild-packs/main/packs.json) cat "$d/packs.json" ;;
  https://api.github.com/repos/someone/rain/commits/HEAD) printf '%s' "$S1" ;;
  https://api.github.com/repos/fabcity/planetai-wild-packs/commits/HEAD) printf '%s' "$S2" ;;
  https://api.github.com/repos/someone/*/commits/HEAD) printf '%s' "$S3" ;;
  https://codeload.github.com/*/tar.gz/*)
    repo="\$(echo "\$url" | cut -d/ -f5)"; sha="\${url##*/}"; f="$d/tgz/\$repo-\$sha.tgz"
    [ -f "\$f" ] || exit 22; if [ -n "\$out" ]; then cp "\$f" "\$out"; else cat "\$f"; fi ;;
  *) exit 22 ;;
esac
STUB
printf '#!/bin/sh\necho "docker $*" >> "%s/docker.log"\n[ "$2" = build ] && [ -f "%s/build-fails" ] && exit 1\nexit 0\n' "$d" "$d" > "$d/bin/docker"
chmod +x "$d/bin/curl" "$d/bin/docker"

# ---------------------------------------------------------------- a node: one core pack and an .env
N="$d/node"; mkdir -p "$N/packs/heat" "$N/app"; printf 'id: heat\nname: Heat\n' > "$N/packs/heat/pack.yaml"
cp app/requires.py "$N/app/"     # the rule the CLI runs, the real file, as every node carries it
echo "core, untouched" > "$N/packs/heat/SENTINEL"; printf 'APP_PORT=1\nNODE_VERSION=v0.75.8\n' > "$N/.env"
pa() { PATH="$d/bin:$PATH" PLANETAI_HOME="$N" bash bin/planetai packs "$@" 2>&1; }

# ---------------------------------------------------------------- a whole repository, at whatever HEAD is now
out="$(pa add someone/rain)"; rc=$?
if [ $rc -eq 0 ] && [ -f "$N/packs/rain-gauge/pack.yaml" ] && [ -f "$N/packs/rain-gauge/adapter.py" ]; then ok "owner/repo: the repository is the pack, extracted into packs/rain-gauge"
else bad "owner/repo did not land in packs/rain-gauge (exit $rc): $out"; fi
grep -qx "source=someone/rain" "$N/packs/rain-gauge/.wild" 2>/dev/null && grep -qx "commit=$S1" "$N/packs/rain-gauge/.wild" \
  && ok "HEAD is resolved to its commit, and the commit is what .wild records" || bad ".wild does not pin $S1: $(cat "$N/packs/rain-gauge/.wild" 2>&1)"
grep -q "not on the wild list" <<< "$out" && grep -q "PACKS_ALLOW_CODE=1" <<< "$out" \
  && ok "a pack from off the list says nobody checked it, and a code pack says what turning it on means" || bad "the warnings are missing: $out"
grep -q "the node is not answering, so whether Set up limits" <<< "$out" \
  && ok "with the node down, it says the saved pack list cannot be read" || bad "no node-down warning: $out"
grep -qx "RAIN_URL=" "$N/.env" && ok "packs install ran after: the pack's setting is in .env" || bad "RAIN_URL is not in .env: $(cat "$N/.env")"
[ ! -s "$d/docker.log" ] && ok "no pip: lines, so no rebuild" || bad "docker was called with nothing to install: $(cat "$d/docker.log")"

# ---------------------------------------------------------------- by id, from the wild list, hosted as one folder there
out="$(pa add tide)"; rc=$?
if [ $rc -eq 0 ] && [ -f "$N/packs/tide/rules.yml" ] && [ ! -e "$N/packs/other" ] && [ ! -e "$N/packs/tide/packs" ]; then
  ok "an id from the list: just its folder of the wild repository, nothing beside it"
else bad "tide did not land as one folder (exit $rc): $out"; fi
grep -qx "source=fabcity/planetai-wild-packs/packs/tide" "$N/packs/tide/.wild" 2>/dev/null && grep -qx "commit=$S2" "$N/packs/tide/.wild" \
  && ok "a hosted pack with no commit in the list is pinned to the wild repository's HEAD" || bad "tide's .wild: $(cat "$N/packs/tide/.wild" 2>&1)"
grep -q "listed, not reviewed" <<< "$out" && ok "a listed pack says nobody has read it" || bad "no listed warning: $out"

# ---------------------------------------------------------------- again, at a later commit: an update
out="$(pa add "someone/rain@$S1B")"; rc=$?
if [ $rc -eq 0 ] && grep -qx v2 "$N/packs/rain-gauge/README.md" && grep -qx "commit=$S1B" "$N/packs/rain-gauge/.wild"; then
  ok "adding it again at a full commit replaces it, and says from which commit"
else bad "the update did not replace the folder (exit $rc): $out"; fi
grep -q "updated from ${S1:0:12}" <<< "$out" && ok "the update names the commit it replaced" || bad "no 'updated from': $out"
grep -q "api.github.com/repos/someone/rain/commits/$S1B" "$d/curl.log" \
  && bad "a full 40-character commit was looked up anyway" || ok "a full commit is used as given, with no lookup"

# ---------------------------------------------------------------- a pack for a newer node: added, and told at once
for spec in someone/future someone/blockfuture; do
  out="$(pa add "$spec")"; rc=$?
  [ $rc -eq 0 ] && grep -q "will not load on this node: it needs a node >=99.0.0 and this node is v0.75.8; planetai update first" <<< "$out" \
    && ok "$spec: added, and says at once it will not load here and what to do" || bad "$spec gave no requires warning (exit $rc): $out"
done

# ---------------------------------------------------------------- refused, and nothing written
expect_refused() { # expect_refused <what> <text in the refusal> <path that must not exist> -- args to packs
  local what="$1" text="$2" absent="$3"; shift 4
  local out rc; out="$(pa "$@")"; rc=$?
  if [ $rc -ne 0 ] && grep -q -- "$text" <<< "$out" && { [ -z "$absent" ] || [ ! -e "$absent" ]; }; then ok "$what"
  else bad "$what (exit $rc): $(tail -6 <<< "$out")"; fi
}
expect_refused "a core pack's id is refused, and the core pack is left alone" "never replaces it" "" -- add someone/heatclone
grep -qx "core, untouched" "$N/packs/heat/SENTINEL" && [ ! -f "$N/packs/heat/.wild" ] && ok "packs/heat is exactly as it was" || bad "packs/heat was touched"
expect_refused "an id the list and the pack disagree on is refused" "pack.yaml says 'not-liar'" "$N/packs/not-liar" -- add liar
expect_refused "an id that is not the node's folder shape is refused" "lowercase letters, digits and hyphens" "$N/packs/under_score" -- add someone/underscored
expect_refused "a pack with symbolic links is refused" "symbolic links" "$N/packs/links" -- add someone/links
expect_refused "a folder with no pack.yaml is refused" "no pack.yaml" "" -- add someone/nopack
expect_refused "an id that is not on the list is refused, and the list's ids are named" "which has deps, ebb, flow, liar, tide" "" -- add nosuch
expect_refused "a path that climbs out is refused before anything is fetched" "is not owner/repo" "" -- add someone/rain/../../etc
expect_refused "no argument says how to call it" "say which pack" "" -- add
[ -z "$(ls -A "$N/packs" | grep -vxE 'heat|rain-gauge|tide|future|block-future')" ] && ok "after every refusal, packs/ holds what was added and nothing else" \
  || bad "a refusal left something in packs/: $(ls -A "$N/packs")"

# ---------------------------------------------------------------- the listing tells core from wild
out="$(pa)"
core_at="$(grep -n "^  core:" <<< "$out" | cut -d: -f1)"; wild_at="$(grep -n "^  wild:" <<< "$out" | cut -d: -f1)"
if [ -n "$core_at" ] && [ -n "$wild_at" ] && [ "$core_at" -lt "$wild_at" ] \
   && sed -n "$((core_at + 1))p" <<< "$out" | grep -q "heat" \
   && sed -n "$((wild_at + 1)),\$p" <<< "$out" | grep -q "rain-gauge" && sed -n "$((wild_at + 1)),\$p" <<< "$out" | grep -q "tide"; then
  ok "packs lists core and wild under their own headings"
else bad "the listing does not separate core from wild: $out"; fi
grep -q "rain-gauge from someone/rain at ${S1B:0:12}" <<< "$out" && ok "and says where each wild pack came from, and at which commit" \
  || bad "no provenance line for rain-gauge: $out"
nl="$(sed -n '/not loaded, written for another node version:/,$p' <<< "$out")"
grep -qE "^    future +it needs a node >=99.0.0 and this node is v0.75.8" <<< "$nl" && grep -qE "^    block-future +it needs a node >=99.0.0" <<< "$nl" \
  && ! grep -qE "^    (heat|rain-gauge|tide) " <<< "$nl" \
  && ok "and lists the packs this node will not load, with why, in either form of requires:" || bad "no 'not loaded' section, or a wrong one: $out"

# ---------------------------------------------------------------- and when the node is running, from what it loaded
cat > "$d/packs-api.json" <<'J'
[{"id": "heat", "kind": "data", "description": "apparent temperature"},
 {"id": "rain-gauge", "kind": "code", "description": "a test pack"},
 {"id": "tide", "kind": "data", "description": "a test pack"}]
J
touch "$d/node-up"; out="$(pa)"; rm -f "$d/node-up"
core_at="$(grep -n "^  core:" <<< "$out" | cut -d: -f1)"; wild_at="$(grep -n "^  wild:" <<< "$out" | cut -d: -f1)"
if grep -q "loaded now" <<< "$out" && [ -n "$core_at" ] && [ -n "$wild_at" ] && [ "$core_at" -lt "$wild_at" ] \
   && sed -n "$((core_at + 1))p" <<< "$out" | grep -qE "heat +data +apparent temperature" \
   && sed -n "$((wild_at + 1)),\$p" <<< "$out" | grep -qE "rain-gauge +code"; then
  ok "with the node up, what it loaded is split into core and wild too, with kind and description"
else bad "the running-node listing does not separate core from wild: $out"; fi

# ---------------------------------------------------------------- a new pack on a running node with a list saved in Set up
# The node lists what it loaded, which cannot include a pack fetched a second ago; its pip: and env: lines were skipped
# that way on node #1 (26 Oct 2026), and the saved PACKS_ENABLED kept it off without a word.
printf '{"runtime": [{"key": "PACKS_ENABLED", "value": "heat, rain-gauge,tide"}]}' > "$d/settings-api.json"
echo "ADMIN_TOKEN=t" >> "$N/.env"; : > "$d/docker.log"; : > "$d/put.log"
touch "$d/node-up"; out="$(pa add someone/synop)"; rc=$?
grep -qx pybufrkit "$N/app/requirements-packs.txt" 2>/dev/null && grep -qx bitstring "$N/app/requirements-packs.txt" && grep -q "compose build app" "$d/docker.log" \
  && ok "the pack just added has its pip: lines in the image, though the running node does not list it yet" \
  || bad "synop's deps were not recorded (exit $rc): $(cat "$N/app/requirements-packs.txt" 2>&1) / $out"
grep -qx "SYNOP_STATION=" "$N/.env" && ok "and its env: setting in .env" || bad "SYNOP_STATION is not in .env: $(cat "$N/.env")"
grep -qx '{"PACKS_ENABLED":"heat,rain-gauge,tide,synop"}' "$d/put.log" 2>/dev/null && grep -q "synop joins the packs this node loads" <<< "$out" \
  && ok "a list saved in Set up gets the new pack, and says so" || bad "PACKS_ENABLED was not extended: $(cat "$d/put.log" 2>&1) / $out"
sed -i.bak '/^ADMIN_TOKEN=/d' "$N/.env" && rm -f "$N/.env.bak"
out="$(pa add someone/synop)"
[ "$(wc -l < "$d/put.log")" -eq 1 ] && grep -q "planetai ui (it creates the admin token), then planetai config set PACKS_ENABLED heat,rain-gauge,tide,synop" <<< "$out" \
  && ok "with no token to write it, it says the pack stays off, and how to make the token and turn it on" || bad "no switch-on hint: $out"
printf '{"runtime": [{"key": "PACKS_ENABLED", "value": ""}]}' > "$d/settings-api.json"
out="$(pa add someone/synop)"; rm -f "$d/node-up"
[ "$(wc -l < "$d/put.log")" -eq 1 ] && ! grep -q "PACKS_ENABLED" <<< "$out" \
  && ok "an empty list is every pack, and is left alone" || bad "an empty PACKS_ENABLED was touched: $out"

# ---------------------------------------------------------------- a build that fails records nothing, so the next run builds
rm -f "$N/app/requirements-packs.txt"; touch "$d/build-fails"
out="$(pa add someone/synop)"; rc=$?; rm -f "$d/build-fails"
[ $rc -ne 0 ] && [ ! -e "$N/app/requirements-packs.txt" ] && grep -q "rebuild failed, so nothing was recorded" <<< "$out" \
  && ok "a failed build leaves the dependency list as it was" || bad "a failed build kept its list (exit $rc): $out"
: > "$d/docker.log"; out="$(pa install)"
grep -qx pybufrkit "$N/app/requirements-packs.txt" 2>/dev/null && grep -q "compose build app" "$d/docker.log" \
  && ok "so packs install, run again, builds" || bad "the retry did not build: $out"

# ---------------------------------------------------------------- packs pending: an Install pressed on the page
# The page writes out/requests/pack-add.json; the crontab line runs `packs pending`, which trusts an id on the list and
# a commit that must be the one it resolves itself (docs/decisions/2026-10-27-pack-install-from-the-page.md).
Q="$N/out/requests"; mkdir -p "$Q"
st() { python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["state"] + "|" + d.get("line", ""))' "$Q/pack-add.status" 2>/dev/null; }
ask() { printf '{"id": "%s", "commit": "%s", "at": 1}' "$1" "$2" > "$Q/pack-add.json"; }
: > "$d/docker.log"
out="$(pa pending)"; [ $? -eq 0 ] && [ ! -e "$Q/pack-add.status" ] && [ ! -s "$d/docker.log" ] \
  && ok "pending with no request does nothing and writes nothing" || bad "pending with no request did something: $out"
ask ebb "$S2"; out="$(pa pending)"
if [ -f "$N/packs/ebb/pack.yaml" ] && grep -qx "commit=$S2" "$N/packs/ebb/.wild" && [ "$(st)" = "done|installed at ${S2:0:12} and loaded" ] \
   && [ ! -e "$Q/pack-add.json" ] && [ ! -e "$Q/lock" ] && grep -q "compose up -d --force-recreate app" "$d/docker.log"; then
  ok "a request for a listed pack at the commit the list gives now: installed, the app restarted, done said, the request and the lock gone"
else bad "the request was not carried out: $(st) / $(ls -A "$Q") / $out"; fi
ask flow "$S1"; pa pending >/dev/null
[ ! -e "$N/packs/flow" ] && grep -q "^failed|the pack changed since you read it: the list now gives ${S2:0:12}, the page showed ${S1:0:12}" <<< "$(st)" \
  && ok "any other commit is refused, with the commit the page showed and the one the list gives" || bad "a request at another commit: $(st)"
printf '{"id": "../etc", "commit": "x"}' > "$Q/pack-add.json"; pa pending >/dev/null
[ "$(st)" = "failed|the request was not a pack id and a commit, so nothing was fetched" ] && [ ! -e "$Q/pack-add.json" ] \
  && ok "a request that is not an id and a commit fetches nothing, and is not tried again" || bad "a malformed request: $(st)"
ask ebb "$S2"; pa pending >/dev/null
grep -q "^failed|packs/ebb is already here. To update a wild pack: planetai packs add ebb" <<< "$(st)" \
  && ok "a pack already here is not installed again from the page; updating it is the terminal's" || bad "a second request for ebb: $(st)"
ask flow "$S2"; mkdir "$Q/lock"; pa pending >/dev/null
[ -e "$Q/pack-add.json" ] && [ ! -e "$N/packs/flow" ] && ok "while another run holds the lock, the request waits for the next minute" || bad "the lock was ignored"
rmdir "$Q/lock"; rm -f "$Q/pack-add.json"
touch "$d/build-fails"; ask deps "$S2"; pa pending >/dev/null; rm -f "$d/build-fails"
[ ! -e "$N/packs/deps" ] && grep -q "^failed|rebuild failed, so nothing was recorded" <<< "$(st)" && [ ! -e "$Q/lock" ] \
  && ok "a new pack whose libraries do not build is taken out again, and the page gets packs add's own line" || bad "a failed build: $(st) / $(ls "$N/packs")"

# ---------------------------------------------------------------- packs cron: the line, once
printf '#!/bin/sh\nif [ "$1" = -l ]; then cat "%s/crontab" 2>/dev/null; else cat > "%s/crontab.new" && mv "%s/crontab.new" "%s/crontab"; fi\n' "$d" "$d" "$d" "$d" > "$d/bin/crontab"; chmod +x "$d/bin/crontab"
echo "17 3 * * * cd /x && ./backup.sh # planetai-backup" > "$d/crontab"
pa cron >/dev/null; pa cron >/dev/null
[ "$(grep -c planetai-packs "$d/crontab")" -eq 1 ] && grep -q planetai-backup "$d/crontab" \
  && grep -q "^\* \* \* \* \* \[ -f '$N/out/requests/pack-add.json' \] && cd '$N' && PATH=/opt/homebrew/bin:/usr/local/bin:\$PATH bin/planetai packs pending" "$d/crontab" \
  && ok "packs cron adds one line, beside the backup's, that runs pending only when the page asked" || bad "the crontab: $(cat "$d/crontab")"

echo
[ "$fails" -eq 0 ] && { echo "packs add: pinned, one folder, refusals write nothing, core and wild listed apart"; exit 0; }
echo "packs add: $fails failure(s)"; exit 1
