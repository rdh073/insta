#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Resolve env file: prefer .env.development, fall back to backend/.env
if [ -f "$ROOT/.env.development" ]; then
  ENV_FILE="$ROOT/.env.development"
elif [ -f "$ROOT/backend/.env" ]; then
  ENV_FILE="$ROOT/backend/.env"
else
  ENV_FILE=""
fi

# Backend
echo "Starting backend on :8000..."
cd "$ROOT/backend"
UVICORN_CMD=(-m uvicorn app.main:app --host 0.0.0.0 --port 8000)
if [ -n "$ENV_FILE" ]; then
  UVICORN_CMD+=(--env-file "$ENV_FILE")
  echo "  Env: $ENV_FILE"
fi
if command -v pyenv >/dev/null 2>&1; then
  pyenv exec python "${UVICORN_CMD[@]}" &
else
  python3 "${UVICORN_CMD[@]}" &
fi
BACKEND_PID=$!

# Frontend
echo "Starting frontend on :5173..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  InstaManager running:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo ""
echo "  Press Ctrl+C to stop both services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM
wait
