#!/usr/bin/env bash
# `planetai hello` (docs/SPEC_hello.md §5): it shows what goes public, sends nothing on a no, and on a yes opens one
# pull request that adds this node to registry.json, or replaces it, keeping its history. curl and gh are stubs; git
# is real, pushing to a bare repo standing in for the fork.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$PWD"; fails=0
ok(){ echo "  ok   $1"; }; bad(){ echo "  FAIL $1"; fails=$((fails+1)); }

D="$(mktemp -d)"; mkdir -p "$D/node/bin" "$D/stub"
printf 'NODE_NAME=mahon1\nNODE_CITY=Mahon\nAPP_PORT=8080\n' > "$D/node/.env"
cp "$REPO/bin/planetai" "$D/node/bin/planetai"
cat > "$D/stub/curl" <<S
#!/bin/sh
case "\$*" in
  */registry.json*) [ -e "$D/listed" ] && cat "$D/listed" || echo '{"nodes": []}';;
  */sensors*) echo '[{"sensor_id": "sck-1", "source": "smartcitizen"}, {"sensor_id": "om", "source": "open-meteo"}, {"sensor_id": "sck-2", "source": "smartcitizen"}]';;
  */ground/meta*) echo '{"on_disk": {"vector": true, "drone": false, "imagery": true}}';;
  *) echo '{"node": "mahon1", "position": "cell", "lat": 39.889, "lon": 4.265, "cell": {"id": "8839a1b2c3fffff", "res": 8}}';;
esac
S
# fabcity's main is a bare repo: an old commit that still lists a node since gone, then today's registry. The fork
# stops at the old one. #365 was cut from such a fork and undid every entry merged after it.
git init -q --bare -b main "$D/upstream.git"
( g="$(mktemp -d)" && cd "$g" && git init -q \
  && python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); r["nodes"].append({"name": "gone"}); print(json.dumps(r))' \
       "$REPO/registry.json" > registry.json \
  && git add . && git -c user.name=t -c user.email=t@t commit -qm old && git push -q "$D/upstream.git" HEAD:refs/tags/old \
  && cp "$REPO/registry.json" . && git -c user.name=t -c user.email=t@t commit -qam today && git push -q "$D/upstream.git" HEAD:main && rm -rf "$g" )
# gh: logged in; a fork is a bare repo whose main is the old commit; sync fast-forwards it; the PR is recorded, not sent
cat > "$D/stub/gh" <<S
#!/bin/sh
case "\$1 \$2" in
  "auth status") exit 0;;
  "repo fork") git clone -q --bare "$D/upstream.git" "$D/fork.git" && git --git-dir="$D/fork.git" update-ref refs/heads/main old \\
      && git clone -q "$D/fork.git" planetai-node 2>/dev/null;;
  "repo sync") git --git-dir="$D/fork.git" fetch -q "$D/upstream.git" main:main;;
  "api user") echo someone;;
  "pr create") echo "\$@" > "$D/pr";;
esac
S
chmod +x "$D/stub/curl" "$D/stub/gh"
run() { PATH="$D/stub:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin" PLANETAI_HOME="$D/node" GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t \
        GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t python3 "$REPO/tests/pty_run.py" "$@" -- bash "$D/node/bin/planetai" hello 2>&1; }

echo "hello: what goes public is shown first, and a yes opens one pull request"

out="$(run "Mahon, Menorca, ES" "Lucas" "" n)"
[[ "$out" == *"8839a1b2c3fffff"* && "$out" == *"39.889"* ]] && ok "the cell and its centre are shown before anything is sent" || bad "the entry was not shown: $out"
[[ "$out" == *"sources   open-meteo, openstreetmap, sentinel-2, smartcitizen"* && "$out" != *"sck-1"* ]] \
  && ok "sources are every source the node reads and the map it keeps, by name, never a kit id" || bad "sources wrong: $out"
[[ ! -e "$D/pr" && ! -d "$D/fork.git" ]] && ok "a no sends nothing" || bad "a no forked or opened a pull request"

out="$(run "Mahon, Menorca, ES" "Lucas" "" y)"
[[ -e "$D/pr" ]] && grep -q -- "--repo fabcity/planetai-node" "$D/pr" && ok "a yes opens the pull request on fabcity/planetai-node" || bad "no pull request: $out"
reg="$(git --git-dir="$D/fork.git" show "$(git --git-dir="$D/fork.git" for-each-ref --format='%(refname)' refs/heads/hello-mahon1-*)":registry.json)"
printf '%s' "$reg" | python3 -c '
import json, sys
r = json.load(sys.stdin)["nodes"]
m = [n for n in r if n["name"] == "mahon1"]
assert len(m) == 1 and m[0]["operator"] == "Lucas" and m[0]["place"] == "Mahon, Menorca, ES", m
assert m[0]["lat"] == 39.889 and "contact" not in m[0], m
assert any(n["name"] == "bayu-ungasan" for n in r), "the other nodes stay"
' && ok "the branch adds mahon1 once, with no contact when none was given, and keeps the others" || bad "registry.json on the branch is wrong"
printf '%s' "$reg" | python3 -c '
import json, sys
r = [n for n in json.load(sys.stdin)["nodes"] if n["name"] != "mahon1"]
assert r == json.load(open(sys.argv[1]))["nodes"], r
' "$REPO/registry.json" && ok "the branch starts from fabcity main, not from an old fork" || bad "the branch was cut from the fork's stale list"

# already listed: the list's words are the defaults, and the same entry again sends nothing (12 Oct 2026: node #1's
# hello offered "bali" and an empty operator while the list said "Ungasan, Badung, Bali, ID" and who runs it)
rm -rf "$D/pr" "$D/fork.git"
echo '{"nodes": [{"name": "mahon1", "place": "Mahon, Menorca, ES", "operator": "Lucas", "cell": "8839a1b2c3fffff",
  "since": "2026-09", "sources": ["open-meteo", "openstreetmap", "sentinel-2", "smartcitizen"], "parent": null, "contact": "l@x.es"}]}' > "$D/listed"
out="$(run "" "" "")"
[[ "$out" == *"already listed, since 2026-09"* && "$out" == *"[Mahon, Menorca, ES]"* && "$out" == *"[Lucas]"* && "$out" == *"[l@x.es]"* ]] \
  && ok "a listed node is told so, and its listed place, operator and contact are the defaults" || bad "the listing was not offered: $out"
[[ "$out" == *"Nothing to send"* && ! -e "$D/pr" && ! -d "$D/fork.git" ]] && ok "the same entry again sends nothing" || bad "an unchanged listing was sent again: $out"

out="$(run "" "" "new@x.es" n)"
[[ "$out" == *"since     2026-09"* && "$out" == *"new@x.es"* && ! -e "$D/pr" ]] \
  && ok "a changed listing keeps the month it was first listed, and a no still sends nothing" || bad "since was reset: $out"

# #367 was titled "list bayu-ungasan" for a node listed since September, and read as a new node
out="$(run "" "" "new@x.es" y)"
grep -q "registry: update mahon1" "$D/pr" 2>/dev/null && ok "a listed node's pull request says update, not list" || bad "a listed node's title: $(cat "$D/pr" 2>/dev/null) $out"

[[ "$fails" == 0 ]] || { rm -rf "$D"; exit 1; }
rm -rf "$D"
