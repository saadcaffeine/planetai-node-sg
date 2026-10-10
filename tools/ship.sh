#!/usr/bin/env bash
# Put what is on main in front of a tester. Three steps that were three separate things to remember:
#   tools/ship.sh              rebuild the tarball, commit it in the site repo, deploy the site
#   tools/ship.sh --no-deploy  everything except the deploy
#   tools/ship.sh --check      say only whether the site is behind main, and exit 1 if it is
#   tools/ship.sh --check-docs say only whether this machine can build the docs site
#
# The docs at planetai.fab.city/docs are rebuilt here too, from the same commit as the tarball, and go
# into the site repo in the same commit. They were a separate step until v0.72.1, and nobody took it
# for fifteen releases: the site described v0.57 while testers ran v0.72.
#
# A merge is not a release. `/install` and `/preflight` are stubs that fetch the current file from this
# repository on every run, so those two are never stale — but `install.sh` and `bin/planetai` reach a
# tester inside the tarball, and the tarball only changes when somebody rebuilds it. That gap shipped
# silent sudos to Linux testers for an hour on 8 September 2026, twice, because it was a step to recall.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

say(){ printf '\033[1;32m>>\033[0m %s\n' "$*"; }
die(){ printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- signing
#
# The checksum next to the tarball proves the bytes did not rot in transit. It proves nothing about who
# built them: anybody who can write to planetai.fab.city/node0/get writes the tarball AND the SHA256, and
# every node takes it on its next `planetai update` with the checksum matching, because they wrote both.
#
# So the tarball is signed with a key that is not on the web server, and `tools/allowed_signers` publishes
# the public half that nodes check against. `--check-key` answers the question without building anything,
# which is what release.sh asks before it cuts a tag.
signing_key() {
  local key="${PLANETAI_SIGNING_KEY:-}"
  [[ -n "$key" ]] || die "PLANETAI_SIGNING_KEY is not set, so this build could not be signed and every node
   would refuse it. Point it at the release key:
     PLANETAI_SIGNING_KEY=~/.planetai/release_key make ship
   docs/SIGNING.md says where that key lives and the one command that makes one.
   A dev tarball nobody will install:  PLANETAI_UNSIGNED=1 make ship"
  key="${key/#\~/$HOME}"
  [[ -f "$key" ]] || die "PLANETAI_SIGNING_KEY points at $key, which is not a file."
  # A key inside the repository is one `git add .` from being public. Compare resolved directories.
  local keydir; keydir="$(cd "$(dirname "$key")" && pwd)"
  case "$keydir/" in "$PWD"/*) die "the signing key is inside the repository ($keydir). Move it out —
   ~/.planetai/release_key is the place. A key here is one commit from being published.";; esac
  command -v ssh-keygen >/dev/null || die "no ssh-keygen on this machine, so nothing can be signed."
  grep -q PLACEHOLDER tools/allowed_signers && die "tools/allowed_signers still carries the placeholder, so no
   release key has been issued yet. docs/SIGNING.md has the command that makes it and the four
   places the public line is pasted."
  # The key that signs must be the key the committed line publishes, or nodes verify against a stranger.
  #
  # Read out of the .pub beside it. `ssh-keygen -y -f <private key>` answers the same question but reads
  # the PRIVATE half and prompts for the passphrase to do it — it does not consult ssh-agent, so the old
  # form failed here however many times you had run ssh-add, and said to run ssh-add again. (19 Sep 2026,
  # the first time this was run against a real key.)
  local pub want
  if [[ -f "$key.pub" ]]; then
    pub="$(awk '{print $1" "$2}' "$key.pub")"
  else
    pub="$(ssh-keygen -y -f "$key" 2>/dev/null | awk '{print $1" "$2}')"
  fi
  [[ -n "$pub" ]] || die "could not read a public key for $key. If it is passphrase-protected and has no
   .pub beside it, write one:  ssh-keygen -y -f $key > $key.pub"
  want="$(grep -v '^[[:space:]]*\(#\|$\)' tools/allowed_signers | head -1 | awk '{print $2" "$3}')"
  [[ "$pub" == "$want" ]] || die "the key in PLANETAI_SIGNING_KEY is not the one tools/allowed_signers publishes.
   signing with  $pub
   nodes trust   $want
   Either this is the wrong key, or a rotation was never committed. Do not ship past this."
  printf '%s' "$key"
}

# Sign the tarball in place, beside its checksum. `-n planetai-node` is the namespace: a signature made
# for anything else — a git commit, an email — will not verify as a release, however valid it is.
sign_tarball() {
  local tgz="$1" key
  if [[ "${PLANETAI_UNSIGNED:-0}" == 1 ]]; then
    printf '\033[1;31m!! PLANETAI_UNSIGNED=1 — this tarball is NOT signed. Every node will refuse it.\033[0m\n' >&2
    rm -f "$tgz.sig"
    return 0
  fi
  key="$(signing_key)" || exit 1
  # `ssh-keygen -Y sign` PROMPTS when <file>.sig is already there — "…already exists. Overwrite
  # (y/n)?" — and with nothing on stdin it answers itself, leaves the old signature untouched, and
  # EXITS 0. So the `|| die` below cannot see it. The first release had no .sig to collide with; the
  # second, v0.62, signed nothing and would have published v0.61's signature over a new tarball. The
  # verify at the end of this function is what caught it. Give it nothing to overwrite.
  rm -f "$tgz.sig"
  # Sign through the agent where there is one. `-f <public key>` is what makes ssh-keygen ask the agent
  # for the private half; `-f <private key>` reads the file and prompts, which cannot work unattended and
  # is what stopped the first real release. Falls back to the private key when the agent has nothing, so
  # an unencrypted key on a build machine still signs.
  local signwith="$key"
  if [[ -f "$key.pub" ]] && ssh-add -l >/dev/null 2>&1; then signwith="$key.pub"; fi
  ssh-keygen -Y sign -f "$signwith" -n planetai-node "$tgz" >/dev/null \
    || die "ssh-keygen could not sign $tgz with $signwith.
   If that is a passphrase-protected key, put it in the agent first:  ssh-add $key"
  # Verify what was just written, against the same file a node will use. A signature nobody checked here
  # is a signature discovered to be wrong by a tester in Menorca.
  ssh-keygen -Y verify -f tools/allowed_signers -I fabcity -n planetai-node \
    -s "$tgz.sig" < "$tgz" >/dev/null \
    || die "the signature just written does not verify against tools/allowed_signers. Nothing was shipped."
  say "signed, and the signature verifies against tools/allowed_signers"
}

# The docs build needs the `markdown` package, which a node never has and a Mac's own python3 does not
# either. Find an interpreter that has it rather than asking somebody to remember which one it is.
docs_python() {
  local p
  for p in python3 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    command -v "$p" >/dev/null 2>&1 && "$p" -c 'import markdown' 2>/dev/null && { printf '%s' "$p"; return 0; }
  done
  return 1
}
NODOCS_MSG="no python3 on this machine has the markdown package, so the docs site cannot be rebuilt
   and planetai.fab.city/docs would go on describing the last release. Install it once:
     python3 -m pip install --user markdown
   Or ship without the docs, deliberately, and rebuild them after with make docs:
     SHIP_WITHOUT_DOCS=1 make ship"

SITE="${PLANETAI_SITE_REPO:-../planetai}"
DEPLOY=1; CHECK=0; KEYCHECK=0; DOCSCHECK=0
for a in "$@"; do case "$a" in --no-deploy) DEPLOY=0;; --check) CHECK=1;; --check-key) KEYCHECK=1;; --check-docs) DOCSCHECK=1;; *) die "unknown flag $a";; esac; done

HERE="$(git describe --tags --always)"
# Absolute, resolved before the fast-forward can rewrite anything, so the re-exec below does not depend on
# the cwd and cannot pick up a different file than the one that started.
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
[[ -d "$SITE/.git" ]] || die "no site repo at $SITE. Clone fabcity/planetai beside this one, or set PLANETAI_SITE_REPO."

if [[ $KEYCHECK -eq 1 ]]; then
  if [[ "${PLANETAI_UNSIGNED:-0}" == 1 ]]; then
    printf '\033[1;31m!! PLANETAI_UNSIGNED=1 — this release will not be signed. Nodes will refuse it.\033[0m\n' >&2
    exit 0
  fi
  signing_key >/dev/null && say "signing key present, and it matches tools/allowed_signers"
  exit 0
fi

if [[ $DOCSCHECK -eq 1 ]]; then
  if [[ "${SHIP_WITHOUT_DOCS:-0}" == 1 ]]; then
    printf '\033[1;33m!!\033[0m SHIP_WITHOUT_DOCS=1: this release will not rebuild planetai.fab.city/docs.\n' >&2
    exit 0
  fi
  PY="$(docs_python)" || die "$NODOCS_MSG"
  say "the docs site can be built here ($PY)"
  exit 0
fi

live_version() { curl -fsSL "https://planetai.fab.city/node0/get/VERSION?cb=$RANDOM.$$" 2>/dev/null || echo unreachable; }

if [[ $CHECK -eq 1 ]]; then
  # The question is whether the site is behind MAIN, so compare main — not HEAD. It compared HEAD, and
  # HEAD is usually a feature branch: from a branch five commits ahead this printed the branch's own
  # describe labelled "main is at" and called the site behind, when main and the site agreed exactly.
  # A release check that cries wolf on every branch is one nobody reads. Shipping refuses anywhere but
  # main; the check now answers about main from anywhere.
  MAIN="$(git describe --tags --always main 2>/dev/null)" || die "no main branch here."
  BR="$(git rev-parse --abbrev-ref HEAD)"
  # VERSION is served with max-age=300, so for a few minutes after a deploy some Cloudflare edges
  # still answer from the old entry. Read once; only if that disagrees, read again a few times before
  # calling the site behind — this check said "behind" seconds after a deploy that had worked, which
  # is the one thing a release check must never get wrong.
  LIVE="$(live_version)"
  if [[ "$MAIN" != "$LIVE" ]]; then
    for _ in 1 2 3 4; do
      sleep 10
      LIVE="$(live_version)"
      [[ "$MAIN" == "$LIVE" ]] && break
    done
  fi
  printf '  main is at          %s\n  the site serves     %s\n' "$MAIN" "$LIVE"
  [[ "$BR" == main ]] || printf '  (you are on %s, at %s — nothing on it is public until it reaches main.)\n' "$BR" "$HERE"
  [[ "$MAIN" == "$LIVE" ]] && { say "a tester gets what is on main"; exit 0; }
  printf '\033[1;33m!!\033[0m the site is behind. A tester downloading now gets the older node: tools/ship.sh\n'
  exit 1
fi

[[ -z "$(git status --porcelain)" ]] || die "this repository is dirty. Commit first — a tester should never get an uncommitted file."
[[ "$(git rev-parse --abbrev-ref HEAD)" == main ]] || die "ship from main, not $(git rev-parse --abbrev-ref HEAD)."
# "Behind" is not "diverged". After a PR is merged on GitHub the local checkout is simply behind, a
# fast-forward away, and refusing there sent somebody to run `git pull` and come back four separate
# times today. Fast-forward it and carry on; refuse only when the two have actually diverged, which is
# the case where guessing would be wrong.
git fetch -q origin
AHEAD="$(git rev-list --count origin/main..HEAD)"
BEHIND="$(git rev-list --count HEAD..origin/main)"
if [[ "$AHEAD" != 0 && "$BEHIND" != 0 ]]; then
  die "main and origin/main have diverged — $AHEAD here, $BEHIND there. Sort that out first; a release
   should never be built from a tree nobody else has."
elif [[ "$AHEAD" != 0 ]]; then
  die "main is $AHEAD commit(s) ahead of origin. Push first, so the tarball matches what is public:
     git push"
elif [[ "$BEHIND" != 0 ]]; then
  say "main is $BEHIND commit(s) behind origin — fast-forwarding, then building from that"
  # NOT backticks: inside a double-quoted string they run the command and paste its output, so this
  # message used to execute `git pull` a second time while building itself and then print a hole where
  # the command name should be.
  WAS="$(cksum < "$SELF")"
  git pull -q --ff-only || die "the fast-forward failed. Run this and read what it says:
     git pull"

  # That pull just rewrote this worktree, and one of the files in it is THIS script.
  #
  # bash does not slurp a script: it reads it incrementally and remembers a byte offset. Replace the file
  # underneath a running shell and it carries on reading at that offset into different content — which is
  # usually a syntax error, and can be a line of some other command. In the middle of a release.
  #
  # It is also why a fix to anything below this line cannot govern the release that introduces it. v0.50
  # committed a correct tarball as "tester tarball at v0.49"; the fix for that shipped in v0.51, and v0.51
  # was still labelled v0.50, because the running script was the pre-fix one the pull had just replaced.
  #
  # So: if the pull changed this file, start it again. The second run finds itself in sync, does not pull,
  # and reads every line from the version it is actually building.
  if [[ "$(cksum < "$SELF")" != "$WAS" ]]; then
    if [[ "${PLANETAI_SHIP_REEXEC:-0}" == 1 ]]; then
      # Only ever once. A second change means somebody pushed again while this was running, and looping
      # on that would be worse than carrying on: HERE is re-read below, so the release is still labelled
      # correctly, and the lines below this point are whatever bash has already buffered.
      say "ship.sh changed again during the release — not restarting a second time"
    else
      say "the fast-forward replaced ship.sh itself — restarting so this release is built by the new one"
      PLANETAI_SHIP_REEXEC=1 exec "$SELF" "$@"
    fi
  fi
fi

# HERE was read at the top, which is what the --check path above wants: it answers about the branch you
# are standing on. Past the fast-forward it is stale by exactly one release, and every release merged on
# GitHub rather than locally comes through here. v0.50 shipped a correct tarball under the commit message
# "tester tarball at v0.49"; the payload was right because bundle.sh reads the tag itself, so only the site
# repo's history lied, and it lied about every release that was ever fast-forwarded.
HERE="$(git describe --tags --always)"

# A release should be a commit whose tests passed. This was added because I shipped v0.41.2-69 while
# its install-smoke run was still queued, and it went red — a workflow edit of mine had split a grep
# across two lines, which is valid bash and so no local check could see it. The tarball was fine that
# time; the point is that nothing knew it was fine.
#
# Missing or unauthenticated `gh` is not a reason to block a release: warn and carry on. A red run is.
if command -v gh >/dev/null 2>&1; then
  CI="$(gh run list --commit "$(git rev-parse HEAD)" --limit 20 \
        --json conclusion,status,workflowName,url 2>/dev/null || true)"
  if [[ -z "$CI" || "$CI" == "[]" ]]; then
    # "No run yet" is not "nothing to wait for". A push fires the workflows within seconds, so an
    # empty list on a commit that has just been pushed means CI has not STARTED — which is the
    # pending case, not the absent one. Treating it as absent is how v0.68 was built and signed
    # minutes before its own lint went red, and shipped with a red gate nobody saw.
    [[ "${SHIP_WITHOUT_CI:-0}" == 1 ]] || die "no CI run has started for this commit yet, so nothing
   has tested what you are about to hand a tester. Wait for it to appear and finish, then ship — or,
   if this commit genuinely has no workflow:
     SHIP_WITHOUT_CI=1 make ship"
    say "no CI run for this commit, shipping anyway because SHIP_WITHOUT_CI=1"
  else
    BAD="$(printf '%s' "$CI" | python3 -c 'import json,sys
r=json.load(sys.stdin)
bad=[x for x in r if x.get("conclusion") in ("failure","timed_out","cancelled")]
print("\n".join("   %s: %s  %s" % (x["workflowName"], x["conclusion"], x["url"]) for x in bad))' 2>/dev/null || true)"
    PENDING="$(printf '%s' "$CI" | python3 -c 'import json,sys
r=json.load(sys.stdin)
print(len([x for x in r if x.get("status") not in ("completed",)]))' 2>/dev/null || echo 0)"
    if [[ -n "$BAD" ]]; then
      printf '%s\n' "$BAD" >&2
      die "CI is red on this commit. A tester should not be handed a build nothing vouched for.
   Fix it, or ship deliberately with:
     SHIP_WITHOUT_CI=1 make ship"
    elif [[ "${PENDING:-0}" != 0 ]]; then
      [[ "${SHIP_WITHOUT_CI:-0}" == 1 ]] || die "CI is still running on this commit ($PENDING run(s)). Wait for it, then ship — or:
     SHIP_WITHOUT_CI=1 make ship"
      say "CI still running, shipping anyway because SHIP_WITHOUT_CI=1"
    else
      say "CI is green on this commit"
    fi
  fi
else
  say "no gh here, so CI was not checked"
fi

say "building the tarball at ${HERE}"
tools/bundle.sh "$SITE/node0/get"
sign_tarball "$SITE/node0/get/planetai-node.tar.gz"

# The docs, from the same commit. `make lint` has already refused a page with a broken link or anchor
# (build_docs.py --check); this only renders. Into the site repo's docs/, which holds nothing else.
if [[ "${SHIP_WITHOUT_DOCS:-0}" == 1 ]]; then
  printf '\033[1;33m!!\033[0m SHIP_WITHOUT_DOCS=1: the docs site was not rebuilt. It still describes the last release it was built for.\n' >&2
else
  PY="$(docs_python)" || die "$NODOCS_MSG"
  "$PY" tools/build_learn.py --check >/dev/null || die "app/static/learn.json is not what docs/site says. make learn, commit, then ship."
  "$PY" tools/build_docs.py --out "$SITE/docs" >/dev/null || die "the docs site did not build. $PY tools/build_docs.py --check says why."
  say "docs site rebuilt at ${HERE}"
fi

# The site repo may hold work of its own. Only ever touch node0/get and docs/, and refuse if anything
# else is dirty.
OTHER="$(git -C "$SITE" status --porcelain -- . ':(exclude)node0/get' ':(exclude)docs' | head -5)"
[[ -z "$OTHER" ]] || { printf '%s\n' "$OTHER" >&2; die "the site repo has other uncommitted changes. Deal with those first; I will not sweep them into a release."; }
if [[ -n "$(git -C "$SITE" status --porcelain -- node0/get docs)" ]]; then
  say "committing the tarball and the docs into the site repo"
  git -C "$SITE" add node0/get docs
  git -C "$SITE" commit -q -m "node0/get + docs: tester tarball and docs site at ${HERE}"
  git -C "$SITE" push -q origin HEAD
else
  say "the site repo already has this tarball and these docs"
fi

# A second copy of the same bytes, somewhere with a provenance trail. planetai.fab.city is one Cloudflare
# bucket: it has no history a reader can check, and whoever can write to it can replace the tarball, the
# checksum and the signature together. A GitHub Release records who published it, when, and from which
# commit, and none of that can be quietly rewritten. The signature is what makes the two copies the same
# artefact rather than two things that look alike.
#
# A node can be pointed at it — PLANETAI_GET=https://github.com/fabcity/planetai-node/releases/download/<tag>
# — so this is a route out if the site is unreachable or not trusted, not only an audit trail.
# install-smoke.yml proves the stub reads it unchanged.
if [[ "$HERE" == v*  && "$HERE" != *-g* ]]; then
  if command -v gh >/dev/null 2>&1; then
    G="$SITE/node0/get"
    # VERSION goes too: the stub reads $GET/VERSION for the line under the logo, so a mirror without it
    # is a mirror that installs a node which cannot say what it is.
    FILES=("$G/planetai-node.tar.gz" "$G/SHA256" "$G/planetai-node.tar.gz.sig" "$G/VERSION")
    [[ "${PLANETAI_UNSIGNED:-0}" == 1 ]] && FILES=("$G/planetai-node.tar.gz" "$G/SHA256" "$G/VERSION")
    if gh release view "$HERE" >/dev/null 2>&1; then
      say "GitHub Release $HERE is already there — replacing its files"
      gh release upload "$HERE" "${FILES[@]}" --clobber \
        || die "could not upload to the GitHub Release $HERE. The site has the tarball; the mirror does not."
    else
      say "publishing the GitHub Release $HERE"
      gh release create "$HERE" --title "$HERE" \
        --notes "The node at ${HERE}. Verify before installing:

    ssh-keygen -Y verify -f tools/allowed_signers -I fabcity \\
      -n planetai-node -s planetai-node.tar.gz.sig < planetai-node.tar.gz

Install from here rather than the site:

    PLANETAI_GET=https://github.com/fabcity/planetai-node/releases/download/${HERE} \\
      bash -c \"\$(curl -fsSL planetai.fab.city/install)\"

SECURITY.md has the signer fingerprint and how to report something." \
        "${FILES[@]}" \
        || die "could not create the GitHub Release $HERE. The site has the tarball; the mirror does not."
    fi
    say "mirrored: https://github.com/fabcity/planetai-node/releases/tag/${HERE}"
  else
    printf '\033[1;33m!!\033[0m no gh here, so the GitHub Release was not published. The site is the only copy.\n' >&2
    printf '   When you have gh:  gh release create %s <the three files in %s>\n' "$HERE" "$SITE/node0/get" >&2
  fi
else
  say "${HERE} is not a tag, so no GitHub Release — only a tagged release is mirrored"
fi

if [[ $DEPLOY -eq 1 ]]; then
  say "deploying the site — this publishes planetai.fab.city (npx wrangler@4 deploy)"
  make -C "$SITE" deploy
  say "live: $(curl -fsSL "https://planetai.fab.city/node0/get/VERSION?cb=$RANDOM" 2>/dev/null || echo '(check by hand)')"
else
  say "not deployed. To publish:  make -C $SITE deploy"
fi
