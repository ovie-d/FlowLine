# Stop everything started by start.ps1 (web app, API, containers). Data is kept.
Set-Location $PSScriptRoot

if (Test-Path .run\setup.pid) {
  $procId = [int](Get-Content .run\setup.pid)
  if (Get-Process -Id $procId -ErrorAction SilentlyContinue) {
    taskkill /PID $procId /T /F *> $null
    Write-Host "stopped background setup ($procId); it resumes on the next start"
  }
  Remove-Item .run\setup.pid, .run\routing-building -ErrorAction SilentlyContinue
}

foreach ($name in @("web", "api")) {
  $pidFile = ".run\$name.pid"
  if (Test-Path $pidFile) {
    $procId = [int](Get-Content $pidFile)
    # /T stops the process tree (node / uvicorn children).
    taskkill /PID $procId /T /F *> $null
    Write-Host "stopped $name ($procId)"
    Remove-Item $pidFile
  }
}

docker compose stop
Write-Host "Flowline stopped (database volume and OSRM data are kept)."
