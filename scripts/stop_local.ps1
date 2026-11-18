# Stop local uvicorn services for the RAG platform.
# Frontends (npm) and Docker are left running unless -All is passed.
param(
  [switch]$All
)

Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match '^python' -and ($_.CommandLine -match 'uvicorn app.main:app' -or $_.CommandLine -match 'celery.*app\.worker\.celery_app') } |
  ForEach-Object {
    Write-Host "Stopping PID $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }

if ($All) {
  Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
    Where-Object { $_.CommandLine -match 'next|admin-portal|user-portal' } |
    ForEach-Object {
      Write-Host "Stopping node PID $($_.ProcessId)"
      Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
  $Root = Split-Path -Parent $PSScriptRoot
  Set-Location $Root
  docker compose -f docker-compose.dev.yml -f docker-compose.override.yml stop
}

Write-Host "Done."
