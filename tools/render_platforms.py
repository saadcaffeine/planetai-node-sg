"""Render the floors table in docs/PLATFORMS.md from data/platform_floors.yml.

The page used to carry the numbers as prose, so the prose and the code could disagree — and did: the page
said "macOS 13+, install OrbStack" when OrbStack needs 14. Now one file holds the floors, this writes the
table, and `make lint` fails when the page has drifted from the data.

  python3 tools/render_platforms.py          rewrite the block
  python3 tools/render_platforms.py --check  fail if the block is stale
"""
import sys

import yaml

FLOORS, TARGET = "data/platform_floors.yml", "docs/PLATFORMS.md"
BEGIN = "<!-- BEGIN GENERATED: tools/render_platforms.py from data/platform_floors.yml -->"
END = "<!-- END GENERATED -->"


def rows(d: dict) -> str:
    r, lin, win, node = d["runtimes"], d["linux"], d["windows"], d["node"]
    ram, disk = node["min_ram_gb"], node["min_free_disk_gb"]
    colima_x86 = r["colima"].get("min_os_x86_64") or r["colima"]["min_os"]
    orb = r["orbstack"]["min_os"]
    # Linux first, macOS second, Windows third — a node's home is an always-on box, and on Linux the
    # floor does not move. That order is a decision (9 September 2026), not an accident of editing.
    out = [
        "| Machine | Minimum OS | Container runtime that installs there | RAM | Free disk |",
        "|---|---|---|---|---|",
        f"| **Ubuntu / Debian (amd64)**, *the first choice* | Ubuntu {lin['docker_engine_ubuntu']['min_os']} · "
        f"Debian {lin['docker_engine_debian']['min_os']} | Docker Engine, installed by the script | {ram} GB | {disk} GB |",
        f"| **Arch, and Omarchy on top of it (amd64)** | rolling | Docker from Arch's own repository, "
        f"installed by the script | {ram} GB | {disk} GB |",
        f"| **macOS, Apple Silicon (arm64)** | **{r['colima']['min_os']}** | OrbStack, Docker Desktop or "
        f"Colima. Colima reaches {r['colima']['min_os']} here. The database image is "
        f"native arm64. | {ram} GB | {disk} GB |",
        f"| **macOS, Intel (x86_64)** | **{colima_x86}** | ≥{orb}: all three · {colima_x86} to 13.7: "
        f"**Colima only** (`--vm-type vz`) · **below {colima_x86}: none, and Linux is the route** | "
        f"{ram} GB | {disk} GB |",
        f"| **Windows via WSL2 (amd64)** | {win['docker_desktop_wsl2']['min_os']} | Docker Desktop, WSL2 "
        f"backend | {win['docker_desktop_wsl2']['min_ram_gb']} GB | {disk} GB |",
        "| **Raspberry Pi OS 64-bit (arm64)** | not set | Docker Engine, installed by the script. The database "
        "image is published for arm64; **no Pi has run a node yet.** 8 GB and an SSD, never an "
        "SD card: see below. | 8 GB | not measured |",
        "",
        "### Where each number comes from",
        "",
        "Every floor below is the vendor's own current sentence, with the date it was read. "
        "`make check-floors` fails when any of them is more than "
        f"{d['meta']['staleness_days']} days old.",
        "",
        "| | Floor | The vendor's words | Read |",
        "|---|---|---|---|",
    ]
    for section in ("runtimes", "vm_hosts", "linux", "windows"):
        for _, e in d[section].items():
            says = " ".join(str(e["says"]).split())
            says = says[:150] + ("…" if len(says) > 150 else "")
            floor = e.get("min_os_x86_64") or e.get("min_os")
            out.append(f"| [{e['name']}]({e['source']}) | {floor} | {says} | {e['checked']} |")
    out += ["", f"*{label_note(d)}*"]
    return "\n".join(out)


def label_note(d: dict) -> str:
    dd = d["runtimes"]["docker_desktop_mac"]
    return ("Docker Desktop's floor moves on its own: " + " ".join(str(dd["says"]).split())
            + ", so it drops the oldest macOS each autumn whether or not anyone edits this page.")


text = open(TARGET).read()
if BEGIN not in text or END not in text:
    sys.exit(f"  x {TARGET} has no generated block. Add the {BEGIN} / {END} markers.")
head, rest = text.split(BEGIN, 1)
_, tail = rest.split(END, 1)
want = f"{BEGIN}\n{rows(yaml.safe_load(open(FLOORS)))}\n{END}"
have = f"{BEGIN}{rest.split(END, 1)[0]}{END}"

if "--check" in sys.argv:
    if have == want:
        print(f"  {TARGET} matches {FLOORS}")
        sys.exit(0)
    sys.exit(f"  x {TARGET} is out of date with {FLOORS}. Run: python3 tools/render_platforms.py")

open(TARGET, "w").write(head + want + tail)
print(f"  rendered the floors table into {TARGET}")
