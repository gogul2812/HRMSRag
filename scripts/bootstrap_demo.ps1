# =============================================================================
# Bootstrap demo Super Admin + Demo Corp + admin + user
# Run AFTER .\scripts\start_local.ps1 (gateway must be healthy).
# Usage:  .\scripts\bootstrap_demo.ps1
# =============================================================================

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$setupToken = "local-setup-token"
if (Test-Path ".env") {
  Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*SETUP_TOKEN=(.*)$') {
      $setupToken = $Matches[1].Trim().Trim('"').Trim("'")
    }
  }
}

$base = "http://127.0.0.1:8000"
Write-Host "Gateway: $base"
Write-Host "SETUP_TOKEN: $setupToken"

try {
  $null = Invoke-WebRequest -Uri "$base/health" -UseBasicParsing -TimeoutSec 5
} catch {
  Write-Host "FAIL: Gateway not reachable. Run .\scripts\start_local.ps1 first." -ForegroundColor Red
  exit 1
}

function Invoke-Json($method, $url, $bodyObj, $headers) {
  $json = if ($null -ne $bodyObj) { ($bodyObj | ConvertTo-Json -Compress) } else { $null }
  $hdrs = @{ "Content-Type" = "application/json" }
  if ($headers) { foreach ($k in $headers.Keys) { $hdrs[$k] = $headers[$k] } }
  try {
    if ($json) {
      return Invoke-RestMethod -Method $method -Uri $url -Headers $hdrs -Body $json
    }
    return Invoke-RestMethod -Method $method -Uri $url -Headers $hdrs
  } catch {
    $resp = $_.ErrorDetails.Message
    Write-Host "  API note: $resp" -ForegroundColor DarkYellow
    return $null
  }
}

Write-Host ""
Write-Host "1) Bootstrap Super Admin..."
$sa = Invoke-Json "POST" "$base/api/v1/organizations/bootstrap-super-admin" @{
  name     = "Platform Super Admin"
  email    = "superadmin@example.com"
  password = "StrongPassword123!"
} @{ "setup-token" = $setupToken }
if ($sa) { Write-Host "  Super Admin ok: $($sa.email)" } else { Write-Host "  (may already exist — continuing)" }

Write-Host ""
Write-Host "2) Login as Super Admin..."
$tok = Invoke-Json "POST" "$base/api/v1/auth/login" @{
  email    = "superadmin@example.com"
  password = "StrongPassword123!"
} $null
if (-not $tok -or -not $tok.access_token) {
  Write-Host "FAIL: Could not login as superadmin@example.com" -ForegroundColor Red
  Write-Host "Check SETUP_TOKEN in .env matches auth-service, then re-run bootstrap." -ForegroundColor Yellow
  exit 1
}
$authHdr = @{ Authorization = "Bearer $($tok.access_token)" }
Write-Host "  Login ok"

Write-Host ""
Write-Host "3) Create Demo Corp + Org Admin..."
$org = Invoke-Json "POST" "$base/api/v1/organizations" @{
  name           = "Demo Corp"
  admin_name     = "Demo Admin"
  admin_email    = "admin@example.com"
  admin_password = "StrongPassword123!"
} $authHdr

$orgId = $null
if ($org -and $org.id) {
  $orgId = $org.id
  Write-Host "  Organization created: $orgId"
} else {
  Write-Host "  Org create failed or already exists — resolving from public list..."
  $public = Invoke-Json "GET" "$base/api/v1/organizations/public" $null $null
  if ($public) {
    $match = @($public | Where-Object { $_.name -eq "Demo Corp" }) | Select-Object -First 1
    if (-not $match) { $match = @($public) | Select-Object -First 1 }
    if ($match) { $orgId = $match.id; Write-Host "  Using org: $($match.name) $orgId" }
  }
}

if (-not $orgId) {
  Write-Host "FAIL: No organization id available." -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "4) Register end user..."
$user = Invoke-Json "POST" "$base/api/v1/auth/register" @{
  email           = "user@example.com"
  password        = "StrongPassword123!"
  name            = "Demo User"
  organization_id = $orgId
} $null
if ($user) { Write-Host "  User ok: $($user.email)" } else { Write-Host "  (user may already exist — ok)" }

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " DEMO ACCOUNTS READY"
Write-Host "========================================" -ForegroundColor Green
Write-Host "Admin portal  http://localhost:3000"
Write-Host "  Super Admin: check 'Platform Super Admin'"
Write-Host "    superadmin@example.com / StrongPassword123!"
Write-Host "  Org Admin: pick organization Demo Corp"
Write-Host "    admin@example.com / StrongPassword123!"
Write-Host "User portal   http://localhost:3001"
Write-Host "  pick Demo Corp"
Write-Host "    user@example.com / StrongPassword123!"
Write-Host ""
Write-Host "Then: Admin → Documents → upload samples\demo\ → wait Indexed → User → Chat"
Write-Host ""
