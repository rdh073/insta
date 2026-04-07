# ─────────────────────────────────────────────────────────────────────────────
# InstaManager — Docker Installation Script (Windows 11 PowerShell)
#
# Usage:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\scripts\docker-install.ps1
#
# What it does:
#   1. Checks Docker Desktop & Docker Compose
#   2. Checks WSL 2 status
#   3. Copies .env.example files (if not present)
#   4. Generates ENCRYPTION_KEY if empty
#   5. Builds and starts all containers
#   6. Waits for health checks
#   7. Prints access URLs
#
# Flags:
#   -BuildOnly      Build images without starting
#   -NoBuild        Start without rebuilding
#   -WithPgAdmin    Include pgAdmin for database inspection
#   -ForceEnv       Overwrite existing .env files
#   -Down           Stop and remove all containers (keep data)
#   -Reset          Stop, remove containers AND volumes (delete all data)
# ─────────────────────────────────────────────────────────────────────────────

param(
    [switch]$BuildOnly,
    [switch]$NoBuild,
    [switch]$WithPgAdmin,
    [switch]$ForceEnv,
    [switch]$Down,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

# ── Helpers ──────────────────────────────────────────────────────────────────
function Write-Info    { param($Msg) Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline; Write-Host $Msg }
function Write-Success { param($Msg) Write-Host "[OK]   " -ForegroundColor Green -NoNewline; Write-Host $Msg }
function Write-Warn    { param($Msg) Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline; Write-Host $Msg }
function Write-Fail    { param($Msg) Write-Host "[FAIL] " -ForegroundColor Red -NoNewline; Write-Host $Msg; exit 1 }
function Write-Step    { param($Msg) Write-Host "`n-- $Msg --" -ForegroundColor White }

# ── Resolve project root ────────────────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Root = (Resolve-Path (Join-Path $ScriptDir "..")).Path

if (-not (Test-Path (Join-Path $Root "docker-compose.yml"))) {
    Write-Fail "docker-compose.yml not found at $Root. Run from the project directory."
}

Set-Location $Root

# ── Handle -Down / -Reset ───────────────────────────────────────────────────
if ($Reset) {
    Write-Step "Resetting (stop + remove volumes)"
    docker compose down -v 2>$null
    Write-Success "All containers and volumes removed"
    exit 0
}

if ($Down) {
    Write-Step "Stopping containers"
    docker compose down 2>$null
    Write-Success "All containers stopped (data preserved in volumes)"
    exit 0
}

# ── Step 1: Check Docker ────────────────────────────────────────────────────
Write-Step "Checking Docker"

# Check WSL 2
try {
    $wslOutput = wsl --status 2>&1
    if ($wslOutput -match "Default Version: 2|WSL version") {
        Write-Success "WSL 2 is available"
    } else {
        Write-Warn "WSL 2 status uncertain — Docker Desktop may still work"
    }
} catch {
    Write-Warn "Could not check WSL status. If Docker Desktop uses WSL 2 backend, this is fine."
}

# Check Docker
try {
    $dockerVer = docker version --format '{{.Server.Version}}' 2>&1
    if ($LASTEXITCODE -ne 0) { throw "docker not responding" }
    Write-Success "Docker Engine: $dockerVer"
} catch {
    Write-Fail @"
Docker is not running or not installed.

  Install Docker Desktop:
    1. Download from https://docker.com/products/docker-desktop/
    2. Or run: winget install Docker.DockerDesktop
    3. Open Docker Desktop and wait for it to start
    4. Settings > General > enable 'Use the WSL 2 based engine'
"@
}

# Check Docker Compose
try {
    $composeVer = docker compose version 2>&1
    if ($LASTEXITCODE -ne 0) { throw "compose not found" }
    Write-Success "Docker Compose: $composeVer"
} catch {
    Write-Fail "Docker Compose not found. Update Docker Desktop to the latest version."
}

# ── Step 2: Environment files ───────────────────────────────────────────────
Write-Step "Setting up environment"

# Root .env
$rootEnv = Join-Path $Root ".env"
$rootEnvExample = Join-Path $Root ".env.example"
if ((Test-Path $rootEnv) -and -not $ForceEnv) {
    Write-Info ".env already exists (use -ForceEnv to overwrite)"
} elseif (Test-Path $rootEnvExample) {
    Copy-Item $rootEnvExample $rootEnv
    Write-Success ".env created from .env.example"
}

# Backend .env
$backendEnv = Join-Path $Root "backend\.env"
$backendEnvExample = Join-Path $Root "backend\.env.example"
if ((Test-Path $backendEnv) -and -not $ForceEnv) {
    Write-Info "backend\.env already exists"
} elseif (Test-Path $backendEnvExample) {
    Copy-Item $backendEnvExample $backendEnv
    Write-Success "backend\.env created from .env.example"
} else {
    Write-Warn "backend\.env.example not found - create backend\.env manually"
}

# Generate ENCRYPTION_KEY if empty
if (Test-Path $backendEnv) {
    $envContent = Get-Content $backendEnv -Raw
    if ($envContent -match "ENCRYPTION_KEY=\s*$" -or $envContent -match "ENCRYPTION_KEY=$") {
        $newKey = $null
        try {
            $newKey = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>$null
        } catch {}
        if (-not $newKey) {
            try {
                $newKey = python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>$null
            } catch {}
        }

        if ($newKey) {
            (Get-Content $backendEnv) -replace "^ENCRYPTION_KEY=.*", "ENCRYPTION_KEY=$newKey" | Set-Content $backendEnv
            Write-Success "ENCRYPTION_KEY auto-generated"
        } else {
            Write-Warn "Could not auto-generate ENCRYPTION_KEY (Python/cryptography not available locally)"
            Write-Info "Set it manually or it will be needed at backend startup"
        }
    } else {
        Write-Info "ENCRYPTION_KEY already set"
    }
}

# Check AI keys
$hasAiKey = $false
foreach ($keyName in @("OPENAI_API_KEY", "GEMINI_API_KEY", "DEEPSEEK_API_KEY")) {
    if (Test-Path $backendEnv) {
        $match = Select-String -Path $backendEnv -Pattern "^$keyName=.+" -Quiet
        if ($match) { $hasAiKey = $true; break }
    }
}

if (-not $hasAiKey) {
    Write-Warn "No AI provider API key found in backend\.env"
    Write-Info "Copilot and Smart Engagement features require at least one:"
    Write-Info "  OPENAI_API_KEY, GEMINI_API_KEY, or DEEPSEEK_API_KEY"
    Write-Info "Other features (accounts, proxy, posts) will work without it."
}

# ── Step 3: Build ───────────────────────────────────────────────────────────
Write-Step "Building Docker images"

$profileArgs = @()
if ($WithPgAdmin) {
    $profileArgs = @("--profile", "dev")
}

if (-not $NoBuild) {
    Write-Info "Building images (first run may take 2-5 minutes)..."
    docker compose @profileArgs build
    if ($LASTEXITCODE -ne 0) { Write-Fail "Docker build failed. Check the output above." }
    Write-Success "Images built"
} else {
    Write-Info "Skipping build (-NoBuild)"
}

if ($BuildOnly) {
    Write-Success "Build complete (-BuildOnly, not starting)"
    exit 0
}

# ── Step 4: Start ───────────────────────────────────────────────────────────
Write-Step "Starting services"

docker compose @profileArgs up -d
if ($LASTEXITCODE -ne 0) { Write-Fail "Failed to start containers." }
Write-Success "Containers started"

# ── Step 5: Health checks ───────────────────────────────────────────────────
Write-Step "Waiting for services"

# Read port config
$backendPort = "8000"
$frontendPort = "3000"
$pgadminPort = "5050"
if (Test-Path $rootEnv) {
    $portMatch = Select-String -Path $rootEnv -Pattern "^BACKEND_PORT=(\d+)" | Select-Object -First 1
    if ($portMatch) { $backendPort = $portMatch.Matches.Groups[1].Value }
    $portMatch = Select-String -Path $rootEnv -Pattern "^FRONTEND_PORT=(\d+)" | Select-Object -First 1
    if ($portMatch) { $frontendPort = $portMatch.Matches.Groups[1].Value }
    $portMatch = Select-String -Path $rootEnv -Pattern "^PGADMIN_PORT=(\d+)" | Select-Object -First 1
    if ($portMatch) { $pgadminPort = $portMatch.Matches.Groups[1].Value }
}

# Wait for PostgreSQL
Write-Info "Waiting for PostgreSQL..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        docker compose exec -T postgres pg_isready -U instauser -d instamanager 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 1
}
if ($ready) { Write-Success "PostgreSQL is ready" }
else { Write-Warn "PostgreSQL did not become ready in 30s - check: docker compose logs postgres" }

# Wait for backend
Write-Info "Waiting for backend..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:${backendPort}/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 2
}
if ($ready) { Write-Success "Backend is ready" }
else { Write-Warn "Backend did not respond in 60s - check: docker compose logs backend" }

# Check frontend
try {
    $response = Invoke-WebRequest -Uri "http://localhost:${frontendPort}" -UseBasicParsing -TimeoutSec 3 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) { Write-Success "Frontend is ready" }
    else { Write-Warn "Frontend returned status $($response.StatusCode)" }
} catch {
    Write-Warn "Frontend not responding yet - may still be starting"
}

# ── Step 6: Summary ─────────────────────────────────────────────────────────
Write-Step "InstaManager is running"

Write-Host ""
Write-Host "  Frontend:   " -ForegroundColor White -NoNewline
Write-Host "http://localhost:${frontendPort}" -ForegroundColor Cyan
Write-Host "  Backend:    " -ForegroundColor White -NoNewline
Write-Host "http://localhost:${backendPort}" -ForegroundColor Cyan
Write-Host "  API Docs:   " -ForegroundColor White -NoNewline
Write-Host "http://localhost:${backendPort}/docs" -ForegroundColor Cyan

if ($WithPgAdmin) {
    Write-Host "  pgAdmin:    " -ForegroundColor White -NoNewline
    Write-Host "http://localhost:${pgadminPort}" -ForegroundColor Cyan -NoNewline
    Write-Host "  (admin@local.dev / admin)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  Logs:       docker compose logs -f" -ForegroundColor DarkGray
Write-Host "  Stop:       docker compose down" -ForegroundColor DarkGray
Write-Host "  Reset:      docker compose down -v  " -ForegroundColor DarkGray -NoNewline
Write-Host "(deletes all data)" -ForegroundColor DarkGray
Write-Host ""

# Show container status
docker compose ps
