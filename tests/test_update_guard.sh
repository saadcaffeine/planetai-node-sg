#!/usr/bin/env bash
# update.sh stops before a release whose core pack has the same id as a wild pack on the node (one `planetai packs
# add` fetched, marked by packs/<id>/.wild). The guard's three functions are lifted out of the real update.sh and run
# against a throwaway node: once with a tarball unpacked beside it, once with a real git remote. Then the file itself
# is read to show the guard runs before the overlay and before the pull, which is the whole point of it.
set -uo pipefail
cd "$(dirname "$0")/.."
fails=0
ok()  { echo "  ok   $*"; }
bad() { echo "  FAIL $*"; fails=$((fails + 1)); }
d="$(mktemp -d)"; trap 'rm -rf "$d"' EXIT
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.invalid GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.invalid

sed -n '/^core_in_dir() {/,/^}$/p' update.sh > "$d/guard.sh"
grep -q '^wild_collisions() {' "$d/guard.sh" && grep -q '^core_in_ref() {' "$d/guard.sh" \
  || { echo "  FAIL could not lift core_in_dir, core_in_ref and wild_collisions out of update.sh"; exit 1; }

pack() { mkdir -p "$1"; printf 'id: %s\n' "$(basename "$1")" > "$1/pack.yaml"; }
wild() { pack "$1"; printf 'source=%s\ncommit=%s\nadded=2026-10-02\n' "$2" "$3" > "$1/.wild"; }
guard() { (cd "$1" && shift && source "$d/guard.sh" && wild_collisions "$@"); }   # guard <node> <check> <arg>

# ---------------------------------------------------------------- the tarball path: the release unpacked in a temp folder
N="$d/node"; pack "$N/packs/heat"; echo keep > "$N/packs/heat/SENTINEL"
wild "$N/packs/rain" someone/rain 1111111111111111111111111111111111111111
wild "$N/packs/tide" fabcity/planetai-wild-packs/packs/tide 2222222222222222222222222222222222222222
R="$d/release/planetai-node"; pack "$R/packs/heat"; pack "$R/packs/rain"     # rain was promoted to core

out="$(guard "$N" core_in_dir "$R" 2>&1)"; rc=$?
[ $rc -ne 0 ] && ok "a release with a core pack named like a wild one stops the update" || bad "it did not stop (exit $rc): $out"
grep -q "packs/rain came from someone/rain (commit 111111111111)" <<< "$out" && grep -q "rm -rf packs/rain" <<< "$out" \
  && ok "it names the wild copy, where it came from, and the one command that clears it" || bad "the message is missing its parts: $out"
grep -q "tide" <<< "$out" && bad "it named tide, which the release does not ship: $out" || ok "a wild pack the release does not ship is not mentioned"
grep -q "packs/heat" <<< "$out" && bad "it named heat, a core pack on both sides: $out" || ok "a core pack on both sides is not a collision"
[ -f "$N/packs/rain/.wild" ] && [ -f "$N/packs/heat/SENTINEL" ] && ok "and it changed nothing on the node" || bad "the guard changed the node"

rm -rf "$R/packs/rain"
out="$(guard "$N" core_in_dir "$R" 2>&1)"; rc=$?
[ $rc -eq 0 ] && [ -z "$out" ] && ok "with no collision it says nothing and lets the update go on" || bad "no collision, but exit $rc: $out"

# ---------------------------------------------------------------- the git path: a real remote that gains the pack
git init -q --bare -b main "$d/origin.git"
git clone -q "$d/origin.git" "$d/up" 2>/dev/null
pack "$d/up/packs/heat"; git -C "$d/up" add -A; git -C "$d/up" commit -qm one; git -C "$d/up" push -q origin main 2>/dev/null
git clone -q "$d/origin.git" "$d/gnode" 2>/dev/null
wild "$d/gnode/packs/rain" someone/rain 1111111111111111111111111111111111111111   # untracked, as packs add leaves it
pack "$d/up/packs/rain"; git -C "$d/up" add -A; git -C "$d/up" commit -qm "rain is core now"; git -C "$d/up" push -q origin main 2>/dev/null
git -C "$d/gnode" fetch -q origin

out="$(guard "$d/gnode" core_in_ref origin/main 2>&1)"; rc=$?
[ $rc -ne 0 ] && grep -q "rm -rf packs/rain" <<< "$out" && ok "on a git checkout, the fetched branch is read before the pull" \
  || bad "the git path did not stop (exit $rc): $out"
pull="$(git -C "$d/gnode" pull --ff-only -q origin main 2>&1)"; prc=$?
[ $prc -ne 0 ] && grep -qi "untracked" <<< "$pull" \
  && ok "which matters: without it, git refuses the pull and blames untracked files" || bad "expected git to refuse the pull (exit $prc): $pull"
out="$(guard "$d/gnode" core_in_ref "origin/main~1" 2>&1)"; rc=$?
[ $rc -eq 0 ] && ok "a branch without that pack passes" || bad "a ref without rain stopped the update: $out"

# ---------------------------------------------------------------- wired in: before the overlay, before the pull
at() { grep -nF -- "$1" update.sh | head -1 | cut -d: -f1; }
x="$(at 'tar xzf "$tmp/n.tar.gz" -C "$tmp"')"; g="$(at 'wild_collisions core_in_dir "$tmp/planetai-node"')"; o="$(at '( cd "$tmp/planetai-node" && tar cf - . )')"
[ -n "$x" ] && [ -n "$g" ] && [ -n "$o" ] && [ "$x" -lt "$g" ] && [ "$g" -lt "$o" ] \
  && ok "update.sh runs it after unpacking the release and before copying it over the node" || bad "tarball path order is wrong or the call is missing (extract $x, guard $g, overlay $o)"
grep -A1 -F 'wild_collisions core_in_dir "$tmp/planetai-node"' update.sh | grep -qF 'rm -rf "$tmp"; exit 1' \
  && ok "and stops there, removing the download" || bad "the tarball guard does not exit, or leaves the download behind"
f="$(at 'git fetch -q --tags origin')"; g="$(at 'wild_collisions core_in_ref "origin/$branch"')"; p="$(at 'git pull --ff-only origin "$branch"')"
[ -n "$f" ] && [ -n "$g" ] && [ -n "$p" ] && [ "$f" -lt "$g" ] && [ "$g" -lt "$p" ] \
  && ok "update.sh runs it after the fetch and before the pull" || bad "git path order is wrong or the call is missing (fetch $f, guard $g, pull $p)"

echo
[ "$fails" -eq 0 ] && { echo "update guard: a promoted wild pack stops the update before anything moves, on both paths"; exit 0; }
echo "update guard: $fails failure(s)"; exit 1
