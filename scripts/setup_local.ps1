# =============================================================================
# RAG Platform - first-time setup (Windows PowerShell)
# =============================================================================
# ALWAYS run from the folder that contains docker-compose.dev.yml
# (the inner "rag-platform" folder, NOT the parent zip folder).
#
#   cd C:\path\to\rag-platform
#   Set-ExecutionPolicy -Scope Process Bypass
#   .\scripts\setup_local.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

# Avoid Windows system DEBUG=release breaking pydantic bool fields
Remove-Item Env:DEBUG -ErrorAction SilentlyContinue
$env:APP_DEBUG = "true"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Fail([string]$msg) {
  Write-Host ""
  Write-Host "FAIL: $msg" -ForegroundColor Red
  exit 1
}

function Step([string]$n, [string]$msg) {
  Write-Host ""
  Write-Host "==== Step $n : $msg ====" -ForegroundColor Cyan
}

Write-Host "RAG Platform setup_local.ps1"
Write-Host "Working directory: $Root"

# ---------------------------------------------------------------------------
# Guard: must be in project root (not parent zip folder)
# ---------------------------------------------------------------------------
if (-not (Test-Path (Join-Path $Root "docker-compose.dev.yml"))) {
  Fail "docker-compose.dev.yml not found. cd into the INNER rag-platform folder first.`nExample: cd C:\Users\YOU\Downloads\rag-platform-new\rag-platform"
}
if (-not (Test-Path (Join-Path $Root "requirements.txt"))) {
  Fail "requirements.txt not found. Wrong folder."
}
if (-not (Test-Path (Join-Path $Root "scripts\start_local.ps1"))) {
  Fail "scripts\start_local.ps1 not found. Wrong folder."
}

function Has-Cmd([string]$name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# ---------------------------------------------------------------------------
Step "1" "Check prerequisites"
# ---------------------------------------------------------------------------
$ok = $true
if (-not (Has-Cmd "python")) {
  Write-Host "MISSING: Python 3.11+ (tick Add to PATH when installing)" -ForegroundColor Red
  $ok = $false
} else {
  Write-Host "OK: $(python --version 2>&1)"
}

if (-not (Has-Cmd "npm")) {
  Write-Host "MISSING: Node.js 20+ / npm" -ForegroundColor Red
  $ok = $false
} else {
  Write-Host "OK: Node $(node --version 2>&1)"
}

if (-not (Has-Cmd "docker")) {
  Write-Host "MISSING: Docker Desktop" -ForegroundColor Red
  $ok = $false
} else {
  Write-Host "OK: Docker CLI found"
}

if (-not $ok) {
  Fail "Install missing tools, open a NEW PowerShell, cd to rag-platform, re-run this script."
}

# ---------------------------------------------------------------------------
Step "2" "Create .venv inside this folder"
# ---------------------------------------------------------------------------
$venvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Host "Creating .venv ..."
  python -m venv (Join-Path $Root ".venv")
} else {
  Write-Host ".venv already exists"
}
if (-not (Test-Path $venvPython)) {
  Fail "Could not create .venv\Scripts\python.exe"
}

# ---------------------------------------------------------------------------
Step "3" "Install Python packages (requirements.txt)"
# ---------------------------------------------------------------------------
& $venvPython -m pip install -U pip wheel setuptools
if ($LASTEXITCODE -ne 0) { Fail "pip upgrade failed" }

# Prefer wheels so litellm does not try to compile with Rust
& $venvPython -m pip install -r (Join-Path $Root "requirements.txt") --prefer-binary
if ($LASTEXITCODE -ne 0) {
  Write-Host "Retrying litellm as binary-only ..." -ForegroundColor Yellow
  & $venvPython -m pip install "litellm>=1.40.0,<1.92.0" --only-binary=:all:
  & $venvPython -m pip install -r (Join-Path $Root "requirements.txt") --prefer-binary
}
if ($LASTEXITCODE -ne 0) {
  Fail "pip install failed. See docs\SETUP_AND_RUN.md troubleshooting (litellm / Rust)."
}
Write-Host "OK: Python packages installed"

# ---------------------------------------------------------------------------
Step "4" "Install frontend packages (npm)"
# ---------------------------------------------------------------------------
Push-Location (Join-Path $Root "frontend")
try {
  npm install
  if ($LASTEXITCODE -ne 0) { Fail "npm install failed" }
} finally {
  Pop-Location
}
Write-Host "OK: frontend ready"

# ---------------------------------------------------------------------------
Step "5" "Create clean UTF-8 .env (no BOM)"
# ---------------------------------------------------------------------------
$envPath = Join-Path $Root ".env"
$example = Join-Path $Root ".env.example"

if (Test-Path $envPath) {
  # Detect mojibake / bad encoding in first lines
  $head = Get-Content $envPath -TotalCount 5 -ErrorAction SilentlyContinue | Out-String
  if ($head -match "Ã|Â|â€|ï»¿") {
    Write-Host "WARN: .env looks corrupted (encoding). Backing up and recreating." -ForegroundColor Yellow
    Copy-Item $envPath "$envPath.bad.bak" -Force
    Remove-Item $envPath -Force
  }
}

if (-not (Test-Path $envPath)) {
  if (-not (Test-Path $example)) { Fail ".env.example missing" }
  # Write UTF-8 without BOM so PowerShell + pydantic read cleanly
  $text = [System.IO.File]::ReadAllText($example)
  $utf8NoBom = New-Object System.Text.UTF8Encoding $false
  [System.IO.File]::WriteAllText($envPath, $text, $utf8NoBom)
  Write-Host "Created .env from .env.example (UTF-8 no BOM)"
  Write-Host "EDIT .env now: set POSTGRES_PASSWORD, REDIS_PASSWORD, JWT_SECRET_KEY, GROQ_API_KEY" -ForegroundColor Yellow
} else {
  Write-Host ".env already exists (kept)"
}

# Ensure SETUP_TOKEN and APP_DEBUG lines exist
$envLines = [System.Collections.Generic.List[string]]::new()
$envLines.AddRange([string[]](Get-Content $envPath))
$joined = ($envLines -join "`n")
if ($joined -notmatch '(?m)^\s*SETUP_TOKEN=') {
  $envLines.Add("SETUP_TOKEN=local-setup-token")
}
if ($joined -notmatch '(?m)^\s*APP_DEBUG=') {
  $envLines.Add("APP_DEBUG=true")
}
if ($joined -notmatch '(?m)^\s*CELERY_TASK_ALWAYS_EAGER=') {
  $envLines.Add("CELERY_TASK_ALWAYS_EAGER=1")
}
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($envPath, (($envLines -join "`r`n") + "`r`n"), $utf8NoBom)

# Load .env into this process (ASCII-safe parser)
Get-Content $envPath | ForEach-Object {
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

if (-not $env:POSTGRES_PASSWORD -or $env:POSTGRES_PASSWORD -match "CHANGE_ME") {
  Write-Host "WARN: POSTGRES_PASSWORD still CHANGE_ME - edit .env before Docker will work" -ForegroundColor Yellow
}
if (-not $env:REDIS_PASSWORD -or $env:REDIS_PASSWORD -match "CHANGE_ME") {
  Write-Host "WARN: REDIS_PASSWORD still CHANGE_ME - edit .env before Docker will work" -ForegroundColor Yellow
}

if (-not $env:POSTGRES_USER) { $env:POSTGRES_USER = "raguser" }
if (-not $env:POSTGRES_DB) { $env:POSTGRES_DB = "ragplatform" }

# Host ports from docker-compose.override.yml
$env:DATABASE_URL_SYNC = "postgresql://$($env:POSTGRES_USER):$($env:POSTGRES_PASSWORD)@127.0.0.1:15432/$($env:POSTGRES_DB)"
$env:DATABASE_URL = "postgresql+asyncpg://$($env:POSTGRES_USER):$($env:POSTGRES_PASSWORD)@127.0.0.1:15432/$($env:POSTGRES_DB)"

# ---------------------------------------------------------------------------
Step "6" "Start Docker (Postgres / Redis / Qdrant)"
# ---------------------------------------------------------------------------
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Starting Docker Desktop..."
  $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
  if (Test-Path $dockerExe) { Start-Process $dockerExe } else { Fail "Start Docker Desktop manually" }
  for ($i = 0; $i -lt 36; $i++) {
    Start-Sleep -Seconds 5
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { break }
    Write-Host "  waiting for Docker... $i"
  }
}
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail "Docker is not ready" }

docker compose -f docker-compose.dev.yml -f docker-compose.override.yml up -d
if ($LASTEXITCODE -ne 0) {
  Fail "docker compose failed. Set real POSTGRES_PASSWORD and REDIS_PASSWORD in .env (not CHANGE_ME)."
}

Write-Host "Waiting for Postgres on 15432..."
$pgReady = $false
for ($i = 0; $i -lt 40; $i++) {
  docker exec ragplatform_postgres pg_isready -U $env:POSTGRES_USER -d $env:POSTGRES_DB 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $pgReady = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $pgReady) { Fail "Postgres not ready. Run: docker compose -f docker-compose.dev.yml -f docker-compose.override.yml ps" }
Write-Host "OK: Postgres ready"

# ---------------------------------------------------------------------------
Step "7" "Run database migrations"
# ---------------------------------------------------------------------------
Push-Location (Join-Path $Root "data\postgres")
try {
  & $venvPython -m alembic upgrade head
  if ($LASTEXITCODE -ne 0) {
    Fail "alembic failed. Password in .env must match the password used when the Postgres volume was created."
  }
} finally {
  Pop-Location
}
Write-Host "OK: Migrations applied"

# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " SETUP COMPLETE"
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "NEXT:"
Write-Host "  1) Edit .env - GROQ_API_KEY and any CHANGE_ME passwords"
Write-Host "  2) .\scripts\start_local.ps1"
Write-Host "  3) .\scripts\bootstrap_demo.ps1"
Write-Host "  4) Admin http://localhost:3000  User http://localhost:3001"
Write-Host ""
Write-Host "Guide: docs\SETUP_AND_RUN.md"
Write-Host ""
