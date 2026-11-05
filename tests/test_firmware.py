"""app/firmware.py: the node's copy of the firmware the workbench flashes, so it flashes with no internet.
A fake publisher stands in for planetai.fab.city and Making Sense Bali; nothing here reaches the network.

    PYTHONPATH=app python3 tests/test_firmware.py
"""
import hashlib
import json
import tempfile
from pathlib import Path

import firmware

MT, BY = firmware.SOURCES["meshtastic"], firmware.SOURCES["bayu"]


def publisher(bayu_version="v6-a", bad_sum=False, bayu_path=None, bayu_down=False):
    fw = b"factory-bin"
    sums = f"{hashlib.sha256(b'other' if bad_sum else fw).hexdigest()}  fw-xiao.factory.bin\n" \
           f"{hashlib.sha256(b'uf2').hexdigest()}  fw-l1.uf2\n"
    files = {
        MT + "files.json": json.dumps({"version": "2.7", "boards": {
            "xiao": {"manifest": "manifest-xiao.json", "factory": "fw-xiao.factory.bin"},
            "l1": {"uf2": "fw-l1.uf2"}}}).encode(),
        MT + "2.7/SHA256SUMS": sums.encode(),
        MT + "manifest-xiao.json": json.dumps({"builds": [{"parts": [{"path": "2.7/fw-xiao.factory.bin", "offset": 0}]}]}).encode(),
        MT + "2.7/fw-xiao.factory.bin": fw,
        MT + "2.7/fw-l1.uf2": b"uf2",
        BY + "manifest.json": json.dumps({"builds": [{"parts": [
            {"path": bayu_path or f"{bayu_version}/esp32s3/app.bin", "offset": 65536}]}]}).encode(),
        BY + f"{bayu_version}/esp32s3/app.bin": b"bayu-" + bayu_version.encode(),
    }
    asked = []

    def get(u):
        asked.append(u)
        if bayu_down and u.startswith(BY):
            raise OSError("no route to makingsense.fablabbali.com")
        if u not in files:
            raise FileNotFoundError(u)
        return files[u]
    return get, asked


root = Path(tempfile.mkdtemp()) / "firmware"

# first run: every file the indexes name, and the indexes
get, asked = publisher()
assert firmware.mirror(root, get) == {"meshtastic": 2, "bayu": 1}
for f in ("meshtastic/files.json", "meshtastic/manifest-xiao.json", "meshtastic/2.7/fw-xiao.factory.bin",
          "meshtastic/2.7/fw-l1.uf2", "meshtastic/2.7/SHA256SUMS", "bayu/manifest.json", "bayu/v6-a/esp32s3/app.bin"):
    assert (root / f).is_file(), f"{f} was not kept"
print("mirror: every file the indexes name is kept, and the indexes")

# second run: a file under a version folder is never fetched again
get, asked = publisher()
assert firmware.mirror(root, get) == {"meshtastic": 0, "bayu": 0}
assert not any(u.endswith((".bin", ".uf2")) for u in asked), asked
print("mirror: a file already here is not fetched again")

# a new Bayu build: the new one is kept, the old one goes
get, _ = publisher(bayu_version="v6-b")
firmware.mirror(root, get)
assert (root / "bayu/v6-b/esp32s3/app.bin").read_bytes() == b"bayu-v6-b"
assert not (root / "bayu/v6-a").exists(), "an old build must not pile up"
print("mirror: a new build replaces the old one")

# a binary that does not match SHA256SUMS is refused, and what was kept stays
fresh = Path(tempfile.mkdtemp()) / "firmware"
get, _ = publisher(bad_sum=True)
try:
    firmware.mirror(fresh, get)
    raise AssertionError("a file that does not match its SHA256SUMS line was kept")
except RuntimeError as e:
    assert "SHA256SUMS" in str(e), e
assert not (fresh / "meshtastic/2.7/fw-xiao.factory.bin").exists() and not (fresh / "meshtastic/files.json").exists()
assert (fresh / "bayu/manifest.json").is_file(), "one publisher failing must not stop the other"
print("mirror: a file that does not match SHA256SUMS is refused; the other publisher still runs")

# a path that climbs out of its folder is refused before anything is written
for bad in ("../../etc/x", "/etc/x"):
    get, _ = publisher(bayu_path=bad)
    try:
        firmware.mirror(Path(tempfile.mkdtemp()) / "firmware", get)
        raise AssertionError(f"{bad} was accepted")
    except RuntimeError as e:
        assert "outside its folder" in str(e), e
print("mirror: a path outside its folder is refused")

# a publisher that cannot be reached keeps what this node had
get, _ = publisher(bayu_version="v6-b", bayu_down=True)
try:
    firmware.mirror(root, get)
    raise AssertionError("an unreachable publisher must be reported")
except RuntimeError as e:
    assert e.args[0].startswith("firmware not refreshed: bayu"), e
assert (root / "bayu/v6-b/esp32s3/app.bin").is_file() and (root / "bayu/manifest.json").is_file()
print("mirror: an unreachable publisher keeps the copy this node had")
print("all firmware checks passed")
