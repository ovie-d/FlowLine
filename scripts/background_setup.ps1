# First-run extras (Windows), started in the background by start.ps1 so the app opens first:
#   1. download the Alberta OSM extract (Geofabrik, ~350 MB) if it is missing
#   2. build the OSRM routing data (~5 min) and start the router
#   3. build the river-crossings map layer (~2 min)
# Until step 2 finishes, dispatch uses straight-line distance with a warning that routing
# is still being prepared (.run\routing-building). Skip with $env:FLOWLINE_ROUTING = "0".
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # Invoke-WebRequest is far faster without it
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Py = ".venv\Scripts\python.exe"
$Pbf = "data\osm\alberta-latest.osm.pbf"
$Url = if ($env:OSM_EXTRACT_URL) { $env:OSM_EXTRACT_URL } else { "https://download.geofabrik.de/north-america/canada/alberta-latest.osm.pbf" }
$Marker = ".run\routing-building"
function Log($m) { Write-Host "$(Get-Date -Format HH:mm:ss) $m" }

New-Item -ItemType Directory -Force -Path .run, data\osm, logs | Out-Null
try {
  if (-not (Test-Path "osrm\alberta-latest.osrm.mldgr")) {
    New-Item -ItemType File -Force -Path $Marker | Out-Null
    if (-not (Test-Path $Pbf)) {
      Log "Downloading the Alberta OSM extract (~350 MB) from Geofabrik..."
      Invoke-WebRequest $Url -OutFile "$Pbf.part" -UseBasicParsing
      $want = $null
      try { $want = ((Invoke-WebRequest "$Url.md5" -UseBasicParsing).Content -split '\s+')[0] }
      catch { Log "No checksum file; skipping verification." }
      if ($want -and $want -ne (Get-FileHash "$Pbf.part" -Algorithm MD5).Hash.ToLower()) {
        Remove-Item "$Pbf.part"
        throw "Checksum mismatch; the download restarts next time."
      }
      Move-Item "$Pbf.part" $Pbf -Force
      Log "Download complete."
    }
    Log "Building the OSRM routing data (one-time, ~5 minutes)..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File scripts\build_osrm.ps1
    if ($LASTEXITCODE -ne 0) { throw "OSRM build failed." }
    Log "Starting the router..."
    docker compose up -d --wait osrm
    if ($LASTEXITCODE -ne 0) { throw "Router did not start." }
    Remove-Item $Marker -ErrorAction SilentlyContinue
    Log "Road routing is ready (dispatch now uses drive times)."
  }

  $hasX = & $Py -c "from core.env import load_dotenv; load_dotenv(); from core.pg import try_connect; c = try_connect(); print(int(bool(c and c.execute('SELECT to_regclass(%s) IS NOT NULL AS ok', ('public.waterway_crossings',)).fetchone()['ok'])))" 2>$null
  if ($hasX -ne "1" -and (Test-Path $Pbf)) {
    Log "Building the river-crossings map layer (one-time, ~2 minutes)..."
    & $Py -m scripts.washout_crossings --layer-only
    if ($LASTEXITCODE -eq 0) { Log "River-crossings layer ready." }
    else { Log "River-crossings layer not built (the map works without it)." }
  }
  Log "Background setup finished."
} catch {
  Log "Background setup stopped: $($_.Exception.Message) It continues on the next start."
  exit 1
} finally {
  Remove-Item $Marker -ErrorAction SilentlyContinue
}
