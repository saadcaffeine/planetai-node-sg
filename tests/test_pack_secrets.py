"""A pack's secrets are treated like the node's own tokens: masked once saved, even to the admin token.

Every key a pack declared used to reach Set up with `secret: False`, so a FIRMS key or a camera bridge token was
published as plain text to anyone holding the admin token, and through the agent's settings tool, which calls
describe(unlocked=True). A pack now lists its secret keys under `secrets:` in its pack.yaml. No network, no database:
the settings rows come from the environment, as they do before the table exists.
Run: PYTHONPATH=app python3 tests/test_pack_secrets.py
"""
import json
import logging
import os
import re
import tempfile
from pathlib import Path

d = Path(tempfile.mkdtemp())
os.environ.update(PACKS_DIR=str(d), DATABASE_URL="postgresql://x:x@127.0.0.1:1/x",
                  CAMERA_WYZE_BRIDGE_TOKEN="supersecret-bridge-token", CAMERA_WYZE_BRIDGE_URL="http://192.168.1.20:5000",
                  COAST_MAX_KM="30")

import settings  # noqa: E402

said = []
logging.getLogger("planetai.settings").addHandler(type("H", (logging.Handler,), {"emit": lambda self, r: said.append(r.getMessage())})())


def pack(name, body):
    (d / name).mkdir(exist_ok=True)
    (d / name / "pack.yaml").write_text(body)


def rows(unlocked):
    settings._cache["at"] = 0
    return {r["key"]: r for r in settings.describe(unlocked=unlocked)["runtime"]}


pack("cam-test", "id: cam-test\nenv:\n"
     '  - "# cam-test: the bridge\'s local address"\n  - "CAMERA_WYZE_BRIDGE_URL="\n'
     '  - "# cam-test: only if the bridge API is protected"\n  - "CAMERA_WYZE_BRIDGE_TOKEN="\n'
     '  - "COAST_MAX_KM=30"\n'
     "secrets: [CAMERA_WYZE_BRIDGE_TOKEN, COAST_MAX_KM, NEVER_DECLARED]\n")

for unlocked in (True, False):
    r = rows(unlocked)
    tok = r["CAMERA_WYZE_BRIDGE_TOKEN"]
    assert tok["secret"] is True and tok["value"] == "•••• set" and tok["set"] is True, tok
    assert tok["pack"] == "cam-test" and tok["group"] == "packs", tok
    assert "supersecret" not in json.dumps(settings.describe(unlocked=unlocked)), "the token's value is in /settings"
print("  a pack's secret is masked in /settings and in the agent's settings tool, with or without the admin token")

r = rows(True)
assert r["CAMERA_WYZE_BRIDGE_URL"]["secret"] is False and r["CAMERA_WYZE_BRIDGE_URL"]["value"] == "http://192.168.1.20:5000"
assert rows(False)["CAMERA_WYZE_BRIDGE_URL"]["value"] != "http://192.168.1.20:5000"
print("  a key the pack does not list is shown to the admin token and masked to anyone else, as before")

assert r["COAST_MAX_KM"]["secret"] is True and r["COAST_MAX_KM"]["value"] == "•••• set", r["COAST_MAX_KM"]
assert "30" != r["COAST_MAX_KM"]["value"]
print("  a node setting a pack also declares and lists as secret is masked too, never less private than the pack asks")

assert any("NEVER_DECLARED" in m and "cam-test" in m for m in said), said
print("  a secret the pack lists but never declares is said in the log")

pack("cam-test", "id: cam-test\nenv:\n  - \"CAMERA_WYZE_BRIDGE_TOKEN=\"\nsecrets: CAMERA_WYZE_BRIDGE_TOKEN\n")
r = rows(True)
assert r["CAMERA_WYZE_BRIDGE_TOKEN"]["secret"] is False
print("  secrets: that is not a list is ignored rather than guessed at")
# Every pack this repo ships: a key whose name or words say token, key or password is listed under secrets:.
# XIAOMI_PURIFIERS carried device tokens and was shown in full to the admin token until it was listed.
# Exempt by name, with the reason: these say "key" because they point at the key, they are not it.
NOT_SECRET = {"EE_PROJECT": "a Cloud project id", "EE_SERVICE_ACCOUNT": "an account's address",
              "EE_KEY_FILE": "the path to the key file, not its contents"}
os.environ["PACKS_DIR"] = str(Path(__file__).resolve().parents[1] / "packs")
shipped = settings.pack_settings()
assert shipped, "no shipped packs were read"
assert NOT_SECRET.keys() <= {r["key"] for r in shipped}, "an exemption names a key no pack declares any more"
leaks = [f'{r["pack"]}: {r["key"]}' for r in shipped if r["key"] not in NOT_SECRET and not r["secret"]
         and re.search(r"token|key|password", f'{r["key"]} {r["help"]}', re.I)]
assert not leaks, f"these shipped pack keys look like secrets and are not listed under secrets: {leaks}"
print("  every shipped pack key that says token, key or password is listed under secrets:")
print("pack secrets: masked like the node's own tokens, everywhere describe() answers")
