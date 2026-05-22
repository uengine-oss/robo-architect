#!/usr/bin/env bash
#
# dev.sh — start the full robo-architect dev stack in one terminal.
#
#   1. backend          FastAPI / uvicorn        http://localhost:8000
#   2. wireframe service open-pencil (Bun)        http://localhost:7610
#   3. frontend         Vue / Vite               http://localhost:5173
#
# Logs from all three are prefixed and interleaved. Ctrl+C stops everything.
#
# Usage:   ./dev.sh
# Override the open-pencil component library:
#          COMPONENT_LIBRARY_PATH=docs/components.fig ./dev.sh
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── Resolve tooling ──────────────────────────────────────────────────────────
BUN="$(command -v bun 2>/dev/null || true)"
[ -z "$BUN" ] && [ -x "$HOME/.bun/bin/bun" ] && BUN="$HOME/.bun/bin/bun"

fail() { echo "[dev] ✗ $1" >&2; exit 1; }
warn() { echo "[dev] ! $1" >&2; }

command -v uv  >/dev/null 2>&1 || fail "'uv' not found on PATH"
command -v npm >/dev/null 2>&1 || fail "'npm' not found on PATH (nvm: 'nvm use 22'?)"
[ -n "$BUN" ] || fail "'bun' not found (PATH or ~/.bun/bin/bun) — install: curl -fsSL https://bun.sh/install | bash"

[ -d "$ROOT/open-pencil" ]   || fail "open-pencil/ missing — run: git submodule update --init open-pencil"
[ -d "$ROOT/frontend" ]      || fail "frontend/ directory missing"
[ -d "$ROOT/open-pencil/node_modules" ] || warn "open-pencil/node_modules missing — run: (cd open-pencil && bun install)"
[ -d "$ROOT/frontend/node_modules" ]    || warn "frontend/node_modules missing — run: (cd frontend && npm install)"

COMPONENT_LIBRARY_PATH="${COMPONENT_LIBRARY_PATH:-docs/components.fig}"
[ -f "$ROOT/open-pencil/$COMPONENT_LIBRARY_PATH" ] || \
  warn "component library '$COMPONENT_LIBRARY_PATH' not found under open-pencil/ — wireframe service may start without components"

# ── Shutdown: kill the whole process group on exit ───────────────────────────
trap 'echo; echo "[dev] stopping all services..."; kill 0 2>/dev/null' EXIT

echo "[dev] starting stack — Ctrl+C to stop all"
echo "[dev]   backend   → http://localhost:8000"
echo "[dev]   wireframe → http://localhost:7610"
echo "[dev]   frontend  → http://localhost:5173"
echo

# ── 1. backend ───────────────────────────────────────────────────────────────
(
  cd "$ROOT"
  uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload 2>&1 | sed -l 's/^/[backend ] /'
) &

# ── 2. open-pencil wireframe service ─────────────────────────────────────────
(
  cd "$ROOT/open-pencil"
  COMPONENT_LIBRARY_PATH="$COMPONENT_LIBRARY_PATH" "$BUN" packages/cli/src/wireframe-service.ts 2>&1 | sed -l 's/^/[wirefrm ] /'
) &

# ── 3. frontend ──────────────────────────────────────────────────────────────
(
  cd "$ROOT/frontend"
  npm run dev 2>&1 | sed -l 's/^/[frontend] /'
) &

wait
