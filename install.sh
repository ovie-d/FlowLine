#!/usr/bin/env bash
# Flowline one-line installer for Linux and macOS:
#
#   curl -fsSL https://raw.githubusercontent.com/ovie-d/FlowLine/main/install.sh | bash
#
# Checks the prerequisites (Docker, git, Node.js 20+, Python 3.11+), clones Flowline
# (or updates an existing clone) and runs ./start.sh, which installs the rest and opens
# the app. Nothing is installed system-wide and no keys are needed.
#
# Options (environment variables):
#   FLOWLINE_DIR     where to put Flowline          (default: ~/flowline)
#   FLOWLINE_BRANCH  which branch to install         (default: main)
#   FLOWLINE_REPO    git URL                         (default: https://github.com/ovie-d/FlowLine.git)
#   FLOWLINE_NO_START=1  clone/update only, don't start
#
# Everything lives in main(), so a partly downloaded script never runs half-way.
set -euo pipefail

main() {
  local repo="${FLOWLINE_REPO:-https://github.com/ovie-d/FlowLine.git}"
  local branch="${FLOWLINE_BRANCH:-main}"
  local dir="${FLOWLINE_DIR:-$HOME/flowline}"
  local os missing=() notes=()
  os="$(uname -s)"

  say()  { printf '\033[1;33m▸\033[0m %s\n' "$*"; }
  ok()   { printf '\033[1;32m✓\033[0m %s\n' "$*"; }
  bad()  { printf '\033[1;31m✗\033[0m %s\n' "$*"; }

  case "$os" in
    Linux|Darwin) ;;
    *) bad "This installer is for Linux and macOS. On Windows use install.ps1 (see the README)."; exit 1 ;;
  esac
  say "Checking prerequisites…"

  # ---- git
  if command -v git >/dev/null; then ok "git $(git --version | awk '{print $3}')"
  elif [[ "$os" == Darwin ]]; then missing+=("git: run 'xcode-select --install' (or https://git-scm.com/downloads)")
  else missing+=("git: install it with your package manager (e.g. 'sudo apt install git') or https://git-scm.com/downloads"); fi

  # ---- Docker (installed and running; start.sh can use the docker group via sg)
  if ! command -v docker >/dev/null; then
    if [[ "$os" == Darwin ]]; then missing+=("Docker Desktop: https://docs.docker.com/desktop/setup/install/mac-install/")
    else missing+=("Docker Engine: https://docs.docker.com/engine/install/ (then add yourself to the docker group: https://docs.docker.com/engine/install/linux-postinstall/)"); fi
  elif docker info >/dev/null 2>&1 || { id -nG "$USER" 2>/dev/null | grep -qw docker && sg docker -c "docker info" >/dev/null 2>&1; }; then
    ok "Docker $(docker --version | awk '{print $3}' | tr -d ,) (running)"
  elif [[ "$os" == Darwin ]]; then
    notes+=("Docker Desktop is installed but not running; start.sh will try to start it.")
    ok "Docker $(docker --version | awk '{print $3}' | tr -d ,) (not running yet)"
  else
    missing+=("Docker is installed but not running or not accessible: 'sudo systemctl start docker', and add yourself to the docker group (https://docs.docker.com/engine/install/linux-postinstall/), then log out and back in")
  fi

  # ---- Node.js 20+ and npm
  if command -v node >/dev/null && command -v npm >/dev/null; then
    local node_major
    node_major="$(node -p 'process.versions.node.split(".")[0]')"
    if (( node_major >= 20 )); then ok "Node.js $(node -v)"
    else missing+=("Node.js 20 or newer (you have $(node -v)): https://nodejs.org/en/download"); fi
  else
    missing+=("Node.js 20+ with npm: https://nodejs.org/en/download")
  fi

  # ---- Python 3.11+ with venv
  if command -v python3 >/dev/null; then
    if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
      if python3 -c 'import venv, ensurepip' 2>/dev/null; then ok "Python $(python3 -V | awk '{print $2}')"
      else missing+=("Python venv support: 'sudo apt install python3-venv' (Debian/Ubuntu) or your distro's equivalent"); fi
    else
      missing+=("Python 3.11 or newer (you have $(python3 -V 2>&1 | awk '{print $2}')): https://www.python.org/downloads/")
    fi
  else
    missing+=("Python 3.11+: https://www.python.org/downloads/")
  fi

  command -v curl >/dev/null || missing+=("curl: install it with your package manager")

  if (( ${#missing[@]} )); then
    echo
    bad "Missing before Flowline can run:"
    for m in "${missing[@]}"; do printf '   • %s\n' "$m"; done
    echo
    echo "Install those, then run the same command again."
    exit 1
  fi
  for n in "${notes[@]+"${notes[@]}"}"; do say "$n"; done

  # ---- get the code
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

  if [[ "${FLOWLINE_NO_START:-0}" == "1" ]]; then
    echo "Start it with: cd \"$dir\" && ./start.sh"
    exit 0
  fi
  say "Starting Flowline (first run installs packages and builds the app; a few minutes)…"
  cd "$dir"
  ./start.sh </dev/null
  echo
  ok "Next time: cd \"$dir\" && ./start.sh    Stop: ./stop.sh"
}

main "$@"
