#!/usr/bin/env bash
# planetai-node installer. Idempotent — re-run any time.
#   ./install.sh --name <node> [--preset bali|barcelona|boston|santiago] [--lat <lat> --lon <lon>]
#                [--sc 19880] [--airgradient host,host] [--purpleair ip] [--indoor] [--no-bad] [--no-bootstrap]
#   A node needs coordinates. Sensors are optional: with none, it still bootstraps 92 days of CAMS air quality
#   and NASA POWER climatology for its location — free, no key, anywhere on earth.
#   pick at least one sensor flag. --indoor marks LAN sensors as indoor. --no-bad disables the Bali Air Dispatch reference (outside Bali).
# Targets: macOS (Apple Silicon/Intel; OrbStack or Docker Desktop), Debian/Ubuntu/Raspberry Pi OS 64-bit, Arch, Fedora, Windows via WSL2 (Ubuntu).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

# ---------------------------------------------------------------- feedback, because run 1 had none
# On 7 September this script printed ONE line — "writing settings, pulling images, building the node" —
# for a phase of several minutes, and then died inside it. The tester could not tell what had been tried,
# what had succeeded, or how long to wait. So: named steps, elapsed seconds on start and finish, a
# heartbeat every 10 s carrying the last interesting line, and on failure the step's NAME first.
#
# No cursor tricks, no spinner, no colour dependence, nothing wider than 80 columns: this has to read the
# same in a terminal, in a pipe, and in a log a tester pastes into an issue.
LOG_FILE="${PLANETAI_INSTALL_LOG:-$PWD/.planetai-install.log}"
STEP_T0=$SECONDS
STEP_N=0; STEP_TOTAL=0; STEP_NAME=""; RUN_T0=$SECONDS
: > "$LOG_FILE"

hb_line() {           # the last thing worth showing: which layer, which image, which build step
  # compose and buildkit redraw with carriage returns, so one "line" of the log holds many frames.
  # Split on \r, keep the frames that name something, take the newest, squeeze the spacing.
  # `|| true` is not decoration: this runs under `set -euo pipefail`, and for the first ten seconds the
  # log is empty, so grep exits 1, the pipeline fails, and the assignment that calls this kills the whole
  # install — silently, before any heartbeat prints. That is exactly what it did.
  { tr '\r' '\n' < "$LOG_FILE" 2>/dev/null \
    | grep -aE 'Downloading|Extracting|Pull complete|Download complete|Verifying|Waiting|Pulling from|Creating|Created|Starting|Started|Healthy|^#[0-9]+ ' \
    | tail -1 | sed -e 's/\x1b\[[0-9;]*[A-Za-z]//g' -e 's/  */ /g' -e 's/^ *//' | cut -c1-62; } 2>/dev/null || true
}
step() {              # step "name"  — announce and start the clock
  STEP_N=$((STEP_N+1)); STEP_NAME="$1"; STEP_T0=$SECONDS
  printf '[%d/%d] %s\n' "$STEP_N" "$STEP_TOTAL" "$1"
}
step_ok()   { printf '        done in %ds\n' $((SECONDS-STEP_T0)); }
# What the log says the failure actually was. "check the network" was printed to a tester whose layer
# commit failed writing to disk — `failed commit on ref "layer-sha256:..."` — on a laptop whose root
# filesystem had gone read-only an hour earlier from kernel-detected drive errors. A reason line that
# points at the wrong subsystem costs more than no reason line at all.
diagnose() {
  local log="${LOG_FILE:-/dev/null}" hit
  hit="$(grep -aoE 'no space left on device|failed commit on ref|input/output error|read-only file system|no such host|network is unreachable|TLS handshake timeout|connection refused|i/o timeout|denied: requested access|manifest unknown' "$log" 2>/dev/null | tail -1)"
  case "$hit" in
    "no space left on device")
      printf 'the disk filled up. Where it went:\n  df -h .\n  docker system df';;
    "failed commit on ref"|"input/output error"|"read-only file system")
      # Every line here fits 80 columns including its 10-column indent. Lucas's terminal wrapped the
      # first version and the trailing comments landed in the middle of the next line.
      #
      # It used to print the dmesg and df commands and ask somebody to run them. That costs a round
      # trip each time — a tester runs it, photographs the screen, sends the photo, waits. Both checks
      # are read-only, so do them here and put the answer in the failure. `sudo -n` never prompts: it
      # uses the credential sudo_first already cached, or fails and we fall back to printing the
      # command. grep matching nothing must not take the caller down, hence the `|| true`.
      local kern dfo dev
      dev="$( df -P / 2>/dev/null | awk 'NR==2{ sub(/p?[0-9]+$/,"",$1); print $1 }' || true )"
      # Only the names smartctl can actually take. macOS df answers /dev/disk3s1s, which would be
      # printed as advice that cannot work.
      case "$dev" in /dev/sd[a-z]|/dev/nvme[0-9]n[0-9]|/dev/hd[a-z]|/dev/vd[a-z]|/dev/mmcblk[0-9]) ;;
                     *) dev="/dev/sda";; esac
      kern="$( { dmesg 2>/dev/null || sudo -n dmesg 2>/dev/null || true; } \
               | grep -aiE 'i/o error|ext4-fs .*(warning|error|failed)|nvme.*(error|timeout|reset)|ata[0-9]+.*(failed|error|frozen)' \
               | tail -3 | sed -e 's/^\[[0-9. ]*\] //' -e 's/^\(.\{66\}\).*/\1/' || true )"
      # -P: the POSIX six-column layout, so $6 is the mount point on macOS as well as Linux. Without
      # it, macOS df prints inode columns and this printed an inode count where the path should be.
      dfo="$( df -hP / /var/lib/docker 2>/dev/null | tail -n +2 \
              | awk '{ printf "%-24.24s %s full\n", $6, $5 }' || true )"
      printf 'the download arrived but could not be written. This is the disk.\n'
      if [[ -n "$kern" ]]; then
        printf 'what the kernel already logged, which settles it:\n'
        printf '%s\n' "$kern" | sed 's/^/  /'
      else
        printf 'what the kernel saw (needs a password, so run it yourself):\n  sudo dmesg | grep -iE "i/o error|ext4|nvme|ata" | tail -20\n'
      fi
      if [[ -n "$dfo" ]]; then
        printf 'and the space, which rules a full filesystem in or out:\n'
        printf '%s\n' "$dfo" | sed 's/^/  /'
      else
        printf 'whether either filesystem is full:\n  df -h / /var/lib/docker\n'
      fi
      printf 'a store earlier trouble left inconsistent. This clears it, and holds
nothing of yours before a first install. Stop the socket too, or the
daemon is woken again while the folder is being deleted:
  sudo systemctl stop docker.socket docker.service
  sudo rm -rf /var/lib/docker && sudo systemctl start docker
If it fails again it is the storage path: drive, cable, controller.
These two help - but a clean result does NOT clear the drive. An SSD
can time out on long writes with every counter still at zero:\n'
      printf '  sudo smartctl -l error %s\n' "$dev"
      printf '  sudo smartctl -A %s | grep -iE "CRC|Reallocat|Pending"\n' "$dev";;
    "no such host"|"network is unreachable"|"TLS handshake timeout"|"connection refused"|"i/o timeout")
      printf 'the registry could not be reached. A proxy, a captive\nportal, or the line itself.';;
    "denied: requested access"|"manifest unknown")
      printf 'the registry refused the image name. That is a bug here,\nnot on your machine. Please tell us.';;
    *) printf '';;
  esac
}

step_fail() {         # step_fail "why"
  printf '\n'
  printf 'FAILED: %s\n' "$STEP_NAME"
  printf '  after   %ds\n' $((SECONDS-STEP_T0))
  local dx; dx="$(diagnose)"; dx="${dx:-${1:-see the log}}"
  printf '  reason  %s\n' "$(printf '%s' "$dx" | head -1)"
  printf '%s\n' "$dx" | tail -n +2 | sed -e 's/^ */          /' 
  local l; l="$( { grep -aE 'ERROR|error:|Error|failed|cannot|denied|refused' "$LOG_FILE" 2>/dev/null | tail -1 | cut -c1-70; } || true)"
  [[ -n "$l" ]] && printf '  log     %s\n          %s\n' "$LOG_FILE" "$l" || printf '  log     %s\n' "$LOG_FILE"
  printf '  resume  planetai setup      (your answers are saved; it will not ask them again)\n'
  printf '\ninstall FAILED at step %d/%d "%s" after %ds — %s\n' "$STEP_N" "$STEP_TOTAL" "$STEP_NAME" $((SECONDS-RUN_T0)) "$LOG_FILE"
  exit 1
}
# sudo cannot ask for a password from a background job. It gets SIGTTIN and stops, or gives up — and the
# prompt lands in the log where nobody sees it. Lucas's screen on 9 September: "[sudo] password for
# lucas:", then a heartbeat saying nothing had happened, then FAILED after 17 seconds. He was never given
# the chance to type it. So: ask ONCE, in the foreground, before any step that needs it.
SUDO_PRIMED=0
sudo_first() {        # sudo_first "what it is for"
  need sudo || return 0
  sudo -n true 2>/dev/null && { SUDO_PRIMED=1; return 0; }   # cached, or this user needs no password
  say "$1 needs your password, once. Nothing else in this install uses sudo."
  sudo -v || die "sudo did not accept the password, so Docker cannot be installed.
   Install it yourself, then run the resume command:
     curl -fsSL https://get.docker.com | sh
     sudo usermod -aG docker $USER"
  SUDO_PRIMED=1
}

watch_run() {         # watch_run "why it failed" cmd...  — run it, heartbeat every 10s, never go quiet
  local why="$1"; shift
  "$@" >>"$LOG_FILE" 2>&1 &
  local pid=$! last=$SECONDS refreshed=$SECONDS h
  while kill -0 "$pid" 2>/dev/null; do
    sleep 2
    # sudo forgets after fifteen minutes by default, and get.docker.com can take longer than that on a
    # slow line — it would then hang for a password it cannot ask for. Keep the ticket alive.
    if [[ $SUDO_PRIMED -eq 1 ]] && (( SECONDS - refreshed >= 60 )); then refreshed=$SECONDS; sudo -n -v 2>/dev/null || true; fi
    if (( SECONDS - last >= 10 )); then
      last=$SECONDS; h="$(hb_line || true)"
      printf '        %4ds  %s\n' $((SECONDS-STEP_T0)) "${h:-still working — the tool has printed nothing new yet}"
    fi
  done
  wait "$pid" || step_fail "$why"
}

say()  { printf '\033[1;32m>>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; printf '!! %s\n' "$*" >>"${LOG_FILE:-/dev/null}" 2>/dev/null || true; }  # a refusal nobody sees twice is a refusal lost: warnings belong in the install log too
# Every exit goes through the reporter. `die` predates it and there are a dozen calls: the old-database
# guard, the missing coordinates, the port clash. Each one used to print a bare xx line with no step
# name, no elapsed time and no way back — the shape the tester met on 7 September. Now they all carry
# their step, and the summary line is printed once whichever path exits.
die()  {
  # Say it ONCE. This printed the whole message as an `xx` line, then again as the `reason`, and the
  # resume line a third time because a long message ended with its own "Then: planetai setup". Lucas's
  # screen carried the same eight lines twice, which is harder to read than one line would have been.
  if [[ -n "${STEP_NAME:-}" ]]; then
    local dx; dx="$(diagnose)"
    printf '\nFAILED: %s\n' "$STEP_NAME" >&2
    printf '  after   %ds\n' $((SECONDS-STEP_T0)) >&2
    # A multi-line reason keeps its own shape, indented under the label rather than folded into it.
    printf '  reason  %s\n' "$(printf '%s' "${dx:-$*}" | head -1)" >&2
    printf '%s\n' "${dx:-$*}" | tail -n +2 | sed -e 's/^ */          /' >&2
    printf '  log     %s\n' "${LOG_FILE:-none yet}" >&2
    printf '  resume  planetai setup      (your answers are saved; it will not ask them again)\n' >&2
    printf '\ninstall FAILED at step %d/%d "%s" after %ds\n' "${STEP_N:-0}" "${STEP_TOTAL:-0}" "$STEP_NAME" $((SECONDS-RUN_T0)) >&2
  else
    printf '\033[1;31mxx\033[0m %s\n' "$*" >&2
    printf '\ninstall FAILED before the first step: %s\n' "$(printf '%s' "$*" | head -1)" >&2
  fi
  exit 1
}
need() { command -v "$1" >/dev/null 2>&1; }

ARGS=("$@")                 # kept whole: the docker-group re-exec below needs them after the loop has shifted them away
NAME=""; SC=""; AG=""; PA=""; LAT=""; LON=""; INDOOR=""; NOBAD=""; PRESET=""; NOBOOT=""
SCUSER=""; KIND=""; TZ_=""; YES=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;; --sc) SC="$2"; shift 2;; --airgradient) AG="$2"; shift 2;; --purpleair) PA="$2"; shift 2;;
    --lat) LAT="$2"; shift 2;; --lon) LON="$2"; shift 2;; --indoor) INDOOR=1; shift;; --no-bad) NOBAD=1; shift;;
    --preset) PRESET="$2"; shift 2;; --no-bootstrap) NOBOOT=1; shift;;
    --sc-user) SCUSER="$2"; shift 2;; --kind) KIND="$2"; shift 2;; --tz) TZ_="$2"; shift 2;; --yes) YES=1; shift;;
    -h|--help) sed -n '2,6p' "$0"; exit 0;; *) die "unknown flag $1";;
  esac
done

# ---- platform
OS="$(uname -s)"; ARCH="$(uname -m)"
case "$ARCH" in x86_64|amd64) ARCH=amd64;; aarch64|arm64) ARCH=arm64;; *) die "unsupported arch $ARCH (32-bit ARM? use a 64-bit OS)";; esac
if [[ "$OS" == "Darwin" ]]; then PLATFORM=macos
elif [[ "$OS" == "Linux" ]]; then
  # read ID in a subshell: os-release also defines NAME, which would overwrite the --name flag (every Linux node was called "Ubuntu")
  ID="$( . /etc/os-release 2>/dev/null && echo "${ID:-}" )"
  case "${ID:-}" in debian|ubuntu|raspbian|linuxmint|pop) PLATFORM=debian;; arch|manjaro|cachyos|endeavouros) PLATFORM=arch;; fedora|rhel|rocky|almalinux) PLATFORM=fedora;; *) PLATFORM=linux;; esac
else die "unsupported OS $OS"; fi
grep -qi microsoft /proc/version 2>/dev/null && { PLATFORM="wsl-${PLATFORM}"; say "Windows (WSL2) detected"; }
say "platform ${PLATFORM}/${ARCH}"

if [[ "$PLATFORM" != macos ]]; then
  for t in curl make; do need "$t" || {
    # Every sudo this script runs says on the line before what it will do and why. Silence is how an
    # installer ends up looking like something that took liberties with a machine.
    sudo_first "installing $t"
    say "$t is missing and the node needs it. This asks for your password to install just that package:"
    case "$PLATFORM" in
      *debian*) echo "     sudo apt-get update && sudo apt-get install -y $t"; sudo apt-get update -qq && sudo apt-get install -y -qq "$t";;
      *arch*)   echo "     sudo pacman -Sy --noconfirm $t";               sudo pacman -Sy --noconfirm "$t";;
      *fedora*) echo "     sudo dnf install -y $t";                       sudo dnf install -y "$t";;
      *)        die "$t is missing and I do not recognise this distribution's package manager. Install $t, then run this again.";;
    esac; }
  done
fi

# ---- the plan, BEFORE the container runtime, not after it. On a fresh Linux box `get.docker.com`
# is the single biggest download of the whole install — hundreds of megabytes of packages — and it
# used to run above the first named step, inside the outer spinner, saying nothing. A tester in
# Menorca watched "writing settings, pulling images, building the node" for twenty minutes on
# 8 September while Docker installed invisibly behind it. Step 1 is the runtime now.
STEP_TOTAL=7
printf '\n%s\n' "Installing a node. Seven steps. Two to six minutes if Docker is already here,"
printf '%s\n' "up to twenty on a fresh Linux box, because Docker itself is a large download."
printf '%s\n' "Progress below. Full log:"
printf '%s\n\n' "  $LOG_FILE"

# ---- docker
# An installed-but-not-running runtime is not a reason to stop: it is a reason to wait. Every tester who hit
# "Docker isn't running" had Docker on the machine and had simply not opened it since the last reboot.
runtime_app() {                     # what is installed here, and the line that starts it
  if   [[ -d /Applications/OrbStack.app ]]; then echo "OrbStack|open -a OrbStack"
  elif [[ -d /Applications/Docker.app   ]]; then echo "Docker Desktop|open -a Docker"
  elif need colima;                           then echo "Colima|colima start"
  elif need systemctl && systemctl list-unit-files docker.service >/dev/null 2>&1; then echo "Docker|sudo systemctl start docker"
  else echo "|"; fi
}
# "The daemon is not up" and "I cannot reach the daemon" are different sentences, and `docker info`
# fails with the same exit code for both. Lucas waited the full five minutes and gave up on a daemon
# that had been listening since 12:34:55 — his journal says so: "Daemon has completed initialization",
# "API listen on /run/docker.sock". He had been added to the docker group in an earlier run, and a shell
# that started before that cannot use it. The re-exec that fixes it lived a hundred lines further down,
# past the wait that had already died.
#
# Return codes: 0 the daemon is usable · 2 the daemon is up but THIS shell may not touch its socket
#               1 it never came up
daemon_state() {
  local err
  err="$(docker info 2>&1 >/dev/null)" && return 0
  case "$err" in
    *"permission denied"*|*"Got permission denied while trying to connect"*) return 2;;
  esac
  # The socket existing with a live service is the same story, whatever the client says.
  if [[ -S /var/run/docker.sock || -S /run/docker.sock ]] \
     && { ! need systemctl || [[ "$(systemctl is-active docker 2>/dev/null)" == active ]]; }; then
    return 2
  fi
  return 1
}
wait_for_daemon() {                 # up to 5 minutes, with the clock visible
  local deadline=$((SECONDS + 300)) st
  while (( SECONDS < deadline )); do
    daemon_state; st=$?
    case $st in
      0) [[ -t 1 ]] && printf '\r\033[K'; say "container runtime is up"; return 0;;
      2) [[ -t 1 ]] && printf '\r\033[K'
         say "the runtime is up. This shell is not in the docker group yet — using it for this run."
         return 2;;
    esac
    [[ -t 1 ]] && printf '\r  waiting for the container runtime … %d:%02d left\033[K' $(( (deadline-SECONDS)/60 )) $(( (deadline-SECONDS)%60 ))
    sleep 2
  done
  [[ -t 1 ]] && printf '\r\033[K'
  return 1
}
# Continue under the docker group now, rather than telling somebody to log out and back in.
use_docker_group() {
  [[ -n "${PLANETAI_SG:-}" ]] && return 1                # already re-exec'd once; do not loop
  need sg || return 1
  grep -qw docker <<< "$(id -nG "$USER" 2>/dev/null)" || sudo usermod -aG docker "$USER" || return 1
  exec sg docker -c "PLANETAI_SG=1 $(printf '%q ' "$0" "${ARGS[@]}")"
}
step "making sure a container runtime is running"
if ! docker info >/dev/null 2>&1; then
  IFS='|' read -r rt_name rt_start <<< "$(runtime_app)"
  if [[ -n "$rt_name" ]]; then
    say "$rt_name is installed but not running. Starting it — this takes up to a minute on a cold boot."
    # Whether the start command WORKED is worth knowing. It used to be `|| true`, so a service that
    # refused to start looked identical to one that was merely slow, and the five-minute countdown ran
    # out before anybody learned that systemctl had already said no.
    start_rc=0
    case "$rt_start" in
      "sudo systemctl start docker")
        sudo_first "starting the Docker service"
        say "this one needs sudo: it starts the system docker service, nothing else"
        sudo systemctl start docker || start_rc=$?;;
      *) $rt_start >/dev/null 2>&1 || start_rc=$?;;
    esac
    [[ $start_rc -eq 0 ]] || warn "the start command returned $start_rc — waiting anyway, in case it is only slow"
    # "Open it by hand" is a Mac sentence. On Linux there is a service, and two commands that say why.
    if [[ "$PLATFORM" == macos ]]; then
      wait_for_daemon; wd=$?
      [[ $wd -eq 2 ]] && use_docker_group
      [[ $wd -eq 1 ]] && die "$rt_name did not come up within 5 minutes. Open it from Applications, wait until it says it is ready, then:
   planetai setup      (your answers are saved; it will not ask them again)"
    else
      wait_for_daemon; wd=$?
      [[ $wd -eq 2 ]] && use_docker_group
      [[ $wd -eq 1 ]] && die "the Docker service did not come up within 5 minutes. These two say why:
     sudo systemctl status docker --no-pager | head -20
     sudo journalctl -u docker --no-pager | tail -30
   If it is crash-looping and this machine has had disk trouble, its image store may be damaged. That
   store holds nothing of yours yet, so it is safe to clear:
     sudo systemctl stop docker.socket docker.service
     sudo rm -rf /var/lib/docker && sudo systemctl start docker"
    fi
  fi
fi
if [[ "$PLATFORM" == "macos" ]]; then
  docker info >/dev/null 2>&1 || die "no container runtime on this Mac. Run 'planetai preflight' — it names the one that installs on this macOS version."
elif [[ "$PLATFORM" == wsl-* ]] && ! need docker; then
  die "Docker not visible inside WSL. Install Docker Desktop for Windows, enable 'Use the WSL 2 based engine' and turn on WSL integration for this distro (Settings → Resources → WSL integration), then re-run."
elif ! need docker && need podman; then
  # Podman is here and Docker is not, and that is almost always deliberate — a Fedora or RHEL machine, or
  # somebody who does not want a root daemon. Installing Docker over the top of it would be this script
  # deciding something the person already decided, and on a Pi it would also mean two runtimes fighting
  # over cgroups.
  #
  # What the node needs is not Docker specifically; it is a `docker` command and a socket. Podman ships
  # both: `podman-docker` provides /usr/bin/docker, and the user socket is what DOCKER_HOST points at.
  # With those two in place every one of this repository's 99 `docker` call sites — 57 in bin/planetai
  # alone — works unchanged, which is why this is two lines of instruction and not a refactor.
  #
  # NOT TESTED ON A NODE. No CI leg runs under Podman and nobody has carried a node on it, so this says
  # what to do and stops rather than installing something and claiming it works. docs/ARM64.md
  # carries what proving it would take.
  warn "Podman is installed here and Docker is not. Not installing Docker over it."
  echo "     The node drives a runtime through the 'docker' command, and Podman can provide one:"
  echo
  echo "       sudo <package manager> install podman-docker        provides /usr/bin/docker"
  echo "       systemctl --user enable --now podman.socket         and a socket for it to talk to"
  echo "       export DOCKER_HOST=unix://\$XDG_RUNTIME_DIR/podman/podman.sock"
  echo
  echo "     Then run this same line again; it will find 'docker' and carry on."
  echo "     No node has been run on Podman and no CI leg covers it, so you would be the first. If you"
  echo "     would rather not be:  curl -fsSL https://get.docker.com | sh"
  die "Podman is here, Docker is not, and the node needs a 'docker' command. The three lines above give it one."
elif ! need docker; then
  say "there is no container runtime on this machine, and the node is two containers. Installing Docker."
  sudo_first "installing Docker"
  case "$PLATFORM" in
    *arch*) echo "     sudo pacman -Sy --noconfirm docker docker-compose   (the packages)"
            echo "     sudo systemctl enable --now docker                  (so it starts with the machine)"
            watch_run "pacman could not install docker — check the network and the mirrors" \
              sudo pacman -Sy --noconfirm docker docker-compose
            sudo systemctl enable --now docker || true;;
    *)      echo "     curl -fsSL https://get.docker.com | sh              (Docker's own installer; it uses sudo itself)"
            # get.docker.com works out which distribution it is on, and on an Ubuntu DERIVATIVE it can get
            # that wrong in a way that poisons apt. Lucas is on Linux Mint 22.3. Its `lsb_release -a -u`
            # exited non-zero, so Docker's script skipped its forked-distro path, read /etc/debian_version
            # — which on an Ubuntu noble base says "trixie/sid" — concluded Debian trixie, added the DEBIAN
            # repository and tried to install Debian packages onto Ubuntu:
            #     deb [...] https://download.docker.com/linux/debian trixie stable
            #     E: Unable to correct problems, you have held broken packages.
            #
            # /etc/os-release already carries UBUNTU_CODENAME, which is the one fact needed, so on a
            # derivative we neither guess nor let it guess. The commands below are Docker's own documented
            # Ubuntu procedure — what its script would have run had it detected correctly. Mint, Pop!_OS,
            # elementary and Zorin all land here.
            UBU_CODENAME="$( . /etc/os-release 2>/dev/null && echo "${UBUNTU_CODENAME:-}" )"
            DIST_ID="$( . /etc/os-release 2>/dev/null && echo "${ID:-}" )"
            if [[ -n "$UBU_CODENAME" && "$DIST_ID" != ubuntu ]]; then
              say "this is ${DIST_ID:-a derivative} on Ubuntu ${UBU_CODENAME}. Using Docker's Ubuntu repository directly —"
              echo "     Docker's own installer mis-reads derivatives as Debian and leaves apt broken."
              # A previous attempt may already have left the wrong repository behind, and apt will keep
              # failing while it is there. Remove it before adding the right one.
              if [[ -f /etc/apt/sources.list.d/docker.list ]] && ! grep -q "linux/ubuntu ${UBU_CODENAME}" /etc/apt/sources.list.d/docker.list; then
                warn "removing an earlier Docker repository that does not match this machine"
                sudo rm -f /etc/apt/sources.list.d/docker.list
              fi
              watch_run "could not add Docker's Ubuntu repository — see the log" bash -c '
                set -e
                sudo apt-get -qq update
                sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq install ca-certificates curl
                sudo install -m 0755 -d /etc/apt/keyrings
                sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
                sudo chmod a+r /etc/apt/keyrings/docker.asc
                printf "deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n" \
                  "$(dpkg --print-architecture)" "'"$UBU_CODENAME"'" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null'
              echo "     repository added. Now the packages — this is the large download."
              watch_run "the Docker packages would not install. The log has apt's own words; 'sudo apt-get -f install' often names the conflict" bash -c '
                set -e
                sudo apt-get -qq update
                sudo DEBIAN_FRONTEND=noninteractive apt-get -y -qq install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin'
            else
              echo "     the big one: several hundred MB of packages, and it says little while it works"
              watch_run "Docker's own installer failed — its output is in the log" \
                bash -c 'curl -fsSL https://get.docker.com | sh'
            fi
            ;;
  esac
  say "and one more, so you can use Docker without sudo every time — it adds your user to the docker group:"
  echo "     sudo usermod -aG docker $USER"
  sudo usermod -aG docker "$USER" || true
  warn "added you to the docker group"
fi
# the new group is not in this shell yet: continue under it now (sg), rather than dying with "permission denied
# while trying to connect to the docker API" and asking the person to log out and in
if ! docker info >/dev/null 2>&1; then
  say "docker group applied for this run (new terminals have it automatically)"
  use_docker_group || true
fi
docker info >/dev/null 2>&1 || die "Docker is installed but this user cannot reach it. Log out and back in (the docker group is new), then run the same line again."
docker compose version >/dev/null 2>&1 || die "docker compose plugin missing"
step_ok

# ---- .env
step "writing settings to .env"
if [[ ! -f .env ]]; then cp .env.example .env; chmod 600 .env; fi
setenv() { local k="$1" v="$2"; if grep -q "^${k}=" .env; then
  if [[ "$PLATFORM" == macos ]]; then sed -i '' "s|^${k}=.*|${k}=${v}|" .env; else sed -i "s|^${k}=.*|${k}=${v}|" .env; fi
  else echo "${k}=${v}" >> .env; fi; }
if [[ -n "$PRESET" ]]; then
  [[ -f "presets/${PRESET}.env" ]] || die "no preset '${PRESET}'. Available: $(ls presets/*.env 2>/dev/null | xargs -n1 basename | sed 's/.env//' | tr '\n' ' ')"
  say "applying preset: ${PRESET}"
  while IFS='=' read -r k v; do [[ "$k" =~ ^[A-Z_]+$ ]] && setenv "$k" "$v"; done < "presets/${PRESET}.env"
fi
[[ -n "$NOBOOT" ]] && setenv BOOTSTRAP 0
[[ -n "$NAME" ]] && setenv NODE_NAME "$NAME"
[[ -n "$SC"   ]] && setenv SC_DEVICES "$SC"
[[ -n "${SCUSER:-}" ]] && setenv SC_USER "$SCUSER"
[[ -n "${KIND:-}" ]] && setenv NODE_KIND "$KIND"
[[ -n "${TZ_:-}" ]] && setenv NODE_TZ "$TZ_"
[[ -n "$AG"   ]] && setenv AIRGRADIENT_HOSTS "$AG"
[[ -n "$PA"   ]] && setenv PURPLEAIR_HOSTS "$PA"
[[ -n "$INDOOR" ]] && setenv SENSOR_INDOOR 1
[[ -n "$NOBAD"  ]] && setenv BAD_ENABLED 0
grep -qE '^NODE_LAT=-?[0-9]' .env || die "this node needs coordinates: pass --lat and --lon, or --preset <site>"
if ! grep -qE '^(SC_DEVICES|SC_USER|AIRGRADIENT_HOSTS|PURPLEAIR_HOSTS)=.+' .env; then
  warn "no sensor configured — that is fine. On first start this node will pull 92 days of CAMS air quality"
  warn "and NASA POWER climatology for its coordinates, so it has something true to say before hardware arrives."
  warn "Add a sensor later with --sc / --airgradient / --purpleair, or edit .env."
fi
[[ -n "$LAT"  ]] && setenv NODE_LAT "$LAT"
[[ -n "$LON"  ]] && setenv NODE_LON "$LON"
# from git in a clone, from the VERSION file the tarball carries otherwise. Testers install from the tarball,
# where git describe has nothing to read, and every one of them reported their version as "dev".
setenv NODE_VERSION "$(git describe --tags --always 2>/dev/null || cat VERSION 2>/dev/null || echo dev)"
NEWPW=0
grep -q '^POSTGRES_PASSWORD=change-me' .env && { setenv POSTGRES_PASSWORD "$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"; NEWPW=1; }
# A new .env means a new database password, and a database from an earlier node may still be on this machine (the
# tester deleted the folder to "start over" but Docker kept the volume). The app would then fail to log in on every
# call while pg_isready and the install's own doctor say the database is fine. Refuse now and say which way out.
if [[ $NEWPW -eq 1 ]]; then
  DATA_DIR_SET="$(grep '^DATA_DIR=' .env | cut -d= -f2 | sed 's/[[:space:]]*#.*$//' | tr -d ' ')"
  # The volume is named after the compose project, and docker-compose.yml pins `name: planetai`, so the
  # volume is planetai_db whatever the folder is called — a tarball install lives in `planetai-node`, and a
  # guard that derives the name from the folder looks for planetai-node_db, finds nothing, and waves a
  # password-changing reinstall past the old node's data (the v0.80.1 update reports). COMPOSE_PROJECT_NAME
  # overrides the pin, so honour it first.
  DBVOL="${COMPOSE_PROJECT_NAME:-planetai}_db"
  if { [[ -z "$DATA_DIR_SET" ]] && docker volume inspect "$DBVOL" >/dev/null 2>&1; } || { [[ -n "$DATA_DIR_SET" && -f "$DATA_DIR_SET/PG_VERSION" ]]; }; then
    warn "a database from an earlier node is still on this machine (${DATA_DIR_SET:-Docker volume $DBVOL}), and this is a new .env,"
    warn "so its password cannot match. Two ways out:"
    warn "  keep that data:  put the earlier .env back in this folder, then run this again"
    warn "  start clean:     docker volume rm $DBVOL   (this deletes the old node's readings), then run this again"
    die "not starting a node whose app cannot log in to its database"
  fi
fi
  [[ -n "$(grep -E "^ADMIN_TOKEN=" .env | cut -d= -f2- | sed "s/[[:space:]]*#.*//" | tr -d " ")" ]] || setenv ADMIN_TOKEN "$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"     # unlocks the GUI's settings pages

step_ok

# ---- port clash check
PORT="$(grep '^APP_PORT=' .env | cut -d= -f2 | sed 's/[[:space:]]*#.*$//' | tr -d ' ')"; PORT="${PORT:-8080}"
if [[ -n "$(docker compose ps -q app 2>/dev/null)" ]]; then :; elif lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  warn "port $PORT is already in use on this machine:"; lsof -nP -iTCP:"$PORT" -sTCP:LISTEN | tail -n +2 | awk '{print "     "$1" (pid "$2")"}' | sort -u
  die "set APP_PORT=8081 (or any free port) in .env and re-run"
fi

# ---- up
step "creating the folders the containers write to"
# create the bind-mounted folders first: on Linux, Docker makes a missing one root-owned, and backup.sh then cannot write
mkdir -p backups exports out
step_ok

# `docker compose pull` prints almost nothing when its output is not a terminal — which is exactly the
# case a tester pastes into an issue, and the reason the heartbeat had nothing to show. `docker pull`
# does print one line per layer, piped or not, so pull the image by name. Same result, visible progress.
DB_IMAGE="$(docker compose config --images 2>/dev/null | grep -E '[a-z0-9._-]+/[a-z0-9._-]+' | head -1)"
DB_IMAGE="${DB_IMAGE:-imresamu/postgis:16-3.4-alpine}"
step "downloading the database image ${DB_IMAGE} (about 162 MB)"
watch_run "the database image did not arrive. The log has the reason; the resume command retries." \
  docker pull "$DB_IMAGE"
step_ok

# BUILDKIT_PROGRESS=plain: the fancy renderer redraws with escape codes and leaves a log nobody can read.
# Plain prints one line per build step, which is what the heartbeat reports and what a tester can paste.
step "building this node's own image and starting both containers"
BUILDKIT_PROGRESS=plain watch_run "the image would not build, or a container would not start" \
  docker compose up -d --build
step_ok

# ---- schema on an existing volume (init.sql only runs when the volume is created)
step "waiting for the database, then applying the schema"
for i in $(seq 30); do
  docker compose exec -T db pg_isready -U planetai >/dev/null 2>&1 && break
  (( i % 5 == 0 )) && printf '        %4ds  waiting for the database to accept connections\n' $((SECONDS-STEP_T0))
  sleep 2
done
if docker compose exec -T db pg_isready -U planetai >/dev/null 2>&1; then
  docker compose exec -T db psql -q -v ON_ERROR_STOP=1 -U planetai planetai < init.sql >>"$LOG_FILE" 2>&1 \
    || printf '        the schema was already there (a fresh volume applies it itself)\n'
else
  printf '        the database did not answer in 60s — the checks below will say so\n'
fi
step_ok

# ---- doctor
step "checking what is running"
sleep 2
ok=1
chk() { if eval "$2" >/dev/null 2>&1; then echo "  ✓ $1"; else echo "  ✗ $1"; ok=0; fi; }
echo "doctor:"
chk "all modules in image" "[ \"\$(ls app/*.py | wc -l)\" -eq \"\$(docker compose exec -T app sh -c 'ls /app/*.py | wc -l')\" ]"
chk "db healthy"      "docker compose exec -T db pg_isready -U planetai"
PORT="$(grep '^APP_PORT=' .env | cut -d= -f2 | sed 's/[[:space:]]*#.*$//' | tr -d ' ')"; PORT="${PORT:-8080}"
chk "app answering"   "curl -sf localhost:${PORT}/health"
chk "telegram set"    "grep -qE '^TELEGRAM_BOT_TOKEN=.+' .env"
[[ -x backup.sh ]] || { chmod +x backup.sh; echo "  ✓ backup.sh made executable"; }
step_ok
[[ $ok -eq 1 ]] || warn "something's off: docker compose logs -f app"
grep -qE '^TELEGRAM_BOT_TOKEN=.+' .env || warn "alerts go to the log only until TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_IDS are set in .env (then: docker compose up -d)"

# ---- backup cron (best effort; skip silently if no crontab)
if need crontab && ! grep -q planetai-backup <<< "$(crontab -l 2>/dev/null)"; then
  ( crontab -l 2>/dev/null; echo "17 3 * * * cd $(pwd) && ./backup.sh >/dev/null 2>&1 # planetai-backup" ) | crontab - 2>/dev/null && say "nightly backup scheduled (03:17)"
fi

echo
if grep -qE 'api\.telegram\.org/bot[0-9]+:' <<< "$(docker compose logs app 2>/dev/null)"; then
  warn "a Telegram bot token is visible in this node's container logs (from a version before v0.4.3)."
  warn "Revoke it: message @BotFather -> /revoke -> pick the bot -> put the new token in .env -> make restart"
  warn "Then clear the old logs: docker compose down && docker compose up -d"
fi
echo
if grep -q '^BOOTSTRAP=1' .env; then
  say "first start pulls ~2,200 rows of history for your location (CAMS 92 days + NASA POWER normals)."
  echo "   watch it:  docker compose logs -f app | grep bootstrap"
fi
# One line, pasteable without editing, success or failure.
NAME_NOW="$(grep '^NODE_NAME=' .env | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' | tr -d ' ')"
printf '\ninstall OK — %s, %d steps in %ds, on localhost:%s\n' "${NAME_NOW:-this node}" "$STEP_TOTAL" $((SECONDS-RUN_T0)) "$PORT"
printf 'log: %s\n' "$LOG_FILE"
say "First reading lands within $(grep '^POLL_SECONDS' .env | cut -d= -f2 || echo 300)s."
echo "   make health     (or: curl -s localhost:${PORT}/health | python3 -m json.tool)"
echo "   make stats"
echo "   docker compose logs -f app"
