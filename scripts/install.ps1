# ─────────────────────────────────────────────────────────────────────────────
# InstaManager — Windows 11 Installation Script (PowerShell)
#
# Usage:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\scripts\install.ps1
#
# What it does:
#   1. Checks prerequisites (Python 3.12+, Node 20+, npm, git)
#   2. Creates backend virtual environment & installs dependencies
#   3. Copies .env.example → .env (if not already present)
#   4. Installs frontend dependencies
#   5. Validates the setup
#
# Flags:
#   -SkipFrontend   Skip frontend installation
#   -SkipBackend    Skip backend installation
#   -ForceEnv       Overwrite existing .env files
# ─────────────────────────────────────────────────────────────────────────────

param(
    [switch]$SkipFrontend,
    [switch]$SkipBackend,
    [switch]$ForceEnv
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

if (-not (Test-Path (Join-Path $Root "start.sh")) -or -not (Test-Path (Join-Path $Root "backend")) -or -not (Test-Path (Join-Path $Root "frontend"))) {
    Write-Fail "Cannot find project root. Run from project directory: .\scripts\install.ps1"
}

Write-Info "Project root: $Root"

# ── Step 1: Prerequisites ───────────────────────────────────────────────────
Write-Step "Checking prerequisites"

# Python
$Python = $null
foreach ($candidate in @("python3.12", "python3", "python", "py")) {
    try {
        $pyOutput = & $candidate --version 2>&1
        if ($pyOutput -match "(\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 12) {
                $Python = $candidate
                Write-Success "Python: $pyOutput"
                break
            }
        }
    } catch {
        continue
    }
}

if (-not $Python) {
    # Try py launcher (common on Windows)
    try {
        $pyOutput = & py -3.12 --version 2>&1
        if ($pyOutput -match "3\.1[2-9]") {
            $Python = "py -3.12"
            Write-Success "Python: $pyOutput (via py launcher)"
        }
    } catch {}
}

if (-not $Python) {
    Write-Fail @"
Python 3.12+ is required but not found.
  Download from: https://www.python.org/downloads/
  Make sure to check 'Add Python to PATH' during installation.
  Or use: winget install Python.Python.3.12
"@
}

# Node.js
try {
    $nodeVer = (node --version 2>&1)
    if ($nodeVer -match "v(\d+)") {
        $nodeMajor = [int]$Matches[1]
        if ($nodeMajor -lt 20) {
            Write-Fail "Node.js 20+ required, found $nodeVer. Download from: https://nodejs.org/"
        }
        Write-Success "Node.js: $nodeVer"
    }
} catch {
    Write-Fail @"
Node.js is required but not found.
  Download from: https://nodejs.org/ (LTS 20.x)
  Or use: winget install OpenJS.NodeJS.LTS
"@
}

# npm
try {
    $npmVer = (npm --version 2>&1)
    Write-Success "npm: v$npmVer"
} catch {
    Write-Fail "npm not found (should come with Node.js)"
}

# git (optional)
try {
    $gitVer = (git --version 2>&1)
    Write-Success "git: $gitVer"
} catch {
    Write-Warn "git not found - not required for install, but needed for development"
}

# ── Step 2: Backend ─────────────────────────────────────────────────────────
if (-not $SkipBackend) {
    Write-Step "Setting up backend"

    $backendDir = Join-Path $Root "backend"
    Push-Location $backendDir

    # Virtual environment
    $venvDir = Join-Path $backendDir ".venv"
    if (Test-Path $venvDir) {
        Write-Info "Virtual environment already exists at backend\.venv"
    } else {
        Write-Info "Creating virtual environment..."
        if ($Python -like "py *") {
            & py -3.12 -m venv .venv
        } else {
            & $Python -m venv .venv
        }
        Write-Success "Virtual environment created"
    }

    # Activate
    $activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
    if (-not (Test-Path $activateScript)) {
        Write-Fail "Cannot find venv activation script at $activateScript"
    }
    & $activateScript
    Write-Success "Virtual environment activated"

    # Upgrade pip
    Write-Info "Upgrading pip..."
    pip install --upgrade pip --quiet 2>&1 | Out-Null
    Write-Success "pip upgraded"

    # Install dependencies
    Write-Info "Installing Python dependencies (this may take a minute)..."
    pip install -r requirements.txt --quiet 2>&1 | Out-Null
    Write-Success "Python dependencies installed"

    # .env file
    $envFile = Join-Path $backendDir ".env"
    $envExample = Join-Path $backendDir ".env.example"
    if ((Test-Path $envFile) -and -not $ForceEnv) {
        Write-Info "backend\.env already exists (use -ForceEnv to overwrite)"
    } else {
        if (Test-Path $envExample) {
            Copy-Item $envExample $envFile
            Write-Success "backend\.env created from .env.example"
        } else {
            Write-Warn "backend\.env.example not found - create backend\.env manually"
        }
    }

    # Create sessions directory
    $sessionsDir = Join-Path $backendDir "sessions"
    if (-not (Test-Path $sessionsDir)) {
        New-Item -ItemType Directory -Path $sessionsDir | Out-Null
    }
    Write-Success "sessions\ directory ready"

    # Deactivate
    try { deactivate } catch {}

    Pop-Location
} else {
    Write-Info "Skipping backend (-SkipBackend)"
}

# ── Step 3: Frontend ────────────────────────────────────────────────────────
if (-not $SkipFrontend) {
    Write-Step "Setting up frontend"

    $frontendDir = Join-Path $Root "frontend"
    Push-Location $frontendDir

    # Install dependencies
    Write-Info "Installing Node dependencies..."
    npm install --silent 2>&1 | Select-Object -Last 3
    Write-Success "Node dependencies installed"

    # .env file
    $envFile = Join-Path $frontendDir ".env"
    $envExample = Join-Path $frontendDir ".env.example"
    if ((Test-Path $envFile) -and -not $ForceEnv) {
        Write-Info "frontend\.env already exists (use -ForceEnv to overwrite)"
    } else {
        if (Test-Path $envExample) {
            Copy-Item $envExample $envFile
            Write-Success "frontend\.env created from .env.example"
        } else {
            Write-Warn "frontend\.env.example not found - create frontend\.env manually"
        }
    }

    Pop-Location
} else {
    Write-Info "Skipping frontend (-SkipFrontend)"
}

# ── Step 4: Validation ──────────────────────────────────────────────────────
Write-Step "Validating installation"

$errors = 0

if (-not $SkipBackend) {
    Push-Location (Join-Path $Root "backend")
    $activateScript = Join-Path $Root "backend\.venv\Scripts\Activate.ps1"
    & $activateScript

    try {
        $importCheck = python -c "import fastapi; import uvicorn; import instagrapi" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Backend core imports OK (fastapi, uvicorn, instagrapi)"
        } else {
            Write-Warn "Some backend imports failed - check pip install output"
            $errors++
        }
    } catch {
        Write-Warn "Backend import check failed"
        $errors++
    }

    try {
        python -c "import langgraph" 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "LangGraph import OK"
        } else {
            Write-Warn "LangGraph import failed - AI copilot features may not work"
        }
    } catch {
        Write-Warn "LangGraph import check failed"
    }

    try { deactivate } catch {}
    Pop-Location
}

if (-not $SkipFrontend) {
    $nodeModules = Join-Path $Root "frontend\node_modules"
    if (Test-Path (Join-Path $nodeModules "vite")) {
        Write-Success "Frontend node_modules OK"
    } else {
        Write-Warn "Frontend node_modules may be incomplete"
        $errors++
    }

    Push-Location (Join-Path $Root "frontend")
    Write-Info "Running TypeScript check..."
    try {
        npx tsc --noEmit 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Success "TypeScript type check passed"
        } else {
            Write-Warn "TypeScript has errors (non-blocking - run 'npx tsc --noEmit' for details)"
        }
    } catch {
        Write-Warn "TypeScript check skipped"
    }
    Pop-Location
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Step "Installation complete"

if ($errors -gt 0) {
    Write-Warn "$errors warning(s) - review the output above"
} else {
    Write-Success "All checks passed"
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "  1. Edit environment files:"
Write-Host "     backend\.env   " -ForegroundColor Cyan -NoNewline; Write-Host "- Set AI provider API keys (OPENAI_API_KEY, etc.)"
Write-Host "     frontend\.env  " -ForegroundColor Cyan -NoNewline; Write-Host "- Usually no changes needed for local dev"
Write-Host ""
Write-Host "  2. Start the application:"
Write-Host ""
Write-Host "     Terminal 1 (Backend):" -ForegroundColor White
Write-Host "     cd backend" -ForegroundColor Cyan
Write-Host "     .venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "     python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env" -ForegroundColor Cyan
Write-Host ""
Write-Host "     Terminal 2 (Frontend):" -ForegroundColor White
Write-Host "     cd frontend" -ForegroundColor Cyan
Write-Host "     npm run dev" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. Open in browser: " -NoNewline; Write-Host "http://localhost:5173" -ForegroundColor White
Write-Host ""
