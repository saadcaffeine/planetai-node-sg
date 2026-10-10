#!/usr/bin/env bash
# ship.sh guards a release, so what it refuses matters. It refused four times in one afternoon for a
# state that needed no decision: main merely BEHIND origin after a pull request was merged on GitHub —
# a fast-forward away, with nothing to choose between. That is not the same as diverged.
#
# Drives the real precondition block from tools/ship.sh against throwaway repositories.
set -uo pipefail

# git exports these to its hooks, and a hook that runs `make test` passes them down here. Every
# `git add` below would then write into the caller's REAL index instead of the throwaway repo:
# running from a pre-commit hook in a worktree, this suite staged f, g, h, i and j into the actual
# commit being made, and they reached a real branch. A test that shells out to git has to own its
# own environment — the hook was fixed too, but this is the half that cannot be bypassed.
unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_COMMON_DIR

# The throwaway commits need an identity, and it comes from the environment, never `git config`. This
# suite used to run `git config user.email t@t` after a `cd` it never checked; when that config landed
# in the real checkout's shared .git/config instead, every worktree committed as `t <t@t>` — 267 commits
# on main from 11 Sep. An environment variable dies with this process, whatever directory it is in.
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

cd "$(dirname "$0")/.."
ROOT="$PWD"; SHIP="$ROOT/tools/ship.sh"; fails=0
email_before="$(git config --local user.email)"
ok(){ echo "  ok   $1"; }; bad(){ echo "  FAIL $1"; fails=$((fails+1)); }
fatal(){ echo "  FAIL $1"; exit 1; }

# The region lifted from ship.sh runs from the sync check through the line that reads the version the
# release will be LABELLED with — as one range, in ship.sh's own order. Lifting the label line separately
# and appending it would put it after the pull no matter where ship.sh keeps it, and the test would pass
# on the bug. v0.50 shipped a correct tarball committed as "tester tarball at v0.49" because that read
# sat above the pull, so it was stale by exactly one release on every release merged on GitHub.
fetch_line="$(grep -n '^git fetch -q origin$' "$SHIP" | cut -d: -f1)"
ff_end="$(awk -v s="$fetch_line" 'NR>s && /^fi$/ {print NR; exit}' "$SHIP")"
here_line="$(grep -n '^HERE="\$(git describe --tags --always)"$' "$SHIP" | cut -d: -f1 | awk -v s="$ff_end" '$1>s {print; exit}')"

if [[ -n "$here_line" ]]; then
  ok "the release label is read after the fast-forward, so it names what the tarball contains"
else
  bad "no 'HERE=\$(git describe ...)' after the fast-forward (line ${ff_end:-?}): every release that
       fast-forwards gets committed to the site repo under the PREVIOUS version's name"
  here_line="$ff_end"
fi

block="$(sed -n "${fetch_line},${here_line}p" "$SHIP")"
[[ -n "$block" ]] || { echo "  FAIL could not lift the sync check from ship.sh"; exit 1; }

# a bare "origin" and a clone of it, so ahead/behind/diverged are real rather than mocked
setup() {
  D="$(mktemp -d)" || fatal "setup: mktemp"
  git init -q --bare -b main "$D/origin.git" || fatal "setup: git init $D/origin.git"
  git clone -q "$D/origin.git" "$D/work" 2>/dev/null || fatal "setup: git clone into $D/work"
  cd "$D/work" || fatal "setup: cd $D/work"
  git checkout -q -B main
  echo one > f; git add f; git commit -q -m one
  git push -q -u origin main 2>/dev/null
}
runblock() {
  { echo 'set -uo pipefail'
    echo 'say(){ printf ">> %s\n" "$*"; }'
    echo 'die(){ printf "xx %s\n" "$*"; exit 1; }'
    printf '%s\n' "$block"
    echo 'echo "HERE=${HERE:-<never set>}"'
    echo 'echo RESULT_OK'
  } > "$D/b.sh"
  bash "$D/b.sh" 2>&1
}

echo "ship gate: what it lets through and what it stops"

setup                                                   # in sync
out="$(runblock)"; grep -q RESULT_OK <<<"$out" && ok "in sync → proceeds" || bad "in sync was refused: $out"
cd /; rm -rf "$D"

setup                                                   # behind: a merge landed on origin, and was tagged
git tag -a v0.49 -m v0.49                               # what this checkout can still see
git clone -q "$D/origin.git" "$D/other" 2>/dev/null && cd "$D/other" || fatal "clone into $D/other"
git checkout -q main 2>/dev/null
echo two > g && git add g && git commit -q -m two && git tag -a v0.50 -m v0.50 \
  && git push -q origin main 2>/dev/null && git push -q origin v0.50 2>/dev/null
cd "$D/work" && git fetch -q --tags origin
out="$(runblock)"
grep -q RESULT_OK <<<"$out" && ok "behind → fast-forwards and proceeds" || bad "behind was refused: $out"
grep -q "fast-forwarding" <<<"$out" && ok "and says it did so" || bad "it fast-forwarded silently"
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] && ok "and the tree really moved" || bad "HEAD did not move"
# the label must name what was just pulled, not what was here before it
want="$(git describe --tags --always origin/main)"
got="$(sed -n 's/^HERE=//p' <<<"$out" | tail -1)"
[[ "$got" == "$want" ]] && ok "and the release is labelled $want, the version it actually contains" \
  || bad "labelled '$got' but contains '$want' — the site repo's history would name the wrong release"
cd /; rm -rf "$D"

setup                                                   # ahead: an unpushed commit
echo three > h && git add h && git commit -q -m three
out="$(runblock)"
grep -q RESULT_OK <<<"$out" && bad "ahead was allowed — the tarball would not match what is public" \
  || ok "ahead → refuses, because the tarball must match what is public"
grep -q "git push" <<<"$out" && ok "and names the command" || bad "no command named"
cd /; rm -rf "$D"

setup                                                   # diverged: both sides moved
git clone -q "$D/origin.git" "$D/other" 2>/dev/null && cd "$D/other" || fatal "clone into $D/other"
git checkout -q main 2>/dev/null
echo far > i && git add i && git commit -q -m far && git push -q origin main 2>/dev/null
cd "$D/work" && echo near > j && git add j && git commit -q -m near && git fetch -q origin
out="$(runblock)"
grep -q RESULT_OK <<<"$out" && bad "a diverged tree was allowed to build a release" \
  || ok "diverged → refuses, which is the case where guessing would be wrong"
grep -q "diverged" <<<"$out" && ok "and says so" || bad "does not say diverged"
cd /; rm -rf "$D"

# The fast-forward rewrites the worktree, and one of the files in it is ship.sh itself. bash reads a script
# incrementally by byte offset, so replacing it mid-run can resume inside different content — and it is why
# a fix below the pull cannot govern the release that introduces it (v0.51 shipped the label fix and was
# still labelled v0.50). The script must notice and restart. Proving that needs the script to live INSIDE
# the repository being pulled, which is the one thing the lifted-block harness above cannot do.
reexec_block="$(sed -n "${fetch_line},$(awk -v s="$here_line" 'NR>s && /^fi$/ {print NR; exit}' "$SHIP")p" "$SHIP")"

setup
mkdir -p "$D/work/tools"
{ echo '#!/usr/bin/env bash'
  echo 'set -uo pipefail'
  echo 'say(){ printf ">> %s\n" "$*"; }'
  echo 'die(){ printf "xx %s\n" "$*"; exit 1; }'
  echo 'SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"'
  echo 'echo "I AM version-one"'
  printf '%s\n' "$reexec_block"
  echo 'echo "BUILDING-AS ${HERE:-<never set>}"'
} > "$D/work/tools/s.sh"
chmod +x "$D/work/tools/s.sh"
git -C "$D/work" add tools/s.sh && git -C "$D/work" commit -q -m "the script, version one"
git -C "$D/work" tag -a v1 -m v1
git -C "$D/work" push -q origin main 2>/dev/null

# origin moves ahead AND edits the script, exactly as a merged release does
git clone -q "$D/origin.git" "$D/other" 2>/dev/null || fatal "clone into $D/other"
sed -i.bak 's/I AM version-one/I AM version-two/' "$D/other/tools/s.sh" && rm -f "$D/other/tools/s.sh.bak"
git -C "$D/other" commit -q -am "the script, version two"
git -C "$D/other" tag -a v2 -m v2
git -C "$D/other" push -q origin main 2>/dev/null && git -C "$D/other" push -q origin v2 2>/dev/null
git -C "$D/work" fetch -q --tags origin

# SHIP_WITHOUT_CI=1 because this throwaway repo has no workflow at all, which is the one case the CI
# check is meant to let through. Without it the run now stops at the gate closed after v0.68 shipped
# ahead of its own lint, and never reaches the restart this case is about.
out="$(cd "$D/work" && SHIP_WITHOUT_CI=1 bash tools/s.sh 2>&1)"
grep -q "restarting so this release is built by the new one" <<<"$out" \
  && ok "a fast-forward that replaces ship.sh restarts it" \
  || bad "ship.sh was replaced mid-run and carried on reading the old file: $out"
grep -q "I AM version-two" <<<"$out" \
  && ok "and the second run is the NEW script, not the one that started" \
  || bad "it restarted but ran the old script again: $out"
[[ "$(grep -c 'I AM version' <<<"$out")" == 2 ]] \
  && ok "exactly twice — once before the pull, once after, no loop" \
  || bad "expected exactly two runs, got $(grep -c 'I AM version' <<<"$out"): $out"
[[ "$(sed -n 's/^BUILDING-AS //p' <<<"$out" | tail -1)" == v2 ]] \
  && ok "and it builds as v2, the version it actually contains" \
  || bad "labelled '$(sed -n 's/^BUILDING-AS //p' <<<"$out" | tail -1)', not v2: $out"

# And the gate bites without that escape. v0.68 was built and signed minutes before its own lint went
# red, because an empty run list read as "nothing to wait for" rather than "CI has not started". A
# check that only ever passes is not a check, so this asserts the refusal, not just the pass above.
out="$(cd "$D/work" && bash tools/s.sh 2>&1)"; rc=$?
[[ $rc -ne 0 ]] && grep -q "no CI run has started for this commit yet" <<<"$out" \
  && ok "and with no CI run and no escape, it refuses" \
  || bad "shipped with nothing having tested the commit (rc=$rc): $out"

cd /; rm -rf "$D"

# Whatever ran above, the repository this suite was run from keeps the identity it came in with.
[[ "$(git -C "$ROOT" config --local user.email)" == "$email_before" ]] \
  && ok "the invoking repo's local user.email is unchanged" \
  || bad "the invoking repo's local user.email changed from '$email_before' to '$(git -C "$ROOT" config --local user.email)'"

[[ $fails -eq 0 ]] && { echo "ship gate tests pass"; exit 0; } || { echo "$fails failed"; exit 1; }
