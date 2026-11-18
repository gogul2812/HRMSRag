# =============================================================================
# Start local RAG stack (Docker + APIs + frontends)
# =============================================================================
#   cd C:\path\to\rag-platform
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\scripts\start_local.ps1
# Stop: .\scripts\stop_local.ps1
# =============================================================================

$ErrorActionPreference = "Continue"

# Avoid Windows system DEBUG=release breaking pydantic bool fields
Remove-Item Env:DEBUG -ErrorAction SilentlyContinue
$env:APP_DEBUG = "true"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path (Join-Path $Root "docker-compose.dev.yml"))) {
  Write-Host "FAIL: Run this from the INNER rag-platform folder (where docker-compose.dev.yml lives)." -ForegroundColor Red
  exit 1
}

if (-not (Test-Path ".env")) {
  Write-Host "FAIL: .env missing. Run .\scripts\setup_local.ps1 first." -ForegroundColor Red
  exit 1
}

# Load .env (strip optional quotes; skip bad lines)
Get-Content .env | ForEach-Object {
  $line = $_.Trim()
  if ($line -eq "" -or $line.StartsWith("#")) { return }
  $eq = $line.IndexOf("=")
  if ($eq -lt 1) { return }
  $key = $line.Substring(0, $eq).Trim()
  $val = $line.Substring($eq + 1).Trim()
  if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
    $val = $val.Substring(1, $val.Length - 2)
  }
  [Environment]::SetEnvironmentVariable($key, $val, "Process")
}

# Local defaults
if (-not $env:LLM_ROUTER_MODE) { $env:LLM_ROUTER_MODE = "litellm" }
if (-not $env:CHAT_FAKE_ORCHESTRATOR) { $env:CHAT_FAKE_ORCHESTRATOR = "0" }
if (-not $env:EMBEDDING_MODEL_NAME) { $env:EMBEDDING_MODEL_NAME = "fake" }
if (-not $env:RERANKER_MODEL_NAME) { $env:RERANKER_MODEL_NAME = "fake" }
if (-not $env:RETRIEVAL_SCORE_THRESHOLD -and $env:RERANKER_MODEL_NAME -match '^(fake|stub|test)$') {
  $env:RETRIEVAL_SCORE_THRESHOLD = "0.15"
}
if (-not $env:PII_SCRUB_MODE) { $env:PII_SCRUB_MODE = "regex" }
# This script always starts a real ingestion-worker (see Start-CeleryWorker below),
# so uploads run async through it. Only force eager mode if you truly don't want
# a worker - set CELERY_TASK_ALWAYS_EAGER=1 in .env yourself.
if (-not $env:CELERY_TASK_ALWAYS_EAGER) { $env:CELERY_TASK_ALWAYS_EAGER = "0" }
if (-not $env:OTEL_SDK_DISABLED) { $env:OTEL_SDK_DISABLED = "true" }
$env:APP_DEBUG = "true"

# OCR needs the Tesseract binary itself, not just the pytesseract wrapper.
$tesseractDir = "C:\Program Files\Tesseract-OCR"
if ((Test-Path $tesseractDir) -and ($env:Path -notlike "*$tesseractDir*")) {
  $env:Path = "$tesseractDir;$env:Path"
}

if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = "raguser" }
if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = "ragplatform" }

if (-not $env:DATABASE_URL -or $env:DATABASE_URL -match 'CHANGE_ME|\$\{') {
  $env:DATABASE_URL = "postgresql+asyncpg://$($env:POSTGRES_USER):$($env:POSTGRES_PASSWORD)@127.0.0.1:15432/$($env:POSTGRES_DB)"
}
if (-not $env:DATABASE_URL_SYNC -or $env:DATABASE_URL_SYNC -match 'CHANGE_ME|\$\{') {
  $env:DATABASE_URL_SYNC = "postgresql://$($env:POSTGRES_USER):$($env:POSTGRES_PASSWORD)@127.0.0.1:15432/$($env:POSTGRES_DB)"
}
if (-not $env:REDIS_URL -or $env:REDIS_URL -match 'CHANGE_ME|\$\{' -or $env:REDIS_URL -match ':6379') {
  $env:REDIS_URL = "redis://:$($env:REDIS_PASSWORD)@127.0.0.1:16379/0"
}
$env:CELERY_BROKER_URL = $env:REDIS_URL
$env:CELERY_RESULT_BACKEND = $env:REDIS_URL
$env:QDRANT_HOST = "127.0.0.1"

Write-Host "> Starting Docker infra..."
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Docker is not running. Starting Docker Desktop..."
  $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerExe) { Start-Process $dockerExe }
  for ($i = 0; $i -lt 36; $i++) {
    Start-Sleep -Seconds 5
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
  }
}
docker compose -f docker-compose.dev.yml -f docker-compose.override.yml up -d

$logDir = Join-Path $Root "logs\local"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$PythonExe = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
  $PythonExe = "python"
  Write-Host "WARN: .venv not found. Run .\scripts\setup_local.ps1 first." -ForegroundColor Yellow
}

function Start-Uvicorn([string]$name, [string]$rel, [int]$port) {
  $wd = Join-Path $Root $rel
  $out = Join-Path $logDir "$name.out.log"
  $err = Join-Path $logDir "$name.err.log"
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) {
      Write-Host "  $name already up :$port"
      return
    }
  } catch {}
  Write-Host "  starting $name :$port"
  $env:APP_DEBUG = "true"
  Remove-Item Env:DEBUG -ErrorAction SilentlyContinue
  Start-Process -FilePath $PythonExe `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$port") `
    -WorkingDirectory $wd `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -WindowStyle Hidden | Out-Null
}

function Start-CeleryWorker([string]$rel) {
  $wd = Join-Path $Root $rel
  $out = Join-Path $logDir "ingestion-worker.out.log"
  $err = Join-Path $logDir "ingestion-worker.err.log"
  $already = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*celery*app.worker.celery_app*' }
  if ($already) {
    Write-Host "  ingestion-worker already running (PID $($already.ProcessId -join ', '))"
    return
  }
  Write-Host "  starting ingestion-worker (celery)"
  # --pool=solo: Windows has no os.fork; prefork/eventlet pools don't work here.
  Start-Process -FilePath $PythonExe `
    -ArgumentList @("-m", "celery", "-A", "app.worker.celery_app", "worker", "--loglevel=INFO", "--pool=solo") `
    -WorkingDirectory $wd `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -WindowStyle Hidden | Out-Null
}

Write-Host "> Starting API services..."
Start-Uvicorn "auth-service" "services\auth-service" 8001
Start-Uvicorn "gateway" "services\gateway" 8000
Start-Uvicorn "admin-config-service" "services\admin-config-service" 8002
Start-Uvicorn "ingestion-service" "services\ingestion-service" 8003
Start-Uvicorn "retrieval-service" "services\retrieval-service" 8004
Start-Uvicorn "llm-orchestrator-service" "services\llm-orchestrator-service" 8005
Start-Uvicorn "chat-service" "services\chat-service" 8006

Write-Host "> Starting ingestion worker (async document processing)..."
Start-CeleryWorker "services\ingestion-service"

Write-Host "> Starting frontends..."
$frontendRoot = Join-Path $Root "frontend"
$npmCmd = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmCmd) { $npmCmd = "C:\Program Files\nodejs\npm.cmd" }
$feLog = Join-Path $Root "logs\local"
Start-Process -FilePath $npmCmd -ArgumentList @("run", "dev:admin") -WorkingDirectory $frontendRoot `
  -RedirectStandardOutput (Join-Path $feLog "admin-portal.out.log") `
  -RedirectStandardError (Join-Path $feLog "admin-portal.err.log") `
  -WindowStyle Hidden
Start-Process -FilePath $npmCmd -ArgumentList @("run", "dev:user") -WorkingDirectory $frontendRoot `
  -RedirectStandardOutput (Join-Path $feLog "user-portal.out.log") `
  -RedirectStandardError (Join-Path $feLog "user-portal.err.log") `
  -WindowStyle Hidden
Write-Host "  (admin :3000, user :3001 - wait ~15s then open browser)"

Write-Host ""
Write-Host "Waiting for gateway health..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2
    if ($r.StatusCode -eq 200) { $ready = $true; break }
  } catch {}
  Start-Sleep -Seconds 2
}

Write-Host ""
if ($ready) {
  Write-Host "OK: Stack is up" -ForegroundColor Green
} else {
  Write-Host "WARN: Gateway not healthy yet - check logs\local\*.err.log" -ForegroundColor Yellow
}
Write-Host "  Admin:   http://localhost:3000"
Write-Host "  User:    http://localhost:3001"
Write-Host "  Gateway: http://localhost:8000/health"
Write-Host ""
Write-Host "If documents stay Pending/Processing: check logs\local\ingestion-worker.err.log"
Write-Host "  (first upload after a restart loads the embedding model into memory - can take"
Write-Host "  10-60s with a real model name, then every upload after that is fast)."
Write-Host "First-time users: .\scripts\bootstrap_demo.ps1"
Write-Host "API keys: docs\API_KEYS.md"
if ($env:GROQ_API_KEY -match 'CHANGE_ME|^$') {
  Write-Host "WARN: GROQ_API_KEY is not set yet." -ForegroundColor Yellow
}
if ($env:EMBEDDING_MODEL_NAME -match '^(fake|stub|test)$') {
  Write-Host "WARN: EMBEDDING_MODEL_NAME=fake - retrieval is a stub, not real semantic search." -ForegroundColor Yellow
}
