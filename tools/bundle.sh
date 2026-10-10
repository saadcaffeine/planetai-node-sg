#!/usr/bin/env bash
# Build the tarball the website serves, so beta testers can install without access to the repository.
#   tools/bundle.sh [outdir]        default: ../planetai/node0/get
# Excludes git history, secrets, local state and the developer's own tooling.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
OUT="${1:-../planetai/node0/get}"
VER="$(git describe --tags --always 2>/dev/null || echo dev)"
mkdir -p "$OUT"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/planetai-node"
# Everything git tracks, minus what a tester must not receive or does not need. docs/design/ is the
# whole of it now rather than just its audit/: it holds the review screenshots, and eight full-page
# JPEGs of a 9800px page is close to two megabytes on a download somebody is doing over a phone
# hotspot in Ungasan. tools/shots.* goes with them — it needs playwright, which is not here.
# docs/archive/ is history for contributors, not a page a node serves.
git ls-files -z | grep -zvE '^(\.github/|tools/(package|release|bundle)\.sh|tools/(check_|shots\.)|tests/|docs/design/|docs/archive/)' \
  | xargs -0 -I{} cp --parents {} "$TMP/planetai-node/" 2>/dev/null \
  || git ls-files | grep -vE '^(\.github/|tools/(package|release|bundle)\.sh|tools/(check_|shots\.)|tests/|docs/design/|docs/archive/)' \
     | while read -r f; do mkdir -p "$TMP/planetai-node/$(dirname "$f")"; cp "$f" "$TMP/planetai-node/$f"; done
echo "$VER" > "$TMP/planetai-node/VERSION"
mkdir -p "$TMP/planetai-node/out" && cp out/.gitkeep "$TMP/planetai-node/out/" 2>/dev/null || true
# macOS's tar records Apple's extended attributes as pax headers, and GNU tar on Linux prints a warning
# for every one of them: Lucas saw several hundred lines of "tar: Ignoring unknown extended header keyword
# 'LIBARCHIVE.xattr.com.apple.quarantine'" scroll past before his install could start. 75 of them were in
# the shipped tarball. Strip the attributes, then tell tar not to record any it still finds. The flags
# differ between bsdtar and GNU tar, so try and fall back rather than assume.
command -v xattr >/dev/null && xattr -cr "$TMP/planetai-node" 2>/dev/null || true
COPYFILE_DISABLE=1 tar --no-xattrs --no-mac-metadata -czf "$OUT/planetai-node.tar.gz" -C "$TMP" planetai-node 2>/dev/null \
  || COPYFILE_DISABLE=1 tar --no-xattrs -czf "$OUT/planetai-node.tar.gz" -C "$TMP" planetai-node 2>/dev/null \
  || COPYFILE_DISABLE=1 tar czf "$OUT/planetai-node.tar.gz" -C "$TMP" planetai-node
# A tester should never see that wall again: refuse to ship a tarball that still carries them.
if gzip -dc "$OUT/planetai-node.tar.gz" | grep -qa 'LIBARCHIVE.xattr'; then
  rm -f "$OUT/planetai-node.tar.gz"
  echo "REFUSING: the tarball still carries Apple extended attributes, which make GNU tar warn on every file"
  exit 1
fi
tar tzf "$OUT/planetai-node.tar.gz" | grep -qE '(^|/)\.(git|env)(/|$)' && { echo "REFUSING: bundle contains .git or .env"; rm -f "$OUT/planetai-node.tar.gz"; exit 1; }
printf '%s\n' "$VER" > "$OUT/VERSION"
shasum -a 256 "$OUT/planetai-node.tar.gz" | awk '{print $1}' > "$OUT/SHA256"
echo "$OUT/planetai-node.tar.gz  ($VER, $(du -h "$OUT/planetai-node.tar.gz" | cut -f1), $(tar tzf "$OUT/planetai-node.tar.gz" | wc -l | tr -d ' ') files)"
