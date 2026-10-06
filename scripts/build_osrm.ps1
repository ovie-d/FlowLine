# One-time OSRM preprocessing (car profile, MLD pipeline) of the Alberta extract (Windows).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\build_osrm.ps1 [-Force]
param([switch]$Force)
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Image = if ($env:OSRM_IMAGE) { $env:OSRM_IMAGE } else { "ghcr.io/project-osrm/osrm-backend:v26.10.0-debian" }
$Pbf = Join-Path $Root "data\osm\alberta-latest.osm.pbf"
$Out = Join-Path $Root "osrm"
$Base = "alberta-latest"
$Threads = if ($env:OSRM_THREADS) { $env:OSRM_THREADS } else { "4" }

if (-not (Test-Path $Pbf)) {
  throw "Missing $Pbf - download https://download.geofabrik.de/north-america/canada/alberta-latest.osm.pbf"
}
if ((Test-Path (Join-Path $Out "$Base.osrm.mldgr")) -and -not $Force) {
  Write-Host "OSRM data already built in $Out (use -Force to rebuild)."
  exit 0
}

New-Item -ItemType Directory -Force -Path $Out | Out-Null
Copy-Item $Pbf (Join-Path $Out "$Base.osm.pbf") -Force

function Invoke-Osrm { docker run --rm -v "${Out}:/data" $Image @args; if ($LASTEXITCODE) { throw "OSRM step failed" } }

Write-Host "[1/3] osrm-extract (car profile)..."
Invoke-Osrm osrm-extract -p /opt/car.lua -t $Threads "/data/$Base.osm.pbf"
Write-Host "[2/3] osrm-partition..."
Invoke-Osrm osrm-partition -t $Threads "/data/$Base.osrm"
Write-Host "[3/3] osrm-customize..."
Invoke-Osrm osrm-customize -t $Threads "/data/$Base.osrm"

Remove-Item (Join-Path $Out "$Base.osm.pbf")
Write-Host "Done. Start the router with: docker compose up -d osrm"
