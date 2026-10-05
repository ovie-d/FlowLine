# Flowline one-command launcher (Windows PowerShell 5.1+ / PowerShell 7).
#   powershell -ExecutionPolicy Bypass -File start.ps1 [-NoOpen]
# Stop with stop.ps1. Logs go to logs\, process ids to .run\.
param([switch]$NoOpen)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$ApiPort = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
$WebPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { "3000" }

function Say($m) { Write-Host "> $m" -ForegroundColor Yellow }
function Ok($m) { Write-Host "OK $m" -ForegroundColor Green }
function Die($m) { Write-Host "!! $m" -ForegroundColor Red; exit 1 }

New-Item -ItemType Directory -Force -Path logs, .run | Out-Null

# ---------------------------------------------------------------- Docker
docker info *> $null
if ($LASTEXITCODE -ne 0) {
  $desktop = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
  if (Test-Path $desktop) {
    Say "Starting Docker Desktop (finish any setup prompts in its window)..."
    Start-Process $desktop
    for ($i = 0; $i -lt 90; $i++) {
      Start-Sleep -Seconds 2
      docker info *> $null
      if ($LASTEXITCODE -eq 0) { break }
    }
  }
  docker info *> $null
  if ($LASTEXITCODE -ne 0) { Die "Docker is not running. Start Docker Desktop and try again." }
}
Ok "Docker is running"

# ---------------------------------------------------------------- config
if (-not (Test-Path .env)) {
  Say "Creating .env from .env.example (add GEMINI_API_KEY for the AI briefing)"
  $lines = Get-Content .env.example
  $cut = ($lines | Select-String -Pattern "^# Frontend" | Select-Object -First 1).LineNumber
  $lines[0..($cut - 2)] | Set-Content .env
}
if (-not (Test-Path .env.local)) {
  Say "Creating .env.local (add NEXT_PUBLIC_MAPBOX_TOKEN for the basemap)"
  "NEXT_PUBLIC_API_URL=http://127.0.0.1:$ApiPort`nNEXT_PUBLIC_MAPBOX_TOKEN=`nNEXT_PUBLIC_MAP_STYLE=dark" |
    Set-Content .env.local
}

# ---------------------------------------------------------------- dependencies
$Py = ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
  Say "Creating Python venv and installing requirements (first run only)..."
  py -3 -m venv .venv
  & $Py -m pip install -q --upgrade pip
  & $Py -m pip install -q -r requirements.txt
  if ($LASTEXITCODE -ne 0) { Die "pip install failed." }
}
if (-not (Test-Path node_modules)) {
  Say "Installing Node packages (first run only)..."
  npm ci --no-audit --no-fund
  if ($LASTEXITCODE -ne 0) { Die "npm ci failed." }
}
Ok "Dependencies ready"

foreach ($port in @($ApiPort, $WebPort)) {
  if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
    Die "Port $port is already in use. Run stop.ps1, or set API_PORT / WEB_PORT."
  }
}

# ---------------------------------------------------------------- services
$Services = @("db")
if (Test-Path "osrm\alberta-latest.osrm.mldgr") {
  $Services += "osrm"
} elseif (Test-Path "data\osm\alberta-latest.osm.pbf") {
  Say "Building OSRM routing data (one-time, ~5 minutes)..."
  & powershell -ExecutionPolicy Bypass -File scripts\build_osrm.ps1
  if ($LASTEXITCODE -ne 0) { Die "OSRM build failed." }
  $Services += "osrm"
} else {
  Write-Host "!! No OSM extract: dispatch falls back to Mapbox / straight-line distance." -ForegroundColor Red
}
Say "Starting $($Services -join ', ') (docker compose)..."
docker compose up -d --wait @Services
if ($LASTEXITCODE -ne 0) { Die "docker compose up failed." }
Ok "Containers healthy"

# ---------------------------------------------------------------- database
$count = & $Py -c "from core.env import load_dotenv; load_dotenv(); from core.pg import try_connect; c = try_connect(); print(c.execute('SELECT count(*) AS n FROM incidents').fetchone()['n'] if c else 0)" 2>$null
if (-not $count -or $count -eq "0") {
  $cer = "data\raw\pipeline-incidents-comprehensive-data.csv"
  if (-not (Test-Path $cer)) {
    Say "Downloading CER incident data..."
    New-Item -ItemType Directory -Force -Path data\raw | Out-Null
    Invoke-WebRequest https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-comprehensive-data.csv -OutFile $cer
    Invoke-WebRequest https://www.cer-rec.gc.ca/open/incident/pipeline-incidents-data-dictionary.csv `
      -OutFile data\raw\pipeline-incidents-data-dictionary.csv
  }
  if (-not (Test-Path data\processed\pipelines_ca.geojson)) { & $Py -m scripts.fetch_pipeline_systems }
  if (-not (Test-Path data\processed\incident_weather.csv)) {
    Write-Host "!! No weather data: similar-incident search runs without weather." -ForegroundColor Red
  }
  Say "Loading the database..."
  & $Py -m scripts.load_postgres
  if ($LASTEXITCODE -ne 0) { Die "Database load failed." }
}
Ok "Database ready"

# ---------------------------------------------------------------- app
# Rebuild only when .env.local, dependencies, config or frontend sources changed.
$files = @(".env.local", "package-lock.json", "next.config.ts", "postcss.config.mjs", "tsconfig.json") |
  Where-Object { Test-Path $_ }
$files += Get-ChildItem -Recurse -File app, components, lib, public | Sort-Object FullName | ForEach-Object FullName
$sha = [System.Security.Cryptography.SHA256]::Create()
$hashes = ($files | ForEach-Object { (Get-FileHash $_ -Algorithm SHA256).Hash }) -join ""
$stamp = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($hashes))) -replace "-", ""
$stampFile = ".next\flowline-build-stamp"
$oldStamp = if (Test-Path $stampFile) { Get-Content $stampFile } else { "" }
if ($env:FORCE_BUILD -eq "1" -or -not (Test-Path ".next\BUILD_ID") -or $oldStamp -ne $stamp) {
  Say "Building the web app (production; .env.local or frontend changed)..."
  npm run build *> logs\web-build.log
  if ($LASTEXITCODE -ne 0) { Die "Web build failed - see logs\web-build.log" }
  $stamp | Set-Content $stampFile
} else {
  Ok "Web build is up to date"
}

Say "Starting API on :$ApiPort and web app on :$WebPort..."
$api = Start-Process -FilePath ".venv\Scripts\uvicorn.exe" -PassThru -WindowStyle Hidden `
  -ArgumentList "api.main:app", "--host", "127.0.0.1", "--port", $ApiPort, "--workers", "1" `
  -RedirectStandardOutput logs\api.log -RedirectStandardError logs\api.err.log
$api.Id | Set-Content .run\api.pid
$web = Start-Process -FilePath "node" -PassThru -WindowStyle Hidden `
  -ArgumentList "node_modules\next\dist\bin\next", "start", "-p", $WebPort `
  -RedirectStandardOutput logs\web.log -RedirectStandardError logs\web.err.log
$web.Id | Set-Content .run\web.pid

for ($i = 0; $i -lt 90; $i++) {
  try {
    Invoke-WebRequest "http://127.0.0.1:$ApiPort/health" -UseBasicParsing -TimeoutSec 2 | Out-Null
    Invoke-WebRequest "http://127.0.0.1:$WebPort/" -UseBasicParsing -TimeoutSec 2 | Out-Null
    Ok "Flowline is up: http://localhost:$WebPort  (API http://127.0.0.1:$ApiPort/docs)"
    if (-not $NoOpen) { Start-Process "http://localhost:$WebPort" }
    exit 0
  } catch { Start-Sleep -Seconds 1 }
}
Die "Timed out waiting for the API or web app - see logs\api.err.log and logs\web.err.log"
