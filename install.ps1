# Flowline one-line installer for Windows (PowerShell 5.1+ or 7):
#
#   irm https://raw.githubusercontent.com/ovie-d/FlowLine/main/install.ps1 | iex
#
# Checks the prerequisites (Docker Desktop, git, Node.js 20+, Python 3.11+) and offers to
# install missing ones with winget (asks first), clones Flowline (or updates it), asks for
# an optional Mapbox token, and runs start.ps1. No keys are needed: AI briefings use the
# Flowline online demo (3 per day) unless you add your own GEMINI_API_KEY to .env.
#
# Options (environment variables, set before running, e.g. $env:FLOWLINE_DIR = "D:\flowline"):
#   FLOWLINE_DIR     where to put Flowline   (default: $HOME\flowline)
#   FLOWLINE_BRANCH  which branch to install (default: main)
#   FLOWLINE_REPO    git URL                 (default: https://github.com/ovie-d/FlowLine.git)
#   FLOWLINE_YES = "1"       install missing prerequisites without asking
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

  # Re-read PATH after installs so new tools work in this same window.
  function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
      [Environment]::GetEnvironmentVariable("Path", "User")
  }

  # Returns the winget ids still needed (empty = all good) and prints what is fine.
  function Check-Prereqs([switch]$Quiet) {
    $need = [ordered]@{}
    if (Has git) { if (-not $Quiet) { Ok "git $((git --version) -replace 'git version ', '')" } }
    else { $need["Git.Git"] = "git" }
    if ((Has node) -and (Has npm) -and ([int]((node -p "process.versions.node.split('.')[0]") | Out-String).Trim() -ge 20)) {
      if (-not $Quiet) { Ok "Node.js $(node -v)" }
    } else { $need["OpenJS.NodeJS.LTS"] = "Node.js LTS" }
    $pyOk = $false
    if (Has py) {
      py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" 2>$null
      $pyOk = ($LASTEXITCODE -eq 0)
    }
    if ($pyOk) { if (-not $Quiet) { Ok "Python $((py -3 -V) -replace 'Python ', '')" } }
    else { $need["Python.Python.3.12"] = "Python 3.12 (with the py launcher)" }
    if (Has docker) { if (-not $Quiet) { Ok "Docker" } }
    else { $need["Docker.DockerDesktop"] = "Docker Desktop (see the licence note in the README)" }
    return $need
  }

  Say "Checking prerequisites..."
  $need = Check-Prereqs
  if ($need.Count -gt 0) {
    if (-not (Has winget)) {
      Write-Host ""
      Bad "Missing before Flowline can run (winget isn't available to install them for you):"
      $links = @{ "Git.Git" = "https://git-scm.com/download/win"; "OpenJS.NodeJS.LTS" = "https://nodejs.org/en/download";
        "Python.Python.3.12" = "https://www.python.org/downloads/windows/";
        "Docker.DockerDesktop" = "https://docs.docker.com/desktop/setup/install/windows-install/" }
      foreach ($id in $need.Keys) { Write-Host "   - $($need[$id]): $($links[$id])" }
      Write-Host "Install those, open a new terminal, then run the same command again."
      return
    }
    Write-Host ""
    Say "Flowline needs a few tools first. The installer will run:"
    foreach ($id in $need.Keys) { Write-Host "     winget install --id $id -e   # $($need[$id])" }
    if ($env:FLOWLINE_YES -ne "1") {
      $answer = Read-Host "   Install them now? Windows may ask for permission. [Y/n]"
      if ($answer -and $answer -notmatch '^(y|yes)$') { Bad "Nothing installed. Install the tools above, then run this again."; return }
    }
    foreach ($id in $need.Keys) {
      Say "Installing $($need[$id])..."
      winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements
      if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {  # -1978335189: already installed
        Bad "Installing $($need[$id]) failed. Install it by hand, then run this again."; return
      }
    }
    Refresh-Path
    if ($need.Contains("Docker.DockerDesktop")) {
      Write-Host ""
      Ok "Docker Desktop is installed."
      Write-Host "   Start Docker Desktop once from the Start menu and finish its setup (it may ask to"
      Write-Host "   enable WSL 2 and restart Windows). Then open a new PowerShell window and run the same"
      Write-Host "   command again to finish installing Flowline."
      return
    }
    $still = Check-Prereqs -Quiet
    if ($still.Count -gt 0) {
      Bad "Some tools aren't available in this window yet. Open a new PowerShell window and run the same command again."
      return
    }
    Ok "Prerequisites installed"
  }
  docker info *> $null
  if ($LASTEXITCODE -ne 0) { Say "Docker Desktop is installed but not running; start.ps1 will try to start it." }

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

  # Optional Mapbox token (Enter keeps the open maps). AI works without a key via the
  # Flowline online demo (3 prompts per day); your own GEMINI_API_KEY in .env wins.
  $envLocal = Join-Path $Dir ".env.local"
  if (-not (Test-Path $envLocal)) {
    $token = (Read-Host "Mapbox token for the Mapbox map styles (optional, free at https://account.mapbox.com; press Enter to use the open maps)").Trim()
    if ($token -and -not $token.StartsWith("pk.")) { Say "That doesn't look like a public Mapbox token (pk.); using the open maps."; $token = "" }
    "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`nNEXT_PUBLIC_MAPBOX_TOKEN=$token`nNEXT_PUBLIC_MAP_STYLE=dark" | Set-Content $envLocal
  }

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
