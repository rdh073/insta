#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# InstaManager — Docker Installation Script (Linux/macOS)
#
# Usage:
#   chmod +x scripts/docker-install.sh
#   ./scripts/docker-install.sh
#
# What it does:
#   1. Checks Docker & Docker Compose are installed
#   2. Copies .env.example files (if not present)
#   3. Generates ENCRYPTION_KEY if empty
#   4. Builds and starts all containers
#   5. Waits for health checks
#   6. Prints access URLs
#
# Flags:
#   --build-only      Build images without starting
#   --no-build        Start without rebuilding (use existing images)
#   --with-pgadmin    Include pgAdmin for database inspection
#   --force-env       Overwrite existing .env files
#   --down            Stop and remove all containers (keep data)
#   --reset           Stop, remove containers AND volumes (delete all data)
#   --help            Show this help
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Colors ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

info()    { printf "${CYAN}[INFO]${NC} %s\n" "$*"; }
success() { printf "${GREEN}[OK]${NC}   %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC} %s\n" "$*"; }
fail()    { printf "${RED}[FAIL]${NC} %s\n" "$*"; exit 1; }
step()    { printf "\n${BOLD}── %s ──${NC}\n" "$*"; }

# ── Parse flags ──────────────────────────────────────────────────────────────
BUILD_ONLY=false
NO_BUILD=false
WITH_PGADMIN=false
FORCE_ENV=false
DO_DOWN=false
DO_RESET=false

for arg in "$@"; do
  case "$arg" in
    --build-only)    BUILD_ONLY=true ;;
    --no-build)      NO_BUILD=true ;;
    --with-pgadmin)  WITH_PGADMIN=true ;;
    --force-env)     FORCE_ENV=true ;;
    --down)          DO_DOWN=true ;;
    --reset)         DO_RESET=true ;;
    --help|-h)
      sed -n '2,/^# ──────/p' "$0" | head -18
      exit 0
      ;;
  esac
done

# ── Resolve project root ────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ ! -f "$ROOT/docker-compose.yml" ]; then
  fail "docker-compose.yml not found at $ROOT. Run from the project root."
fi

cd "$ROOT"

# ── Handle --down / --reset ─────────────────────────────────────────────────
if [ "$DO_RESET" = true ]; then
  step "Resetting (stop + remove volumes)"
  docker compose down -v 2>/dev/null || docker-compose down -v
  success "All containers and volumes removed"
  exit 0
fi

if [ "$DO_DOWN" = true ]; then
  step "Stopping containers"
  docker compose down 2>/dev/null || docker-compose down
  success "All containers stopped (data preserved in volumes)"
  exit 0
fi

# ── Step 1: Check Docker ────────────────────────────────────────────────────
step "Checking Docker"

# Detect compose command
COMPOSE=""
if docker compose version &>/dev/null; then
  COMPOSE="docker compose"
  success "docker compose: $(docker compose version --short 2>/dev/null || docker compose version)"
elif docker-compose version &>/dev/null; then
  COMPOSE="docker-compose"
  success "docker-compose: $(docker-compose version --short 2>/dev/null || docker-compose version)"
else
  fail "Docker Compose not found.
  Install Docker:
    Ubuntu:  https://docs.docker.com/engine/install/ubuntu/
    macOS:   brew install docker docker-compose"
fi

if ! docker info &>/dev/null; then
  fail "Docker daemon is not running.
  Start it:
    Ubuntu:  sudo systemctl start docker
    macOS:   Open Docker Desktop"
fi

docker_ver=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "unknown")
success "Docker Engine: $docker_ver"

# ── Step 2: Environment files ───────────────────────────────────────────────
step "Setting up environment"

# Root .env
if [ -f .env ] && [ "$FORCE_ENV" = false ]; then
  info ".env already exists (use --force-env to overwrite)"
else
  if [ -f .env.example ]; then
    cp .env.example .env
    success ".env created from .env.example"
  fi
fi

# Backend .env
if [ -f backend/.env ] && [ "$FORCE_ENV" = false ]; then
  info "backend/.env already exists"
else
  if [ -f backend/.env.example ]; then
    cp backend/.env.example backend/.env
    success "backend/.env created from .env.example"
  else
    warn "backend/.env.example not found — create backend/.env manually"
  fi
fi

# Generate ENCRYPTION_KEY if empty
if [ -f backend/.env ]; then
  current_key=$(grep -oP '^ENCRYPTION_KEY=\K.+' backend/.env 2>/dev/null || true)
  if [ -z "$current_key" ]; then
    # Try generating with Python (available on most systems)
    new_key=""
    if command -v python3 &>/dev/null; then
      new_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || true)
    fi
    if [ -z "$new_key" ] && command -v python &>/dev/null; then
      new_key=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || true)
    fi

    if [ -n "$new_key" ]; then
      sed -i "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$new_key|" backend/.env
      success "ENCRYPTION_KEY auto-generated"
    else
      warn "Could not auto-generate ENCRYPTION_KEY (cryptography not installed locally)"
      info "It will be generated inside the container on first run, or set it manually"
    fi
  else
    info "ENCRYPTION_KEY already set"
  fi
fi

# Check if at least one AI key is configured
has_ai_key=false
for key_name in OPENAI_API_KEY GEMINI_API_KEY DEEPSEEK_API_KEY; do
  val=$(grep -oP "^${key_name}=\K.+" backend/.env 2>/dev/null || true)
  if [ -n "$val" ]; then
    has_ai_key=true
    break
  fi
done

if [ "$has_ai_key" = false ]; then
  warn "No AI provider API key found in backend/.env"
  info "Copilot and Smart Engagement features require at least one:"
  info "  OPENAI_API_KEY, GEMINI_API_KEY, or DEEPSEEK_API_KEY"
  info "Other features (accounts, proxy, posts) will work without it."
fi

# ── Step 3: Build ───────────────────────────────────────────────────────────
step "Building Docker images"

PROFILE_ARGS=""
if [ "$WITH_PGADMIN" = true ]; then
  PROFILE_ARGS="--profile dev"
fi

if [ "$NO_BUILD" = false ]; then
  info "Building images (first run may take 2-5 minutes)..."
  $COMPOSE $PROFILE_ARGS build
  success "Images built"
else
  info "Skipping build (--no-build)"
fi

if [ "$BUILD_ONLY" = true ]; then
  success "Build complete (--build-only, not starting)"
  exit 0
fi

# ── Step 4: Start ───────────────────────────────────────────────────────────
step "Starting services"

$COMPOSE $PROFILE_ARGS up -d
success "Containers started"

# ── Step 5: Health checks ───────────────────────────────────────────────────
step "Waiting for services"

# Wait for PostgreSQL
info "Waiting for PostgreSQL..."
retries=0
max_retries=30
while [ $retries -lt $max_retries ]; do
  if $COMPOSE exec -T postgres pg_isready -U instauser -d instamanager &>/dev/null; then
    success "PostgreSQL is ready"
    break
  fi
  retries=$((retries + 1))
  sleep 1
done
if [ $retries -eq $max_retries ]; then
  warn "PostgreSQL did not become ready in ${max_retries}s — check logs: $COMPOSE logs postgres"
fi

# Wait for backend
info "Waiting for backend..."
retries=0
backend_port=$(grep -oP '^BACKEND_PORT=\K\d+' .env 2>/dev/null || echo "8000")
while [ $retries -lt $max_retries ]; do
  if curl -sf "http://localhost:${backend_port}/health" &>/dev/null; then
    success "Backend is ready"
    break
  fi
  retries=$((retries + 1))
  sleep 2
done
if [ $retries -eq $max_retries ]; then
  warn "Backend did not respond in ${max_retries}s — check logs: $COMPOSE logs backend"
fi

# Check frontend
frontend_port=$(grep -oP '^FRONTEND_PORT=\K\d+' .env 2>/dev/null || echo "3000")
if curl -sf "http://localhost:${frontend_port}" &>/dev/null; then
  success "Frontend is ready"
else
  warn "Frontend not responding yet — may still be starting"
fi

# ── Step 6: Summary ─────────────────────────────────────────────────────────
step "InstaManager is running"

printf "\n"
printf "  ${BOLD}Frontend:${NC}   ${CYAN}http://localhost:${frontend_port}${NC}\n"
printf "  ${BOLD}Backend:${NC}    ${CYAN}http://localhost:${backend_port}${NC}\n"
printf "  ${BOLD}API Docs:${NC}   ${CYAN}http://localhost:${backend_port}/docs${NC}\n"

if [ "$WITH_PGADMIN" = true ]; then
  pgadmin_port=$(grep -oP '^PGADMIN_PORT=\K\d+' .env 2>/dev/null || echo "5050")
  printf "  ${BOLD}pgAdmin:${NC}    ${CYAN}http://localhost:${pgadmin_port}${NC}  ${DIM}(admin@local.dev / admin)${NC}\n"
fi

printf "\n"
printf "  ${DIM}Logs:${NC}       $COMPOSE logs -f\n"
printf "  ${DIM}Stop:${NC}       $COMPOSE down\n"
printf "  ${DIM}Reset:${NC}      $COMPOSE down -v  ${DIM}(deletes all data)${NC}\n"
printf "\n"

# Show container status
$COMPOSE ps
