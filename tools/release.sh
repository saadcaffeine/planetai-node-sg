#!/usr/bin/env bash
# Cut a release from the development machine. Nodes never run this.
#   tools/release.sh 0.4.5
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
V="${1:?usage: tools/release.sh <version>   e.g. 0.4.5}"

say(){ printf '\033[1;32m>>\033[0m %s\n' "$*"; }
die(){ printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }

[[ -n "$(git status --porcelain)" ]] && die "working tree is dirty — commit first, then release"
grep -q "^## v${V}" CHANGELOG.md || die "CHANGELOG.md has no '## v${V}' section. Say what changed and why."
git rev-parse "v${V}" >/dev/null 2>&1 && die "tag v${V} already exists"

# The signing key, checked BEFORE the tag is cut. A checksum served from the same origin as the tarball
# proves only that the bytes did not rot on the way: whoever can write to node0/get writes both files,
# and every node takes it on the next `planetai update`. The signature is the half that names the sender.
#
# ship.sh owns the check and does the signing; this asks it the question early, because the next two
# steps tag and push. Discovering a missing key after `git push --tags` leaves a public tag naming a
# release nobody can publish.
tools/ship.sh --check-key || exit 1
# The docs site is rebuilt by ship.sh too, and needs the markdown package. Same reason, same place.
tools/ship.sh --check-docs || exit 1

# And the site repo, for exactly the same reason as the key above. ship.sh refuses to publish into a
# site repo that has uncommitted work of its own — "I will not sweep them into a release" — but it
# only finds out at step four, and steps two and three have already tagged and pushed by then. That
# leaves a public tag naming a release nobody can publish, which is the failure the key check exists
# to prevent, arriving by a different door. Found 21 September 2026 while cutting v0.67, with the
# site repo mid-rebuild from a parallel session.
SITE_="${PLANETAI_SITE_REPO:-../planetai}"
if [[ -d "$SITE_/.git" ]]; then
  OTHER_="$(git -C "$SITE_" status --porcelain -- . ':(exclude)node0/get' ':(exclude)docs' | head -5)"
  [[ -z "$OTHER_" ]] || { printf '%s\n' "$OTHER_" >&2
    die "the site repo ($SITE_) has uncommitted work that is not node0/get or docs/, so ship.sh will refuse
   to publish — and it refuses AFTER this script has tagged and pushed. Deal with those first."; }
fi

# And the programme page: it states this release's number, its pack and language counts and node #1's
# rho, and on 23 Sep 2026 it was eight releases behind with every gate green (R25). Refuse to tag while
# it describes another release; the fix is a commit in the site repo, before the tag, not after.
if [[ -d "$SITE_/.git" ]]; then
  python3 tools/check_site.py --site "$SITE_" --version "v${V}" \
    || die "the programme page does not describe v${V}: update $SITE_/web/src/data.js, run make root and make staging there, commit, then release."
fi

say "lint + tests"
make lint >/dev/null && make test >/dev/null || die "checks failed"

say "tagging v${V}"
git tag -a "v${V}" -m "v${V}"
git push origin main --tags

say "building the tarball, committing it in the site repo, deploying"
tools/ship.sh

# What a node downloads, all three of it. ship.sh built and signed them; this is the receipt.
GET="${PLANETAI_SITE_REPO:-../planetai}/node0/get"
for f in planetai-node.tar.gz SHA256 planetai-node.tar.gz.sig; do
  [[ "$f" == *.sig && "${PLANETAI_UNSIGNED:-0}" == 1 ]] && continue
  [[ -s "$GET/$f" ]] || die "$GET/$f is missing or empty after the build. Nothing was released."
done

say "released v${V}, signed. Nodes update with:  ./update.sh"
