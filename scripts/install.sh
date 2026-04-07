#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# InstaManager — Linux/macOS Installation Script
#
# Usage:
#   chmod +x scripts/install.sh
#   ./scripts/install.sh
#
# What it does:
#   1. Checks prerequisites (Python 3.12+, Node 20+, npm, git)
#   2. Creates backend virtual environment & installs dependencies
#   3. Copies .env.example → .env (if not already present)
#   4. Installs frontend dependencies
#   5. Validates the setup
#
# Flags:
#   --skip-frontend   Skip frontend installation
#   --skip-backend    Skip backend installation
#   --force-env       Overwrite existing .env files
#   --help            Show this help
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()    { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }
step()    { echo -e "\n${BOLD}── $* ──${NC}"; }

# ── Parse flags ──────────────────────────────────────────────────────────────
SKIP_FRONTEND=false
SKIP_BACKEND=false
FORCE_ENV=false

for arg in "$@"; do
  case "$arg" in
    --skip-frontend) SKIP_FRONTEND=true ;;
    --skip-backend)  SKIP_BACKEND=true ;;
    --force-env)     FORCE_ENV=true ;;
    --help|-h)
      head -20 "$0" | tail -16
      exit 0
      ;;
  esac
done

# ── Resolve project root ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$ROOT/scripts/start.sh" ] || [ ! -d "$ROOT/backend" ] || [ ! -d "$ROOT/frontend" ]; then
  fail "Cannot find project root. Run this script from the project directory: ./scripts/install.sh"
fi

info "Project root: $ROOT"

# ── Step 1: Prerequisites ───────────────────────────────────────────────────
step "Checking prerequisites"

check_command() {
  if command -v "$1" &>/dev/null; then
    local ver
    ver=$("$1" --version 2>&1 | head -1)
    success "$1 found: $ver"
    return 0
  else
    return 1
  fi
}

# Python — prefer python3.12, then python3, then python
PYTHON=""
for candidate in python3.12 python3 python; do
  if command -v "$candidate" &>/dev/null; then
    py_ver=$("$candidate" --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
    py_major=$(echo "$py_ver" | cut -d. -f1)
    py_minor=$(echo "$py_ver" | cut -d. -f2)
    if [ "$py_major" -eq 3 ] && [ "$py_minor" -ge 12 ]; then
      PYTHON="$candidate"
      success "Python: $($PYTHON --version 2>&1)"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  fail "Python 3.12+ is required but not found.
  Install it:
    Ubuntu:  sudo apt install python3.12 python3.12-venv
    macOS:   brew install python@3.12
    pyenv:   pyenv install 3.12"
fi

# Node.js
if check_command node; then
  node_ver=$(node --version | grep -oP '\d+' | head -1)
  if [ "$node_ver" -lt 20 ]; then
    fail "Node.js 20+ required, found v$node_ver.
  Install: https://nodejs.org/ or use nvm: nvm install 20"
  fi
else
  fail "Node.js is required but not found.
  Install:
    Ubuntu:  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install nodejs
    macOS:   brew install node@20"
fi

# npm
check_command npm || fail "npm not found (should come with Node.js)"

# git
check_command git || warn "git not found — not required for install, but needed for development"

# ── Step 2: Backend ─────────────────────────────────────────────────────────
if [ "$SKIP_BACKEND" = false ]; then
  step "Setting up backend"

  cd "$ROOT/backend"

  # Virtual environment
  if [ -d ".venv" ]; then
    info "Virtual environment already exists at backend/.venv"
  else
    info "Creating virtual environment..."
    "$PYTHON" -m venv .venv
    success "Virtual environment created"
  fi

  # Activate
  # shellcheck disable=SC1091
  source .venv/bin/activate
  success "Virtual environment activated"

  # Upgrade pip
  info "Upgrading pip..."
  pip install --upgrade pip --quiet
  success "pip upgraded: $(pip --version | cut -d' ' -f1-2)"

  # Install dependencies
  info "Installing Python dependencies (this may take a minute)..."
  pip install -r requirements.txt --quiet
  success "Python dependencies installed"

  # .env file
  if [ -f .env ] && [ "$FORCE_ENV" = false ]; then
    info "backend/.env already exists (use --force-env to overwrite)"
  else
    if [ -f .env.example ]; then
      cp .env.example .env
      success "backend/.env created from .env.example"
    else
      warn "backend/.env.example not found — create backend/.env manually"
    fi
  fi

  # Create sessions directory
  mkdir -p sessions
  success "sessions/ directory ready"

  deactivate 2>/dev/null || true
else
  info "Skipping backend (--skip-backend)"
fi

# ── Step 3: Frontend ────────────────────────────────────────────────────────
if [ "$SKIP_FRONTEND" = false ]; then
  step "Setting up frontend"

  cd "$ROOT/frontend"

  # Install dependencies
  info "Installing Node dependencies..."
  npm install --silent 2>&1 | tail -3
  success "Node dependencies installed"

  # .env file
  if [ -f .env ] && [ "$FORCE_ENV" = false ]; then
    info "frontend/.env already exists (use --force-env to overwrite)"
  else
    if [ -f .env.example ]; then
      cp .env.example .env
      success "frontend/.env created from .env.example"
    else
      warn "frontend/.env.example not found — create frontend/.env manually"
    fi
  fi
else
  info "Skipping frontend (--skip-frontend)"
fi

# ── Step 4: Validation ──────────────────────────────────────────────────────
step "Validating installation"

errors=0

if [ "$SKIP_BACKEND" = false ]; then
  cd "$ROOT/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate

  if "$PYTHON" -c "import fastapi; import uvicorn; import instagrapi" 2>/dev/null; then
    success "Backend core imports OK (fastapi, uvicorn, instagrapi)"
  else
    warn "Some backend imports failed — check pip install output"
    errors=$((errors + 1))
  fi

  if "$PYTHON" -c "import langgraph" 2>/dev/null; then
    success "LangGraph import OK"
  else
    warn "LangGraph import failed — AI copilot features may not work"
  fi

  deactivate 2>/dev/null || true
fi

if [ "$SKIP_FRONTEND" = false ]; then
  cd "$ROOT/frontend"
  if [ -d "node_modules/.vite" ] || [ -d "node_modules/vite" ]; then
    success "Frontend node_modules OK"
  else
    warn "Frontend node_modules may be incomplete"
    errors=$((errors + 1))
  fi

  # Type check
  info "Running TypeScript check..."
  if npx tsc --noEmit 2>/dev/null; then
    success "TypeScript type check passed"
  else
    warn "TypeScript has errors (non-blocking — run 'npx tsc --noEmit' for details)"
  fi
fi

# ── Done ─────────────────────────────────────────────────────────────────────
step "Installation complete"

if [ "$errors" -gt 0 ]; then
  warn "$errors warning(s) — review the output above"
else
  success "All checks passed"
fi

printf "\n"
printf "${BOLD}Next steps:${NC}\n"
printf "\n"
printf "  1. Edit environment files:\n"
printf "     ${CYAN}backend/.env${NC}   — Set AI provider API keys (OPENAI_API_KEY, etc.)\n"
printf "     ${CYAN}frontend/.env${NC}  — Usually no changes needed for local dev\n"
printf "\n"
printf "  2. Start the application:\n"
printf "     ${CYAN}./scripts/start.sh${NC}     — Starts backend (:8000) + frontend (:5173)\n"
printf "\n"
printf "     Or run separately:\n"
printf "     ${CYAN}cd backend && source .venv/bin/activate${NC}\n"
printf "     ${CYAN}python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --env-file .env${NC}\n"
printf "     ${CYAN}cd frontend && npm run dev${NC}\n"
printf "\n"
printf "  3. Open in browser: ${BOLD}http://localhost:5173${NC}\n"
printf "\n"
