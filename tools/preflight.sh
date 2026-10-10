#!/usr/bin/env bash
# Everything the node needs from a machine, checked before it asks anybody anything.
#
#   curl -fsSL planetai.fab.city/preflight | bash     # nothing installed yet
#   planetai preflight [--json]                        # on a node
#
# Self-contained on purpose: it is fetched and run on its own, before the code is downloaded, so it may not
# assume the repository, .env, docker, python or anything else is there — a Mac with no Xcode Command Line
# Tools has no python3 either. It reads; it never writes, never sudos, never installs, never asks.
#
# Every fact about the machine comes from a probe that an environment variable can replace, so the whole
# matrix runs from fixtures in tests/ without owning twelve Macs:
#   PF_OS PF_OS_VERSION PF_ARCH PF_HW_MODEL PF_MEM_BYTES PF_DISK_FREE_KB PF_DISK_MOUNT
#   PF_APPS PF_DOCKER_RUNNING PF_HAVE (a space-separated list of commands to pretend exist)
#   PF_IS_LAPTOP PF_BATTERY PF_HAS_ETHERNET PF_EGRESS_OK
#
# The version floors are generated into this file from data/platform_floors.yml, where each one carries the
# vendor's URL and the date somebody read it. `make lint` fails if the two have drifted.
#
# Exit codes, because two callers depend on them:
#   0  every row passed — go
#   1  something failed that this tester can fix; each ✗ carries the line that fixes it
#   2  no container runtime can be installed on this OS version. Not an error: an answer.
#      The installer prints the verdict and exits 0 on this one.
set -uo pipefail        # not -e: a failing check is the point

JSON=0; [[ "${1:-}" == "--json" ]] && JSON=1
G=$'\033[32m'; R=$'\033[31m'; Y=$'\033[33m'; D=$'\033[2m'; B=$'\033[1m'; N=$'\033[0m'
[[ -t 1 ]] || { G=""; R=""; Y=""; D=""; B=""; N=""; }

# ---- BEGIN GENERATED FLOORS
# From data/platform_floors.yml, where each floor carries its vendor URL and the date it was read.
# Do not edit by hand. Regenerate: python3 tools/gen_floors.py   Verify: make lint
FLOORS_CHECKED=2026-09-08
RUNTIMES_orbstack_name="OrbStack"
RUNTIMES_orbstack_min_os="14.0"
RUNTIMES_orbstack_min_os_x86_64="14.0"
RUNTIMES_orbstack_install="gui"
RUNTIMES_orbstack_source="https://docs.orbstack.dev/faq"
RUNTIMES_docker_desktop_mac_name="Docker Desktop"
RUNTIMES_docker_desktop_mac_min_os="14.0"
RUNTIMES_docker_desktop_mac_min_os_x86_64="14.0"
RUNTIMES_docker_desktop_mac_install="gui"
RUNTIMES_docker_desktop_mac_source="https://docs.docker.com/desktop/setup/install/mac-install/"
RUNTIMES_colima_name="Colima"
RUNTIMES_colima_min_os="13.0"
RUNTIMES_colima_min_os_x86_64="13.5"
RUNTIMES_colima_install="binary"
RUNTIMES_colima_source="https://github.com/abiosoft/colima/blob/main/docs/FAQ.md#are-older-macos-versions-supported"
VM_HOSTS_utm_name="UTM"
VM_HOSTS_utm_min_os="11.3"
VM_HOSTS_utm_min_os_x86_64="11.3"
VM_HOSTS_utm_install="binary"
VM_HOSTS_utm_source="https://github.com/utmapp/UTM/releases/tag/v5.0.5"
VM_HOSTS_vmware_fusion_13_0_name="VMware Fusion 13.0"
VM_HOSTS_vmware_fusion_13_0_min_os="12.0"
VM_HOSTS_vmware_fusion_13_0_min_os_x86_64="12.0"
VM_HOSTS_vmware_fusion_13_0_install="gui"
VM_HOSTS_vmware_fusion_13_0_source="https://techdocs.broadcom.com/us/en/vmware-cis/desktop-hypervisors/fusion-pro/13-0/using-vmware-fusion/getting-started-with-vmware-fusion/system-requirements-for-vmware-fusion.html"
VM_HOSTS_virtualbox_name="VirtualBox"
VM_HOSTS_virtualbox_min_os="13.0"
VM_HOSTS_virtualbox_min_os_x86_64="13.0"
VM_HOSTS_virtualbox_install="gui"
VM_HOSTS_virtualbox_source="https://www.virtualbox.org/manual/topics/installation.html"
VM_HOSTS_multipass_name="Multipass"
VM_HOSTS_multipass_min_os="14.0"
VM_HOSTS_multipass_min_os_x86_64="14.0"
VM_HOSTS_multipass_install="gui"
VM_HOSTS_multipass_source="https://canonical.com/multipass/docs/latest/how-to-guides/install-multipass/"
MAC_LAST_MONTEREY="12.7.6"
mac_ceiling() {   # identifier -> last macOS|marketing name, or empty when unknown
  case "$1" in
    "MacBookPro11,4") printf '%s|%s' "12.7.6" "MacBook Pro (Retina, 15-inch, Mid 2015)";;
    "MacBookPro11,5") printf '%s|%s' "12.7.6" "MacBook Pro (Retina, 15-inch, Mid 2015)";;
    "MacBookPro12,1") printf '%s|%s' "12.7.6" "MacBook Pro (Retina, 13-inch, Early 2015)";;
    "MacBookPro13,1") printf '%s|%s' "12.7.6" "MacBook Pro (13-inch, 2016, Two Thunderbolt 3 ports)";;
    "MacBookPro13,2") printf '%s|%s' "12.7.6" "MacBook Pro (13-inch, 2016, Four Thunderbolt 3 ports)";;
    "MacBookPro13,3") printf '%s|%s' "12.7.6" "MacBook Pro (15-inch, 2016)";;
    "MacBookPro14,1") printf '%s|%s' "13.7.6" "MacBook Pro (13-inch, 2017, Two Thunderbolt 3 ports)";;
    "MacBookPro14,2") printf '%s|%s' "13.7.6" "MacBook Pro (13-inch, 2017, Four Thunderbolt 3 ports)";;
    "MacBookPro14,3") printf '%s|%s' "13.7.6" "MacBook Pro (15-inch, 2017)";;
    *) printf '';;
  esac
}
ASSET_utm_dmg_url="https://github.com/utmapp/UTM/releases/download/v4.7.5/UTM.dmg"
ASSET_utm_dmg_version="v4.7.5"
ASSET_omarchy_iso_url="https://iso.omarchy.org/omarchy-4.0.3.iso"
ASSET_omarchy_iso_version="4.0.3"
ASSET_ubuntu_server_iso_url="https://releases.ubuntu.com/24.04/ubuntu-24.04.4-live-server-amd64.iso"
ASSET_ubuntu_server_iso_version="24.04.4"
LINUX_ubuntu_min="22.04"
LINUX_debian_min="11"
LINUX_fedora_min="43"
WINDOWS_min="10 22H2 (build 19045)"
WINDOWS_min_ram_gb=8
NODE_min_ram_gb=4
NODE_min_free_disk_gb=3
# ---- END GENERATED FLOORS

# Compare two dotted versions: ver_ge 12.7.6 13.5 is false. Pure bash — no sort -V, whose -V flag is not
# on every platform, and no python.
ver_ge() {
  local a="$1" b="$2" i x y
  local -a A B; IFS=. read -r -a A <<< "$a"; IFS=. read -r -a B <<< "$b"
  for i in 0 1 2; do
    x="${A[i]:-0}"; y="${B[i]:-0}"; x="${x//[^0-9]/}"; y="${y//[^0-9]/}"
    (( 10#${x:-0} > 10#${y:-0} )) && return 0
    (( 10#${x:-0} < 10#${y:-0} )) && return 1
  done
  return 0
}

# ---------------------------------------------------------------- probes. Each one is the machine, or the
# fixture standing in for it. Nothing below this line calls uname, sw_vers, sysctl or df directly.
probe()          { local var="$1"; shift; if [[ -n "${!var:-}" ]]; then printf '%s' "${!var}"; else "$@" 2>/dev/null || true; fi; }
probe_os()       { probe PF_OS uname -s; }
probe_os_ver()   { probe PF_OS_VERSION sw_vers -productVersion; }
probe_arch()     { probe PF_ARCH uname -m; }
probe_model()    { probe PF_HW_MODEL sysctl -n hw.model || /usr/sbin/sysctl -n hw.model; }
probe_apps()     { printf '%s' "${PF_APPS:-/Applications}"; }
probe_pretty()   { probe PF_OS_PRETTY bash -c '. /etc/os-release 2>/dev/null && echo "${PRETTY_NAME:-Linux}"'; }
# have(): PF_HAVE lets a fixture say which commands exist without putting stubs on PATH
have() { [[ -n "${PF_HAVE+x}" ]] && { [[ " $PF_HAVE " == *" $1 "* ]]; return; }; command -v "$1" >/dev/null 2>&1; }
docker_running() { [[ -n "${PF_DOCKER_RUNNING:-}" ]] && { [[ "$PF_DOCKER_RUNNING" == 1 ]]; return; }; have docker && docker info >/dev/null 2>&1; }
probe_mem_bytes() {
  [[ -n "${PF_MEM_BYTES:-}" ]] && { printf '%s' "$PF_MEM_BYTES"; return; }
  if [[ "$(probe_os)" == Darwin ]]; then
    # /usr/sbin is not on every PATH, and a check that cannot measure must not report 0 GB and fail.
    sysctl -n hw.memsize 2>/dev/null || /usr/sbin/sysctl -n hw.memsize 2>/dev/null || echo 0
  else printf '%s' "$(( $(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0) * 1024 ))"; fi
}
disk_target()      { local t="${PLANETAI_HOME:-$HOME}"; [[ -d "$t" ]] || t="$HOME"; printf '%s' "$t"; }
probe_disk_free_k(){ [[ -n "${PF_DISK_FREE_KB:-}" ]] && { printf '%s' "$PF_DISK_FREE_KB"; return; }; df -Pk "$(disk_target)" 2>/dev/null | awk 'NR==2{print $4}'; }
probe_disk_mount() { [[ -n "${PF_DISK_MOUNT:-}"   ]] && { printf '%s' "$PF_DISK_MOUNT";   return; }; df -P  "$(disk_target)" 2>/dev/null | awk 'NR==2{print $6}'; }
probe_app()        { [[ -d "$(probe_apps)/$1" ]]; }
# Can the node's folder be written to at all? Lucas's laptop answered every other row with a tick while
# its root filesystem was mounted read-only — Linux does that when the kernel finds errors on the disk —
# so "This machine can run a node" was printed to a machine that could not create a file.
probe_writable()   {
  [[ -n "${PF_WRITABLE:-}" ]] && { [[ "$PF_WRITABLE" == 1 ]]; return; }
  local t="$(disk_target)/.planetai-write-test.$$"
  ( : > "$t" ) 2>/dev/null || return 1
  rm -f "$t" 2>/dev/null
  return 0
}
probe_laptop()     { [[ -n "${PF_IS_LAPTOP:-}" ]] && { [[ "$PF_IS_LAPTOP" == 1 ]]; return; }
                     case "$(probe_os)" in
                       Darwin) [[ "$(probe_model)" == MacBook* ]];;
                       Linux)  compgen -G "/sys/class/power_supply/BAT*" >/dev/null;;
                       *)      return 1;;
                     esac; }
probe_ethernet()   { [[ -n "${PF_HAS_ETHERNET:-}" ]] && { [[ "$PF_HAS_ETHERNET" == 1 ]]; return; }
                     case "$(probe_os)" in
                       Darwin) networksetup -listallhardwareports 2>/dev/null | grep -qiE "Hardware Port: (Ethernet|Thunderbolt Ethernet)";;
                       Linux)  compgen -G "/sys/class/net/en*" >/dev/null || compgen -G "/sys/class/net/eth*" >/dev/null;;
                       *)      return 0;;
                     esac; }
probe_cores()      { [[ -n "${PF_CORES:-}" ]] && { printf '%s' "$PF_CORES"; return; }
                     sysctl -n hw.ncpu 2>/dev/null || /usr/sbin/sysctl -n hw.ncpu 2>/dev/null || nproc 2>/dev/null || echo ""; }

# A fix line is either prose or a command. Prose wraps at 78 columns so the table reads at 80x24; a
# command NEVER wraps — a wrapped command cannot be copied, which is the only thing it is for.
fixline() {
  local t="$1" line word
  if [[ "$t" == *"&&"* || "$t" == curl* || "$t" == sudo* || "$t" == open* || "$t" == *"| bash"* ]]; then
    printf '                %s%s%s\n' "$D" "$t" "$N"; return
  fi
  line=""
  for word in $t; do
    if [[ -n "$line" && ${#line} -gt 0 && $(( ${#line} + ${#word} + 1 )) -gt 62 ]]; then
      printf '                %s%s%s\n' "$D" "$line" "$N"; line="$word"
    else line="${line:+$line }$word"; fi
  done
  [[ -n "$line" ]] && printf '                %s%s%s\n' "$D" "$line" "$N"
}

rows=""; fails=0; floor=0
# JSON string escaping, in bash, because a bare Mac has no python3 either — that is the whole point of
# this script. A fix line can be two lines long, and a raw newline inside a JSON string is invalid: the
# --json output, which testers are told to paste into an issue, would not parse. CI caught it.
jesc() { local v="$1"; v="${v//\\/\\\\}"; v="${v//\"/\\\"}"; v="${v//$'\n'/\\n}"; v="${v//$'\t'/\\t}"; printf '%s' "$v"; }
# row NAME "value" PASS "fix line"
row() {
  local name="$1" val="$2" pass="$3" fix="${4:-}"
  [[ "$pass" == 1 ]] || fails=$((fails+1))
  if [[ $JSON -eq 1 ]]; then
    rows+="$(printf '{"check":"%s","value":"%s","ok":%s,"fix":%s}' \
      "$name" "$(jesc "$val")" \
      "$([[ $pass == 1 ]] && echo true || echo false)" \
      "$([[ "$pass" != 1 && -n "$fix" ]] && printf '"%s"' "$(jesc "$fix")" || echo null)"),"
  else
    printf '  %-13s %-44.44s %s\n' "$name" "$val" "$([[ $pass == 1 ]] && echo "${G}✓${N}" || echo "${R}✗${N}")"
    [[ $pass == 1 || -z "$fix" ]] || fixline "$fix"
  fi
}

# ---------------------------------------------------------------- os and arch
OS="$(probe_os)"; ARCH="$(probe_arch)"
case "$ARCH" in x86_64|amd64) ARCH=x86_64;; aarch64|arm64) ARCH=arm64;; esac
MACVER=0; MODEL=""; OSNAME="$OS"; PLATFORM=other

if [[ "$OS" == Darwin ]]; then
  PLATFORM=macos
  MACVER="$(probe_os_ver)"; MACVER="${MACVER:-0}"
  MODEL="$(probe_model)"
  case "${MACVER%%.*}" in 11) CODENAME="Big Sur";; 12) CODENAME=Monterey;; 13) CODENAME=Ventura;; 14) CODENAME=Sonoma;; 15) CODENAME=Sequoia;; 26) CODENAME=Tahoe;; *) CODENAME="";; esac
  OSNAME="macOS $MACVER${CODENAME:+ ($CODENAME)}"
elif [[ "$OS" == Linux ]]; then
  PLATFORM=linux
  OSNAME="$(probe_pretty)"; OSNAME="${OSNAME:-Linux}"
  { [[ "${PF_IS_WSL:-0}" == 1 ]] || grep -qi microsoft /proc/version 2>/dev/null; } && { PLATFORM=wsl; OSNAME="$OSNAME (WSL2)"; }
fi

# The macOS floor is not a constant: it is the lowest floor of any container runtime that installs on THIS
# architecture, read from the generated block above. On Intel that is Colima at 13.5 (Lima's vz cannot boot
# the guest kernel below it); on Apple Silicon it is Colima at 13.0. It was hard-coded at 13.5 for both,
# which turned away an Apple Silicon Mac on 13.0–13.4 that Colima does support.
mac_floor() {
  local lo="" f
  for f in "$RUNTIMES_orbstack_min_os" "$RUNTIMES_docker_desktop_mac_min_os" \
           "$([[ "$ARCH" == x86_64 ]] && echo "$RUNTIMES_colima_min_os_x86_64" || echo "$RUNTIMES_colima_min_os")"; do
    [[ -z "$f" ]] && continue
    [[ -z "$lo" ]] && { lo="$f"; continue; }
    ver_ge "$lo" "$f" && lo="$f"
  done
  printf '%s' "$lo"
}
MAC_FLOOR=""; MAC_FLOOR_OK=1
if [[ "$PLATFORM" == macos ]]; then
  MAC_FLOOR="$(mac_floor)"
  ver_ge "$MACVER" "$MAC_FLOOR" || { MAC_FLOOR_OK=0; floor=1; }
fi

[[ $JSON -eq 1 ]] || printf '\n%spreflight%s  %sno questions, no changes, nothing installed%s\n\n' "$B" "$N" "$D" "$N"

if [[ "$PLATFORM" == macos ]]; then
  row os "$OSNAME" "$MAC_FLOOR_OK" "macOS $MAC_FLOOR or newer is required for any container runtime — see the verdict below"
elif [[ "$PLATFORM" == linux || "$PLATFORM" == wsl ]]; then
  row os "$OSNAME" 1
else
  row os "$OSNAME" 0 "the node runs on macOS, Linux, or Windows through WSL2"
fi

# Until v0.63 arm64 Linux FAILED here, because the database image was published for amd64 only. It is not
# any more (`imresamu/postgis:16-3.4-alpine`, see docker-compose.yml), so a Pi, a Jetson and a reComputer
# pass the architecture check. Passing it is not the same as having been run on one: docs/PLATFORMS.md keeps
# the table of arm64 machines that have actually carried a node, and on 19 Sep 2026 that table is empty.
case "$ARCH" in
  x86_64) row arch "x86_64" 1;;
  arm64)  if [[ "$PLATFORM" == macos ]]; then row arch "arm64 (native database image since v0.63)" 1
          else row arch "arm64 (untested on hardware — docs/ARM64.md)" 1; fi;;
  *)      row arch "$ARCH" 0 "unsupported architecture; the node needs 64-bit x86 or arm64";;
esac

# ---------------------------------------------------------------- memory
MEMB="$(probe_mem_bytes)"; MEMB="${MEMB:-0}"
MEMGB=$(( MEMB / 1073741824 ))
MEMNEED="$NODE_min_ram_gb"; [[ "$PLATFORM" == wsl ]] && MEMNEED="$WINDOWS_min_ram_gb"
if [[ $MEMB -eq 0 ]]; then row memory "could not read it" 1
else row memory "${MEMGB} GB" "$([[ $MEMGB -ge $MEMNEED ]] && echo 1 || echo 0)" \
  "${MEMNEED} GB is the container runtime's own minimum; this machine has ${MEMGB} GB"; fi

# ---------------------------------------------------------------- disk
FREEK="$(probe_disk_free_k)"; FREEK="${FREEK:-0}"
FREEGB=$(( FREEK / 1048576 ))
MOUNT="$(probe_disk_mount)"
row "disk free" "${FREEGB} GB on ${MOUNT:-/}" "$([[ $FREEGB -ge $NODE_min_free_disk_gb ]] && echo 1 || echo 0)" \
  "the images and the database need about ${NODE_min_free_disk_gb} GB free; ${FREEGB} GB is left on ${MOUNT:-/}"

# ---------------------------------------------------------------- container runtime
# Colima is the only macOS runtime that installs with one command and no GUI, which is what an
# unattended mini needs. One 16 MB binary; the vz backend is Apple's own hypervisor, so no QEMU and no
# package manager. It runs the same amd64 postgis image the node already uses.
colima_line() {
  local l="curl -fsSL -o /tmp/colima https://github.com/abiosoft/colima/releases/latest/download/colima-Darwin-${ARCH} && sudo install /tmp/colima /usr/local/bin/colima"
  # Colima drives the docker client; without Homebrew that client is a plain download too. The version is
  # pinned because a copy-pasteable line cannot scrape a directory listing, and a pin that goes stale is
  # harmless here: an older docker client talks to a newer daemon. Newest is at
  # https://download.docker.com/mac/static/stable/<arch>/ (checked 8 Sep 2026: 29.8.0).
  have docker || l="$l && curl -fsSL https://download.docker.com/mac/static/stable/${ARCH}/docker-29.8.0.tgz | tar xz -C /tmp && sudo install /tmp/docker/docker /usr/local/bin/docker"
  echo "$l && colima start --vm-type vz --cpu 2 --memory 4 --disk 20"
}

runtime_fix() {
  case "$PLATFORM" in
    macos)
      if   ver_ge "$MACVER" "$RUNTIMES_orbstack_min_os"; then echo "$(colima_line)
                (or a GUI: ${RUNTIMES_orbstack_name} at https://orbstack.dev/download, or ${RUNTIMES_docker_desktop_mac_name} — both work on macOS ${MACVER%%.*})"
      elif [[ $MAC_FLOOR_OK -eq 1 ]];  then echo "$(colima_line)
                (${RUNTIMES_colima_name} is the only one on macOS ${MACVER}: ${RUNTIMES_orbstack_name} and ${RUNTIMES_docker_desktop_mac_name} both need ${RUNTIMES_orbstack_min_os})"
      else echo "no container runtime installs on macOS ${MACVER} — see the verdict below"; fi;;
    wsl)   echo "install Docker Desktop for Windows, turn on 'Use the WSL 2 based engine' and WSL integration for this distro, then run this again";;
    linux) echo "the installer adds Docker itself (curl -fsSL https://get.docker.com | sh). Nothing to do now.";;
    *)     echo "";;
  esac
}

# Being on the disk is not the same as being able to run. A tester in Mallorca downloaded the OrbStack
# .dmg the day before, so the folder existed; OrbStack needs macOS 14 and his Mac is on 12.7.6. Preflight
# read the folder, ticked the row green, and promised to start it and wait up to five minutes for a daemon
# that could never appear. So every runtime carries its own floor and is only counted where it can launch.
rt_min_os() {
  case "$1" in
    OrbStack)         printf '%s' "$RUNTIMES_orbstack_min_os";;
    "Docker Desktop") printf '%s' "$RUNTIMES_docker_desktop_mac_min_os";;
    Colima)           [[ "$ARCH" == x86_64 ]] && printf '%s' "$RUNTIMES_colima_min_os_x86_64" || printf '%s' "$RUNTIMES_colima_min_os";;
    *)                printf '';;
  esac
}
rt_launchable() {                      # 0 = can start here
  local min; min="$(rt_min_os "$1")"
  [[ "$PLATFORM" != macos || -z "$min" ]] && return 0
  ver_ge "$MACVER" "$min"
}

RT_NAME=""; RT_STATE=""
if docker_running; then RT_NAME="docker"; RT_STATE=running
elif have docker || have colima || probe_app OrbStack.app || probe_app Docker.app; then
  if   probe_app OrbStack.app; then RT_NAME="OrbStack"
  elif probe_app Docker.app;   then RT_NAME="Docker Desktop"
  elif have colima;            then RT_NAME="Colima"
  else RT_NAME="docker"; fi
  if rt_launchable "$RT_NAME"; then RT_STATE=installed; else RT_STATE=unlaunchable; fi
fi

if [[ "$RT_STATE" == running ]]; then
  row runtime "docker, running" 1
elif [[ "$RT_STATE" == unlaunchable ]]; then
  # A cross, with the number, and no promise. The fix is whatever CAN run here, which on a Mac below
  # every floor is nothing — the verdict says so rather than this row pretending otherwise.
  row runtime "$RT_NAME installed, but requires macOS $(rt_min_os "$RT_NAME")" 0 "$(runtime_fix)"
elif [[ "$RT_STATE" == installed ]]; then
  case "$RT_NAME" in
    OrbStack)        START="open -a OrbStack";;
    "Docker Desktop") START="open -a Docker";;
    Colima)          START="colima start";;
    *)               START="start your container runtime (on Linux: sudo systemctl start docker)";;
  esac
  # not a failure the tester has to act on: the installer starts it and waits. Say so.
  row runtime "$RT_NAME, not running" 1
  [[ $JSON -eq 1 ]] || printf '                %sthe install starts it and waits up to 5 minutes (%s)%s\n' "$D" "$START" "$N"
elif [[ "$PLATFORM" == linux ]]; then
  row runtime "none found — the installer adds Docker" 1
else
  row runtime "none found" 0 "$(runtime_fix)"
fi

# ---------------------------------------------------------------- can it be written to
# Free space is not the same as writable. A filesystem the kernel has remounted read-only reports its
# space cheerfully and refuses every write.
if probe_writable; then row writable "yes" 1
else
  DTGT="$(disk_target)"
  row writable "read-only: nothing can be written" 0 "the filesystem holding ${DTGT} cannot be written to. That is the machine, not the node, and it is the first thing to fix."
  [[ $JSON -eq 1 ]] || {
    printf '                %ssee what the kernel says about the disk:%s\n' "$D" "$N"
    printf '                %s  mount | grep " / "%s\n' "$D" "$N"
    printf '                %s  sudo dmesg | grep -iE "ext4|i/o error|remount" | tail -20%s\n' "$D" "$N"
    printf '                %sLinux remounts a filesystem read-only when it finds errors on the drive.%s\n' "$D" "$N"
    printf '                %sA reboot usually brings it back and runs a check; if it returns, the drive%s\n' "$D" "$N"
    printf '                %sis failing and this machine should not be a node until it is replaced.%s\n' "$D" "$N"
  }
fi

# ---------------------------------------------------------------- python3, which the CLI needs
# This script is pure bash on purpose. `planetai` is not: it geocodes a place name, reads an answers
# file and formats every --json with python3's standard library. A clean Arch and a minimal Ubuntu
# Server have no python3, and the CLI died on them with "Something went wrong" — measured in CI on
# 9 September 2026, on ubuntu:22.04 and archlinux:latest.
py3_fix() {
  case "$PLATFORM" in
    macos) echo "python3 comes with the Xcode Command Line Tools: xcode-select --install";;
    linux|wsl)
      case "$(probe_pretty)" in
        *Arch*|*Manjaro*|*Omarchy*|*CachyOS*|*EndeavourOS*) echo "sudo pacman -S --noconfirm python";;
        *Fedora*|*Red\ Hat*|*Rocky*|*Alma*)                  echo "sudo dnf install -y python3";;
        *)                                                   echo "sudo apt-get update && sudo apt-get install -y python3";;
      esac;;
    *) echo "install python3 (the standard library is enough; nothing here runs pip)";;
  esac
}
if have python3; then row python3 "present" 1
else row python3 "not installed" 0 "$(py3_fix)"; fi

# ---------------------------------------------------------------- egress
# The four hosts that decide whether an install finishes. Everything else is post-install and belongs to doctor.
# `curl -f` would fail on the 401 the Docker registry answers with and the 404 a bare API root gives, and both
# of those mean the host is reachable. The only real failure is no answer at all, which curl reports as 000.
EG_OK=1; EG_BAD=""
if [[ -n "${PF_EGRESS_OK:-}" ]]; then
  EG_OK="$PF_EGRESS_OK"; [[ "$EG_OK" == 1 ]] || EG_BAD="${PF_EGRESS_BAD:-the network}"
else
  for h in planetai.fab.city/node0/get/SHA256 raw.githubusercontent.com registry-1.docker.io/v2/ api.open-meteo.com; do
    code="$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "https://$h" 2>/dev/null || echo 000)"
    [[ "$code" != 000 ]] || { EG_OK=0; EG_BAD="${EG_BAD:+$EG_BAD }${h%%/*}"; }
  done
fi
row egress "$([[ $EG_OK == 1 ]] && echo "site, github, registry, open-meteo" || echo "cannot reach: $EG_BAD")" "$EG_OK" \
  "the install needs to reach $EG_BAD. A proxy or a captive portal is in the way."

# ---------------------------------------------------------------- ports
busy="${PF_PORTS_BUSY-}"
if [[ -z "${PF_PORTS_BUSY+x}" ]]; then
  for p in 8080 5432; do
    if have lsof; then lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1 && busy="${busy:+$busy, }$p"
    elif have ss;  then ss -ltn "sport = :$p" 2>/dev/null | grep -q LISTEN && busy="${busy:+$busy, }$p"; fi
  done
fi
row ports "$([[ -z "$busy" ]] && echo "8080, 5432 free" || echo "$busy in use")" "$([[ -z "$busy" ]] && echo 1 || echo 0)" \
  "set APP_PORT to a free port in .env before installing (8080 is the dashboard; 5432 is the database, bound to localhost)"

# ---------------------------------------------------------------- notes, not failures
# Only what is true of THIS machine, at most three lines, and never mixed into the verdict. A laptop is a
# fine node and a bad one for the same reason: it is designed to go to sleep.
if [[ $JSON -eq 0 ]] && probe_laptop; then
  echo
  printf '  %sThis is a laptop. Three things, none of them failures:%s\n' "$B" "$N"
  case "$PLATFORM" in
    macos)
      printf '    %ssleep%s      a sleeping machine is a stopped node. Closing the lid counts.\n' "$D" "$N"
      printf '                 %ssudo pmset -a disablesleep 1%s   (asks for your password; stops all sleep, lid included)\n' "$D" "$N"
      printf '    %sbattery%s    a laptop left plugged in for years is worth a look before you rely on it:\n' "$D" "$N"
      printf '                 %ssystem_profiler SPPowerDataType | grep -E "Cycle Count|Condition"%s\n' "$D" "$N";;
    linux|wsl)
      printf '    %ssleep%s      a sleeping machine is a stopped node. Closing the lid counts.\n' "$D" "$N"
      printf '                 %ssudo sed -i s/^#HandleLidSwitch=.*/HandleLidSwitch=ignore/ /etc/systemd/logind.conf%s\n' "$D" "$N"
      printf '                 %sthen: sudo systemctl restart systemd-logind%s\n' "$D" "$N"
      printf '    %sbattery%s    a laptop left plugged in for years is worth a look before you rely on it:\n' "$D" "$N"
      printf '                 %scat /sys/class/power_supply/BAT0/health /sys/class/power_supply/BAT0/cycle_count%s\n' "$D" "$N";;
  esac
  probe_ethernet || { printf '    %sethernet%s   no wired port here. For a node that stays on, a USB gigabit adapter\n' "$D" "$N"
                      printf '                 is the wired path; WiFi drops and a node notices.\n'; }
fi

# ---------------------------------------------------------------- verdict
# Did the machine itself pass, and only its system fail? That decides whether the verdict opens by
# saying what this computer is, or stays quiet about it.
HW_OK=0
# arm64 counts as hardware that passed from v0.63. While the database image was amd64-only, an arm64
# machine with 32 GB and a terabyte free was still not a node, so the architecture belonged in this
# test; now the only architectures that fail are the ones the case above rejects outright.
[[ $MEMGB -ge $MEMNEED && $FREEGB -ge $NODE_min_free_disk_gb && ( "$ARCH" == x86_64 || "$ARCH" == arm64 ) ]] && HW_OK=1

if [[ $JSON -eq 1 ]]; then
  verdict=ok; [[ $fails -gt 0 ]] && verdict=fixable; [[ $floor -eq 1 ]] && verdict=below-floor
  printf '{"ok":%s,"verdict":"%s","os":"%s","arch":"%s","checks":[%s]}\n' \
    "$([[ $fails -eq 0 ]] && echo true || echo false)" "$verdict" "$(jesc "$OSNAME")" "$ARCH" "${rows%,}"
  [[ $floor -eq 1 ]] && exit 2; [[ $fails -eq 0 ]] && exit 0 || exit 1
fi

echo
if [[ $floor -eq 1 ]]; then
  # What the machine IS, before what it lacks. A 2015 quad-core with 16 GB is a better node than the mini
  # PC we would otherwise tell somebody to buy; saying only "unsupported" reads as "your laptop is junk",
  # and that is both untrue and the opposite of this project's own argument.
  CORES="$(probe_cores)"
  if [[ $HW_OK -eq 1 ]]; then
    printf '  %sThis hardware is a capable node — %s cores, %s GB, %s GB free. The OS is the only blocker.%s\n\n' \
      "$G" "${CORES:-?}" "$MEMGB" "$FREEGB" "$N"
  fi
  printf '  %sNo container runtime can be installed on %s.%s\n' "$B" "$OSNAME" "$N"
  printf '  %s needs %s, %s needs %s, %s needs %s here.\n\n' \
    "$RUNTIMES_orbstack_name" "$RUNTIMES_orbstack_min_os" \
    "$RUNTIMES_docker_desktop_mac_name" "$RUNTIMES_docker_desktop_mac_min_os" \
    "$RUNTIMES_colima_name" "$([[ "$ARCH" == x86_64 ]] && echo "$RUNTIMES_colima_min_os_x86_64" || echo "$RUNTIMES_colima_min_os")"

  # Is upgrading a route on THIS model? One of three sentences, and never a guess.
  CEIL="$(mac_ceiling "$MODEL")"; CEIL_VER="${CEIL%%|*}"; CEIL_NAME="${CEIL#*|}"
  printf '  %sIs upgrading a route?%s\n' "$B" "$N"
  if [[ -z "$CEIL" ]]; then
    printf '    I do not have a last-supported macOS for %s, so I will not guess.\n' "${MODEL:-this model}"
    printf '    Apple lists it: https://support.apple.com/en-us/HT201862\n'
    printf '    If this Mac can reach macOS %s, upgrade and run this again.\n\n' "$MAC_FLOOR"
  elif ver_ge "$CEIL_VER" "$MAC_FLOOR"; then
    printf '    Yes. %s can run macOS %s — upgrade, then run this again.\n\n' "$CEIL_NAME" "$CEIL_VER"
  else
    printf '    No. This model cannot go past macOS %s — upgrading is not a route.\n' "$CEIL_VER"
    printf '    %s, and Apple ships nothing newer for it.\n\n' "$CEIL_NAME"
  fi

  # Routes, as commands. Not "use another machine".
  printf '  %sTwo routes that work on this machine%s\n\n' "$B" "$N"
  printf '  %s1. Linux in a virtual machine, on this Mac.%s UTM is free, needs no account, and on Intel\n' "$B" "$N"
  printf '     it uses Apple'"'"'s own hypervisor, so the CPU runs at close to full speed.\n'
  printf '     %sUTM %s supports macOS %s — this Mac included.%s\n' "$D" "$ASSET_utm_dmg_version" "$VM_HOSTS_utm_min_os" "$N"
  printf '       curl -fL -o ~/Downloads/UTM.dmg %s\n' "$ASSET_utm_dmg_url"
  printf '       open ~/Downloads/UTM.dmg\n'
  printf '       curl -fL -o ~/Downloads/ubuntu-server.iso %s\n' "$ASSET_ubuntu_server_iso_url"
  printf '     %sThen in UTM: Create a New Virtual Machine → Virtualize → Linux → that .iso.\n' "$D"
  printf '     Give it 2 CPUs, 4096 MB, 25 GB. Install Ubuntu Server, then inside the VM run\n'
  printf '     the same line you ran here.%s\n\n' "$N"
  printf '  %s2. Linux on the metal, and this laptop becomes the node.%s The better end state: no\n' "$B" "$N"
  printf '     macOS underneath, nothing to keep awake, and the floor stops moving. Two choices,\n'
  printf '     depending on whether anyone still uses this machine day to day:\n\n'
  printf '     %sUbuntu Server%s — nobody uses it, it just runs. No desktop, ssh in, lowest upkeep.\n' "$B" "$N"
  printf '       curl -fL -o ~/Downloads/ubuntu-server.iso %s\n' "$ASSET_ubuntu_server_iso_url"
  printf '     %sOmarchy %s%s — a laptop somebody uses AND a node. Arch underneath, a finished desktop,\n' "$B" "$ASSET_omarchy_iso_version" "$N"
  printf '     five questions from stick to working machine.\n'
  printf '       curl -fL -o ~/Downloads/omarchy.iso %s\n' "$ASSET_omarchy_iso_url"
  printf '     %sThe walk-through for either: docs/REVIVE_A_LAPTOP.md — a USB stick and about an hour.%s\n\n' "$D" "$N"
  printf '  %sNothing was installed and nothing was changed.%s  Floors: data/platform_floors.yml\n\n' "$D" "$N"
  exit 2
fi
if ! probe_writable; then
  printf '  %sThis machine cannot run a node yet, and the reason is its disk.%s\n\n' "$R" "$N"
  printf '  The filesystem is mounted read-only, so nothing can be installed or written anywhere —\n'
  printf '  not a node, not a log, not a settings file. Everything else above may be fine.\n\n'
  printf '  %sDo this before anything else%s\n' "$B" "$N"
  printf '    mount | grep " / "                                       is it ro?\n'
  printf '    sudo dmesg | grep -iE "ext4|i/o error|remount" | tail -20  what the kernel found\n'
  printf '    sudo reboot                                              usually remounts it and checks\n\n'
  printf '  If it goes read-only again after a reboot, the drive is failing. Copy anything you want off\n'
  printf '  it first. A node writes to its disk every few minutes, so a failing drive is the one piece of\n'
  printf '  hardware it cannot tolerate.\n\n'
  printf '  %sNothing was installed and nothing was changed.%s\n\n' "$D" "$N"
  exit 1
fi
if [[ $fails -eq 0 ]]; then
  printf '  %sThis machine can run a node.%s\n' "$G" "$N"
  # An Intel Mac works today and is on a treadmill: OrbStack went to 14, Docker Desktop drops the oldest
  # macOS every autumn, Multipass went to 14. Apple ships no new Intel Macs, so the floor only rises.
  # A note, not a failure, and only where it is true.
  if [[ "$PLATFORM" == macos && "$ARCH" == x86_64 ]]; then
    printf '\n  %sWorth knowing, while it is working:%s this is an Intel Mac, and every container runtime\n' "$Y" "$N"
    printf '  for macOS has raised its floor in the last two years. Linux on this machine does not have\n'
    printf '  that problem, and it is a better node — nothing to keep awake, and the floor stops moving.\n'
    printf '    %sUbuntu Server%s  nobody uses it, it just runs\n' "$B" "$N"
    printf '    %sOmarchy%s        a laptop somebody uses, and a node\n' "$B" "$N"
    printf '    %sdocs/REVIVE_A_LAPTOP.md%s\n' "$D" "$N"
  fi
  echo
  exit 0
fi
printf '  %s%d check%s failed.%s Each line above carries the fix. Nothing was installed.\n' "$Y" "$fails" "$([[ $fails -eq 1 ]] || echo s)" "$N"
printf '  Paste this into an issue:  %splanetai preflight --json%s   (or: curl -fsSL planetai.fab.city/preflight | bash -s -- --json)\n\n' "$D" "$N"
exit 1
