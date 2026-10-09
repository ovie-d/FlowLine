#!/usr/bin/env bash
# Flowline one-line installer for Linux and macOS:
#
#   curl -fsSL https://raw.githubusercontent.com/ovie-d/FlowLine/main/install.sh | bash
#
# 1. Checks the prerequisites (Docker, git, Node.js 20+, Python 3.11+) and offers to
#    install any that are missing, showing the exact commands and asking first.
# 2. Clones Flowline (or updates an existing clone).
# 3. Asks for an optional Mapbox token (Enter skips it: the app uses open maps).
# 4. Runs ./start.sh, which installs the Python/Node packages into the folder and opens
#    the app. AI briefings work without a key through the Flowline online demo
#    (3 per day); put your own GEMINI_API_KEY in .env for unlimited use.
#
# Options (environment variables):
#   FLOWLINE_DIR     where to put Flowline          (default: ~/flowline)
#   FLOWLINE_BRANCH  which branch to install         (default: main)
#   FLOWLINE_REPO    git URL                         (default: https://github.com/ovie-d/FlowLine.git)
#   FLOWLINE_YES=1   install missing prerequisites without asking
#   FLOWLINE_NO_START=1  clone/update only, don't start
#
# Everything lives in main(), so a partly downloaded script never runs half-way.
set -euo pipefail

main() {
  local repo="${FLOWLINE_REPO:-https://github.com/ovie-d/FlowLine.git}"
  local branch="${FLOWLINE_BRANCH:-main}"
  local dir="${FLOWLINE_DIR:-$HOME/flowline}"
  local os pm="" python="python3"
  USER="${USER:-$(id -un)}"
  os="$(uname -s)"

  say()  { printf '\033[1;33m▸\033[0m %s\n' "$*"; }
  ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
  bad()  { printf '\033[1;31m✗\033[0m %s\n' "$*"; }
  have() { command -v "$1" >/dev/null 2>&1; }
  # Questions go to the terminal even when this script arrives through a pipe.
  # (/dev/tty can exist without being openable: no controlling terminal, e.g. CI.)
  tty_ok() { { : </dev/tty; } 2>/dev/null; }
  ask() {
    local prompt="$1" reply=""
    if tty_ok; then
      printf '%s' "$prompt" > /dev/tty
      IFS= read -r reply < /dev/tty || true
    fi
    printf '%s' "$reply"
  }
  as_root() { if [[ $EUID -eq 0 ]]; then "$@"; else sudo "$@"; fi; }
  local SUDO="sudo "
  [[ $EUID -eq 0 ]] && SUDO=""

  case "$os" in
    Linux|Darwin) ;;
    *) bad "This installer is for Linux and macOS. On Windows use install.ps1 (see the README)."; exit 1 ;;
  esac
  if [[ "$os" == Linux ]]; then
    for p in apt-get dnf pacman; do have "$p" && { pm="$p"; break; }; done
  fi

  # ------------------------------------------------------------ what is missing
  local need_git=0 need_node=0 need_python=0 need_docker=0 docker_stopped=0
  check() {
    need_git=0 need_node=0 need_python=0 need_docker=0 docker_stopped=0
    have git || need_git=1
    if have node && have npm && (( $(node -p 'process.versions.node.split(".")[0]') >= 20 )); then :; else need_node=1; fi
    python=""
    for c in python3 python3.13 python3.12 python3.11; do
      if have "$c" && "$c" -c 'import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        python="$c"; break
      fi
    done
    [[ -n "$python" ]] || need_python=1
    if ! have docker; then
      need_docker=1
    elif ! docker info >/dev/null 2>&1 && ! { id -nG "$USER" 2>/dev/null | grep -qw docker && sg docker -c "docker info" >/dev/null 2>&1; }; then
      docker_stopped=1
    fi
  }
  say "Checking prerequisites…"
  check
  (( need_git ))    || ok "git $(git --version | awk '{print $3}')"
  (( need_node ))   || ok "Node.js $(node -v)"
  (( need_python )) || ok "Python $("$python" -V | awk '{print $2}')"
  (( need_docker || docker_stopped )) || ok "Docker $(docker --version | awk '{print $3}' | tr -d ,)"

  # ------------------------------------------------------------ install plan
  local plan=() manual=()
  if (( need_git || need_node || need_python || need_docker )); then
    if [[ "$os" == Darwin ]]; then
      have brew || plan+=('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"   # Homebrew')
      local pkgs=()
      (( need_git )) && pkgs+=(git)
      (( need_node )) && pkgs+=(node)
      (( need_python )) && pkgs+=(python@3.12)
      (( ${#pkgs[@]} )) && plan+=("brew install ${pkgs[*]}")
      (( need_docker )) && plan+=("brew install --cask docker   # Docker Desktop (see the licence note in the README)")
    elif [[ "$pm" == apt-get ]]; then
      local pkgs=(ca-certificates curl)
      (( need_git )) && pkgs+=(git)
      if (( need_python )); then
        # The distro's python3 is used if it is 3.11+; older Ubuntu gets 3.12 (deadsnakes).
        local cand
        cand="$(apt-cache policy python3 2>/dev/null | awk '/Candidate:/ {print $2}' | grep -oE '^[0-9]+\.[0-9]+' || true)"
        if [[ -n "$cand" ]] && printf '%s\n3.11\n' "$cand" | sort -V | head -1 | grep -qx 3.11; then
          pkgs+=(python3 python3-venv)
        elif grep -qi '^ID=ubuntu' /etc/os-release 2>/dev/null; then
          pkgs+=(software-properties-common)
          plan+=("${SUDO}apt-get update && ${SUDO}DEBIAN_FRONTEND=noninteractive apt-get install -y ${pkgs[*]}")
          pkgs=()
          plan+=("${SUDO}add-apt-repository -y ppa:deadsnakes/ppa && ${SUDO}DEBIAN_FRONTEND=noninteractive apt-get install -y python3.12 python3.12-venv   # Python 3.12")
        else
          manual+=("Python 3.11+ (your distribution's python3 is older): https://www.python.org/downloads/")
        fi
      fi
      (( ${#pkgs[@]} )) && plan+=("${SUDO}apt-get update && ${SUDO}DEBIAN_FRONTEND=noninteractive apt-get install -y ${pkgs[*]}")
      (( need_node )) && plan+=("curl -fsSL https://deb.nodesource.com/setup_22.x | ${SUDO:+sudo -E }bash - && ${SUDO}DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs   # Node.js 22 (NodeSource)")
      (( need_docker )) && plan+=("curl -fsSL https://get.docker.com | ${SUDO}sh && ${SUDO}usermod -aG docker $USER && ${SUDO}systemctl enable --now docker   # Docker Engine")
    elif [[ "$pm" == dnf ]]; then
      local pkgs=()
      (( need_git )) && pkgs+=(git)
      (( need_node )) && pkgs+=(nodejs npm)
      (( need_python )) && pkgs+=(python3)
      (( ${#pkgs[@]} )) && plan+=("${SUDO}dnf install -y ${pkgs[*]}")
      (( need_docker )) && plan+=("curl -fsSL https://get.docker.com | ${SUDO}sh && ${SUDO}usermod -aG docker $USER && ${SUDO}systemctl enable --now docker   # Docker Engine")
    elif [[ "$pm" == pacman ]]; then
      local pkgs=()
      (( need_git )) && pkgs+=(git)
      (( need_node )) && pkgs+=(nodejs npm)
      (( need_python )) && pkgs+=(python)
      (( need_docker )) && pkgs+=(docker docker-compose)
      plan+=("${SUDO}pacman -S --needed --noconfirm ${pkgs[*]}")
      (( need_docker )) && plan+=("${SUDO}usermod -aG docker $USER && ${SUDO}systemctl enable --now docker")
    else
      (( need_git )) && manual+=("git: https://git-scm.com/downloads")
      (( need_node )) && manual+=("Node.js 20+: https://nodejs.org/en/download")
      (( need_python )) && manual+=("Python 3.11+: https://www.python.org/downloads/")
      (( need_docker )) && manual+=("Docker Engine: https://docs.docker.com/engine/install/")
    fi
  fi

  if (( ${#manual[@]} )); then
    echo; bad "Please install these yourself, then run the same command again:"
    printf '   • %s\n' "${manual[@]}"
    exit 1
  fi
  if (( ${#plan[@]} )); then
    echo
    say "Flowline needs a few tools first. The installer will run:"
    printf '     %s\n' "${plan[@]}"
    if [[ "${FLOWLINE_YES:-0}" != "1" ]]; then
      local answer
      answer="$(ask "   Install them now? This may ask for your password. [Y/n] ")"
      if [[ -z "$answer" ]] && ! tty_ok; then
        bad "No terminal to ask in. Re-run with FLOWLINE_YES=1 to install automatically."; exit 1
      fi
      [[ "$answer" =~ ^([Yy]|[Yy]es|)$ ]] || { bad "Nothing installed. Install the tools above, then run this again."; exit 1; }
    fi
    local input=/dev/null
    tty_ok && input=/dev/tty
    for cmd in "${plan[@]}"; do
      say "${cmd%%   #*}"
      bash -c "${cmd%%   #*}" < "$input" || { bad "That step failed. Fix it (or install by hand), then run this again."; exit 1; }
    done
    if [[ "$os" == Darwin ]] && have brew; then eval "$(brew shellenv 2>/dev/null)" || true; fi
    if [[ "$os" == Darwin && "$need_docker" == 1 ]]; then open -a Docker || true; fi
    hash -r
    check
    if (( need_git || need_node || need_python || need_docker )); then
      bad "Some tools still aren't available in this terminal. Open a new terminal and run the same command again."
      exit 1
    fi
    ok "Prerequisites installed"
  fi
  if (( docker_stopped )); then
    if [[ "$os" == Darwin ]]; then
      say "Docker Desktop isn't running yet; start.sh will start it."
    else
      say "Starting Docker (may ask for your password)…"
      as_root systemctl start docker 2>/dev/null || true
      id -nG "$USER" | grep -qw docker || as_root usermod -aG docker "$USER" || true
    fi
  fi

  # ------------------------------------------------------------ get the code
  if [[ -d "$dir/.git" ]]; then
    say "Updating Flowline in $dir…"
    git -C "$dir" fetch --quiet origin "$branch"
    git -C "$dir" checkout --quiet "$branch"
    git -C "$dir" merge --ff-only --quiet FETCH_HEAD || {
      bad "Couldn't fast-forward $dir (local changes?). Update it by hand, or set FLOWLINE_DIR to a new folder."
      exit 1
    }
  elif [[ -e "$dir" ]]; then
    bad "$dir exists and is not a Flowline clone. Set FLOWLINE_DIR to another folder."
    exit 1
  else
    say "Downloading Flowline into $dir…"
    git clone --quiet --depth 1 --branch "$branch" "$repo" "$dir"
  fi
  ok "Flowline is in $dir"

  # ------------------------------------------------------------ optional map token
  if [[ ! -f "$dir/.env.local" ]]; then
    local token=""
    token="$(ask "Mapbox token for the Mapbox map styles (optional, free at https://account.mapbox.com; press Enter to use the open maps): ")"
    token="$(printf '%s' "$token" | tr -d '[:space:]')"
    if [[ -n "$token" && ! "$token" =~ ^pk\. ]]; then
      say "That doesn't look like a public Mapbox token (pk.…); using the open maps."
      token=""
    fi
    printf 'NEXT_PUBLIC_API_URL=http://127.0.0.1:8000\nNEXT_PUBLIC_MAPBOX_TOKEN=%s\nNEXT_PUBLIC_MAP_STYLE=dark\n' "$token" > "$dir/.env.local"
  fi

  if [[ "${FLOWLINE_NO_START:-0}" == "1" ]]; then
    echo "Start it with: cd \"$dir\" && ./start.sh"
    exit 0
  fi
  say "Starting Flowline (first run installs packages and builds the app; a few minutes)…"
  cd "$dir"
  FLOWLINE_PYTHON="$python" ./start.sh </dev/null
  echo
  ok "Next time: cd \"$dir\" && ./start.sh    Stop: ./stop.sh"
}

main "$@"
