#!/usr/bin/env bash
# `planetai radio` runs through the ~/.local/bin symlink on every node. It once looked for tools/radio.py next to
# the link (~/.local/tools/), so the command failed on node #1 after its packages were installed (17 Oct 2026).
set -euo pipefail
cd "$(dirname "$0")/.."
t="$(mktemp -d)"; trap 'rm -rf "$t"' EXIT
ln -s "$PWD/bin/planetai" "$t/planetai"; mkdir "$t/py"
# a python3 that has the packages and reports which file it was asked to run
printf '#!/bin/sh\ncase "$*" in *"import meshtastic"*) exit 0;; esac\n[ -f "$1" ] && echo "radio.py at $1" || echo "missing: $1"\n' > "$t/py/python3"
chmod +x "$t/py/python3"
out="$(PATH="$t/py:$PATH" "$t/planetai" radio --help)"
[[ "$out" == "radio.py at $PWD/tools/radio.py" ]] || { echo "  x planetai radio through a symlink ran: $out"; exit 1; }
echo "  ok   planetai radio, run through a symlink, finds the node's tools/radio.py"
grep -q 'python3 -m pip install --user' bin/planetai || { echo "  x the hint must install for the python3 that runs radio.py"; exit 1; }
echo "  ok   its install hint is python3 -m pip, for the same interpreter"
# The region comes from NODE_CITY in .env, whose shipped line carries a comment. radio.py once read the comment as
# part of the city, found no region and fell back to EU_868: an 868 MHz fleet for node #1 in Bali (17 Oct 2026).
r="$t/root"; mkdir -p "$r"
printf 'NODE_NAME=testnode\nNODE_CITY=bali                         # pilot key used in Index cells: bali | barcelona\n' > "$r/.env"
PLANETAI_ROOT="$r" python3 tools/radio.py init >/dev/null
grep -q 'SG_923' "$r/config/radio/fleet.yaml" || { echo "  x a commented NODE_CITY=bali did not give SG_923"; exit 1; }
echo "  ok   NODE_CITY=bali with its shipped comment gives SG_923, Indonesia's band"
printf 'NODE_NAME=testnode\nNODE_CITY=atlantis\n' > "$r/.env"; rm -rf "$r/config"
if PLANETAI_ROOT="$r" python3 tools/radio.py init >/dev/null 2>"$t/err"; then echo "  x an unknown city got a region"; exit 1; fi
grep -q 'no radio region' "$t/err" || { echo "  x an unknown city must say to pass --region"; cat "$t/err"; exit 1; }
echo "  ok   a city with no known region refuses and asks for --region, never guesses"
# `planetai radio` on its own is the guide: every step in order and the one command that comes next. A node that
# only had the fleet once read `Next: planetai radio provision …` with no idea that a broker came first.
printf 'NODE_NAME=testnode\nNODE_CITY=bali\n' > "$r/.env"; rm -rf "$r/config"
# the guide reads whether the packages import; give it stubs so the steps after the packages are what is tested
mkdir -p "$t/stub/meshtastic" "$t/stub/paho/mqtt" "$t/empty"; : > "$t/stub/meshtastic/__init__.py"; : > "$t/stub/paho/__init__.py"; : > "$t/stub/paho/mqtt/__init__.py"
g="$(PYTHONPATH="$t/stub" PLANETAI_ROOT="$r" python3 tools/radio.py)"
grep -q '^Next: planetai meshtastic' <<<"$g" || { echo "  x with no broker the guide's next step must be the broker:"; echo "$g"; exit 1; }
printf 'NODE_NAME=testnode\nNODE_CITY=bali\nMQTT_PASS=x\nCOMPOSE_PROFILES=mqtt\n' > "$r/.env"
g="$(PYTHONPATH="$t/stub" PLANETAI_ROOT="$r" python3 tools/radio.py)"
grep -q '^Next: planetai radio init' <<<"$g" || { echo "  x with a broker and no fleet the next step must be init:"; echo "$g"; exit 1; }
PLANETAI_ROOT="$r" python3 tools/radio.py init >/dev/null
g="$(PYTHONPATH="$t/stub" PLANETAI_ROOT="$r" python3 tools/radio.py)"
grep -q 'provision gateway-host' <<<"$g" && grep -q '✓ 3. The fleet: region SG_923' <<<"$g" \
  || { echo "  x with a fleet the next step must be the gateway radio:"; echo "$g"; exit 1; }
echo "  ok   planetai radio on its own walks broker → fleet → gateway and names the next command"
# and without the packages, step 1 is the pip line for this very python3 (no stub on the path, and none installed
# in a clean interpreter: -S skips site-packages, PYTHONNOUSERSITE the user's)
g="$(PYTHONNOUSERSITE=1 PLANETAI_ROOT="$r" python3 -S tools/radio.py 2>&1 || true)"
grep -q '^Next: python3 -m pip install --user .*meshtastic paho-mqtt' <<<"$g" || { echo "  x without the packages the next step must install them:"; echo "$g"; exit 1; }
echo "  ok   without the packages, the guide's first step is the pip line for its own python3"
# radio.py runs meshtastic as a module of its own python3. It once looked for the `meshtastic` script, which a Mac's
# `pip install --user` puts on nobody's PATH, and called that a radio which "did not come back after a reboot".
c="$(PYTHONPATH="$t/stub" python3 -c 'import sys; sys.argv=["x"]; sys.path.insert(0,"tools"); import radio; print(radio.meshtastic_cli())')"
[[ "$c" == *"'-m', 'meshtastic'"* ]] || { echo "  x meshtastic must run as python3 -m meshtastic, got: $c"; exit 1; }
if PYTHONNOUSERSITE=1 python3 -S -c 'import sys; sys.path.insert(0,"tools"); import radio; radio.wait_ready("/dev/null", tries=1)' 2>"$t/err"; then
  echo "  x wait_ready passed with no meshtastic"; exit 1; fi
grep -q 'not installed' "$t/err" || { echo "  x a missing meshtastic must say so, not that the radio did not come back:"; cat "$t/err"; exit 1; }
echo "  ok   meshtastic runs as python3 -m meshtastic, and a missing package is said as such"
# Once the gateway runs as a service, its port is taken. The guide once offered the gateway's own port for the next
# radio, which would have rewritten the gateway as a sensor (node #1, 18 Oct).
h="$t/home"; mkdir -p "$h/Library/LaunchAgents" "$h/.config/systemd/user"
for f in "$h/Library/LaunchAgents/city.fab.planetai.radio.plist" "$h/.config/systemd/user/planetai-radio.service"; do
  echo "<string>/dev/cu.usbmodemGATE</string> --port /dev/cu.usbmodemGATE" > "$f"; done
g="$(FAKE_HOME="$h" PYTHONPATH="$t/stub" PLANETAI_ROOT="$r" python3 -c '
import os, sys; from pathlib import Path; sys.path.insert(0, "tools"); import radio
radio.Path.home = staticmethod(lambda: Path(os.environ["FAKE_HOME"]))   # the service file, without hiding user-site packages
radio.usb_radios = lambda: [("/dev/cu.usbmodemGATE", "seeed-xiao-s3")]
f = radio.load_fleet(); f.setdefault("radios", []).append({"id": "!1", "role": "gateway-host", "name": "gw", "short": "GW", "provisioned": "x"}); radio.save_fleet(f)
radio.guide()')"
grep -q 'keep it plugged in' <<<"$g" && ! grep -q 'provision sensor .*--port /dev/cu.usbmodemGATE' <<<"$g" \
  || { echo "  x the guide offered the gateway's port for another radio:"; echo "$g"; exit 1; }
echo "  ok   with the gateway running, the guide never offers its port for the next radio"
# `--fixed -8.8,115.1`: a south latitude starts with a minus, and argparse once took it for an option and stopped at
# "expected one argument". Every radio in Bali has one (19 Oct 2026). Accepted, the command reaches its next question.
# Python 3.12+ argparse accepts it already; node #1 runs Apple's 3.9, so the test puts 3.9's rule back first.
for fx in "--fixed -8.81902,115.16736" "--fixed=-8.81902,115.16736" "--fixed -8.81902,115.16736,12"; do
  # shellcheck disable=SC2086
  if PLANETAI_ROOT="$r" python3 - provision sensor "Mesh test" MTU $fx >"$t/out" 2>&1 <<'PY'
import argparse, re, sys
sys.path.insert(0, "tools")
init = argparse._ActionsContainer.__init__
def as_39(self, *a, **k):
    init(self, *a, **k)
    self._negative_number_matcher = re.compile(r"^-\d+$|^-\d*\.\d+$")   # Python 3.9's
argparse._ActionsContainer.__init__ = as_39
import radio
radio.main(sys.argv[1:])
PY
  then echo "  x provision with no port passed"; exit 1; fi
  grep -q -- '--port is needed' "$t/out" || { echo "  x $fx did not parse:"; cat "$t/out"; exit 1; }
done
if PLANETAI_ROOT="$r" python3 tools/radio.py provision sensor "Mesh test" MTU --fixed -8.8 >"$t/out" 2>&1; then echo "  x --fixed with one number passed"; exit 1; fi
grep -q -- '--fixed wants LAT,LON' "$t/out" || { echo "  x a half coordinate must say what --fixed wants:"; cat "$t/out"; exit 1; }
echo "  ok   --fixed takes a south latitude as written (-8.8,115.1), and a half coordinate says what it wants"
