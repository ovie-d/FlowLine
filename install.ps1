# Flowline one-line installer for Windows (PowerShell 5.1+ or 7):
#
#   irm https://raw.githubusercontent.com/ovie-d/FlowLine/main/install.ps1 | iex
#
# Checks the prerequisites (Docker Desktop, git, Node.js 20+, Python 3.11+), clones
# Flowline (or updates an existing clone) and runs start.ps1, which installs the rest
# and opens the app. Nothing is installed system-wide and no keys are needed.
#
# Options (environment variables, set before running, e.g. $env:FLOWLINE_DIR = "D:\flowline"):
#   FLOWLINE_DIR     where to put Flowline   (default: $HOME\flowline)
#   FLOWLINE_BRANCH  which branch to install (default: main)
#   FLOWLINE_REPO    git URL                 (default: https://github.com/ovie-d/FlowLine.git)
#   FLOWLINE_NO_START = "1"  clone/update only
#
# Runs inside a script block and never calls `exit`, so it can't close your terminal.
& {
  $ErrorActionPreference = "Stop"
  $Repo = if ($env:FLOWLINE_REPO) { $env:FLOWLINE_REPO } else { "https://github.com/ovie-d/FlowLine.git" }
  $Branch = if ($env:FLOWLINE_BRANCH) { $env:FLOWLINE_BRANCH } else { "main" }
  $Dir = if ($env:FLOWLINE_DIR) { $env:FLOWLINE_DIR } else { Join-Path $HOME "flowline" }

  function Say($m) { Write-Host "> $m" -ForegroundColor Yellow }
  function Ok($m) { Write-Host "OK $m" -ForegroundColor Green }
  function Bad($m) { Write-Host "!! $m" -ForegroundColor Red }
  function Has($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

  Say "Checking prerequisites..."
  $missing = @()

  if (Has git) { Ok "git $((git --version) -replace 'git version ', '')" }
  else { $missing += "git: https://git-scm.com/download/win  (or: winget install Git.Git)" }

  if (-not (Has docker)) {
    $missing += "Docker Desktop: https://docs.docker.com/desktop/setup/install/windows-install/  (or: winget install Docker.DockerDesktop)"
  } else {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) { Ok "Docker (running)" }
    else { Say "Docker Desktop is installed but not running; start.ps1 will try to start it." }
  }

  if ((Has node) -and (Has npm)) {
    $major = [int]((node -p "process.versions.node.split('.')[0]") | Out-String).Trim()
    if ($major -ge 20) { Ok "Node.js $(node -v)" }
    else { $missing += "Node.js 20 or newer (you have $(node -v)): https://nodejs.org/en/download  (or: winget install OpenJS.NodeJS.LTS)" }
  } else {
    $missing += "Node.js 20+: https://nodejs.org/en/download  (or: winget install OpenJS.NodeJS.LTS)"
  }

  # start.ps1 creates the venv with the Python launcher (py -3).
  if (Has py) {
    py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
    if ($LASTEXITCODE -eq 0) { Ok "Python $((py -3 -V) -replace 'Python ', '')" }
    else { $missing += "Python 3.11 or newer (you have $(py -3 -V)): https://www.python.org/downloads/windows/  (or: winget install Python.Python.3.12)" }
  } else {
    $missing += "Python 3.11+ with the 'py' launcher: https://www.python.org/downloads/windows/  (or: winget install Python.Python.3.12)"
  }

  if ($missing.Count -gt 0) {
    Write-Host ""
    Bad "Missing before Flowline can run:"
    $missing | ForEach-Object { Write-Host "   - $_" }
    Write-Host ""
    Write-Host "Install those (open a new terminal afterwards so PATH updates), then run the same command again."
    return
  }

  if (Test-Path (Join-Path $Dir ".git")) {
    Say "Updating Flowline in $Dir..."
    git -C $Dir fetch --quiet origin $Branch
    git -C $Dir checkout --quiet $Branch
    git -C $Dir merge --ff-only --quiet FETCH_HEAD
    if ($LASTEXITCODE -ne 0) { Bad "Couldn't fast-forward $Dir (local changes?). Update it by hand, or set FLOWLINE_DIR."; return }
  } elseif (Test-Path $Dir) {
    Bad "$Dir exists and is not a Flowline clone. Set `$env:FLOWLINE_DIR to another folder."
    return
  } else {
    Say "Downloading Flowline into $Dir..."
    git clone --quiet --depth 1 --branch $Branch $Repo $Dir
    if ($LASTEXITCODE -ne 0) { Bad "git clone failed."; return }
  }
  Ok "Flowline is in $Dir"

  if ($env:FLOWLINE_NO_START -eq "1") {
    Write-Host "Start it with: powershell -ExecutionPolicy Bypass -File `"$Dir\start.ps1`""
    return
  }
  Say "Starting Flowline (first run installs packages and builds the app; a few minutes)..."
  # A separate Windows PowerShell process so the script runs regardless of the execution policy.
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dir "start.ps1")
  Write-Host ""
  Ok "Next time: powershell -ExecutionPolicy Bypass -File `"$Dir\start.ps1`"   Stop: stop.ps1"
}
