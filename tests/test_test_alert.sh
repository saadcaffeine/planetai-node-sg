#!/usr/bin/env bash
# `planetai test-alert` on node #1 (5 Oct 2026) said "no alert fired in 90 seconds" while the alert fired and reached
# Telegram — twice. It decided by comparing how many rows GET /alerts returned before and after, and /alerts returns
# at most 50 by default, so on any node with 50+ alerts the count never grew; while it waited, the one-minute rule
# fired a second time. Runs the real cmd_test_alert lifted out of bin/planetai against a stubbed /alerts that already
# holds 50 alerts, offline, with sleep stubbed.
set -uo pipefail
cd "$(dirname "$0")/.."
fails=0
d="$(mktemp -d)"; trap 'rm -rf "$d"' EXIT

sed -n '/^cmd_test_alert() {/,/^}$/p' bin/planetai > "$d/fn.sh"
sed -n '/^json() {/,/; }$/p' bin/planetai >> "$d/fn.sh"
grep -q 'packs/_test' "$d/fn.sh" && grep -q '^json()' "$d/fn.sh" || { echo "  FAIL could not lift cmd_test_alert() and json()"; exit 1; }

mkdir -p "$d/node" "$d/bin"
printf '%s\n' '#!/bin/sh' 'exit 0' > "$d/bin/sleep"; chmod +x "$d/bin/sleep"
cat > "$d/stubs.sh" <<'S'
step() { :; }; say() { echo "SAY $*"; }; fail() { echo "FAIL $*"; exit 1; }; envget() { :; }; B=""; N=""
# /alerts: fifty old alerts, newest first; from the third call on, the run's own alert is on top, and fifty rows
# still come back — the length never changes, which is what fooled the old check.
api() {
  local n; n=$(( $(cat "$CALLS" 2>/dev/null || echo 0) + 1 )); echo "$n" > "$CALLS"; echo "$1" >> "$CALLS.urls"
  local rid; rid="$(sed -n 's/^- id: //p' packs/_test/rules.yml 2>/dev/null)"
  python3 - "$n" "$rid" <<'P'
import json, sys
n, rid = int(sys.argv[1]), sys.argv[2]
old = [{"id": 600 - i, "rule_id": "heat/heat_stress_now", "sensor_id": "sc-1"} for i in range(50)]
rows = ([{"id": 999, "rule_id": f"_test/{rid}", "sensor_id": "node"}] + old[:49]) if n >= 3 and rid else old
print(json.dumps(rows))
P
}
S

out="$(cd "$d/node" && CALLS="$d/calls" PATH="$d/bin:/usr/bin:/bin" bash -c '. "$1"; . "$2"; cmd_test_alert' _ "$d/stubs.sh" "$d/fn.sh" 2>&1)"
check() { if eval "$1"; then echo "  ok  $2"; else echo "  FAIL $2"; echo "$out" | sed 's/^/      /'; fails=$((fails+1)); fi; }
check 'grep -q "SAY it fired. Alert #999" <<<"$out"' "with 50+ alerts already stored, the run's own alert is found (#999)"
check '! grep -q "^FAIL" <<<"$out"' "it does not report 'no alert fired'"
check '[[ ! -d "$d/node/packs/_test" ]]' "the temporary rule is removed"
check '[[ "$(cat "$d/calls")" -le 4 ]]' "it stops polling as soon as the alert is seen ($(cat "$d/calls") calls), so the rule cannot fire twice"
echo "test-alert: $([[ $fails == 0 ]] && echo 'finds its own alert on a node with 50+ alerts' || echo "$fails failed")"
[[ $fails == 0 ]]
