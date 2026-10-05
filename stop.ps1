# Stop everything started by start.ps1 (web app, API, containers). Data is kept.
Set-Location $PSScriptRoot

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
