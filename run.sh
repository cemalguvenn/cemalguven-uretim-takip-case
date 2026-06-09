#!/usr/bin/env bash
#
# run.sh — one-click launcher for the Üretim Performans Takip case.
#
# Checks toolchain, installs backend (pip) and frontend (npm) dependencies in
# order, then starts the FastAPI backend (:8000) and the Vite frontend (:5173)
# together. Press Ctrl+C once to stop both cleanly.
#
# Fail-safe: any setup error aborts before servers start; both child processes
# are always torn down on exit.

set -Eeuo pipefail

# --- resolve project root (works no matter where it's launched from) ----------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

VENV_DIR="$ROOT_DIR/.venv"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# --- pretty logging -----------------------------------------------------------
log()  { printf '\033[1;34m[run]\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m[ok]\033[0m  %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[fail]\033[0m %s\n' "$*" >&2; exit 1; }

# --- cleanup: always kill both servers on exit --------------------------------
BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
  trap - INT TERM EXIT
  log "shutting down..."
  [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  [ -n "$BACKEND_PID" ]  && kill "$BACKEND_PID"  2>/dev/null || true
  wait 2>/dev/null || true
  ok "stopped."
}
trap cleanup INT TERM EXIT

# --- toolchain checks ---------------------------------------------------------
log "checking toolchain..."
command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.10+ and retry."
command -v node    >/dev/null 2>&1 || die "node not found. Install Node.js 18+ and retry."
command -v npm     >/dev/null 2>&1 || die "npm not found. Install Node.js (bundles npm) and retry."
ok "python3 $(python3 --version 2>&1 | awk '{print $2}'), node $(node --version), npm $(npm --version)"

[ -d "$BACKEND_DIR" ]  || die "backend directory missing: $BACKEND_DIR"
[ -d "$FRONTEND_DIR" ] || die "frontend directory missing: $FRONTEND_DIR"

# --- env file -----------------------------------------------------------------
if [ ! -f "$ROOT_DIR/.env" ]; then
  if [ -f "$ROOT_DIR/.env.example" ]; then
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    ok "created .env from .env.example"
  else
    warn ".env and .env.example both missing — backend will use built-in defaults"
  fi
fi

# --- backend: virtualenv + pip ------------------------------------------------
log "setting up backend (Python)..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR" || die "failed to create virtualenv at $VENV_DIR"
  ok "created virtualenv (.venv)"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate" || die "failed to activate virtualenv"

python3 -m pip install --upgrade pip >/dev/null 2>&1 || warn "pip self-upgrade skipped"
log "installing backend dependencies (pip)..."
python3 -m pip install -r "$BACKEND_DIR/requirements.txt" || die "pip install failed"
ok "backend dependencies ready"

# --- frontend: npm ------------------------------------------------------------
log "installing frontend dependencies (npm)..."
if [ -f "$FRONTEND_DIR/package-lock.json" ]; then
  ( cd "$FRONTEND_DIR" && npm ci ) || ( cd "$FRONTEND_DIR" && npm install ) \
    || die "npm install failed"
else
  ( cd "$FRONTEND_DIR" && npm install ) || die "npm install failed"
fi
ok "frontend dependencies ready"

# --- launch both servers ------------------------------------------------------
log "starting backend on http://localhost:$BACKEND_PORT ..."
( cd "$BACKEND_DIR" && exec uvicorn main:app --host 0.0.0.0 --port "$BACKEND_PORT" --reload ) &
BACKEND_PID=$!

log "starting frontend on http://localhost:$FRONTEND_PORT ..."
( cd "$FRONTEND_DIR" && exec npm run dev -- --port "$FRONTEND_PORT" ) &
FRONTEND_PID=$!

sleep 2
# bail out early if either process died on startup
kill -0 "$BACKEND_PID"  2>/dev/null || die "backend failed to start (see log above)"
kill -0 "$FRONTEND_PID" 2>/dev/null || die "frontend failed to start (see log above)"

ok "both servers are up:"
printf '      backend  -> http://localhost:%s  (docs: /docs)\n' "$BACKEND_PORT"
printf '      frontend -> http://localhost:%s\n' "$FRONTEND_PORT"
log "press Ctrl+C to stop both."

# Block until either server exits (portable to bash 3.2, which lacks `wait -n`).
# Ctrl+C fires the INT trap; if one server dies, the loop ends and cleanup runs.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done
warn "a server exited — tearing down the other."
