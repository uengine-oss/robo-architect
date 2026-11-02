#!/usr/bin/env bash
#
# dev.sh — start the full robo-architect dev stack in one terminal.
#
#   1. backend          FastAPI / uvicorn        http://localhost:8000
#   2. wireframe service open-pencil (Bun)        http://localhost:7610
#   3. frontend         Vue / Vite               http://localhost:5173
#   4. analyzer frontend Module Federation remote http://localhost:5001
#
# Logs from all four are prefixed and interleaved. Ctrl+C stops everything.
#
# Usage:   ./dev.sh
# Override the open-pencil component library:
#          COMPONENT_LIBRARY_PATH=docs/components.fig ./dev.sh
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Load the repository-level development environment for every child process.
# Python loads .env on its own, but Vite's config reads process.env directly;
# without this, ROBO_GATEWAY_URL and the Lite graph connection diverge.
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

# ── Resolve tooling ──────────────────────────────────────────────────────────
BUN="$(command -v bun 2>/dev/null || true)"
[ -z "$BUN" ] && [ -x "$HOME/.bun/bin/bun" ] && BUN="$HOME/.bun/bin/bun"

fail() { echo "[dev] ✗ $1" >&2; exit 1; }
warn() { echo "[dev] ! $1" >&2; }

# A Lite Desktop stack keeps its graph password in the generated container
# environment and allocates host ports dynamically. Local source development
# can reuse that running stack without copying its secret into .env.
if [ "${ROBO_LITE_DOCKER_DISCOVERY:-false}" = "true" ]; then
  graph_bolt_container="${ROBO_LITE_GRAPH_BOLT_CONTAINER:-robo-architect-desktop-graph-bolt-1}"
  analyzer_container="${ROBO_LITE_ANALYZER_CONTAINER:-robo-architect-desktop-analyzer-1}"
  gateway_container="${ROBO_LITE_GATEWAY_CONTAINER:-robo-architect-desktop-gateway-1}"

  if command -v docker >/dev/null 2>&1; then
    graph_bolt_port="$(docker port "$graph_bolt_container" 7687/tcp 2>/dev/null | head -n 1 | awk -F: '{print $NF}')"
    gateway_port="$(docker port "$gateway_container" 9000/tcp 2>/dev/null | head -n 1 | awk -F: '{print $NF}')"
    graph_password="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$analyzer_container" 2>/dev/null | sed -n 's/^NEO4J_PASSWORD=//p' | head -n 1)"

    if [ -n "$graph_bolt_port" ] && [ -n "$graph_password" ]; then
      export NEO4J_URI="bolt://127.0.0.1:$graph_bolt_port"
      export NEO4J_USER="${NEO4J_USER:-robo}"
      export NEO4J_PASSWORD="$graph_password"
      export NEO4J_DATABASE="${NEO4J_DATABASE:-robo}"
      export ANALYZER_NEO4J_DATABASE="${ANALYZER_NEO4J_DATABASE:-analyzer_run}"
      echo "[dev] using Lite graph runtime at $NEO4J_URI"
    else
      warn "Lite graph runtime discovery failed; check Docker containers or set NEO4J_* in .env"
    fi

    if [ -n "$gateway_port" ]; then
      export ROBO_GATEWAY_URL="http://127.0.0.1:$gateway_port"
      echo "[dev] using Lite gateway at $ROBO_GATEWAY_URL"
    fi
  else
    warn "ROBO_LITE_DOCKER_DISCOVERY=true but docker is not on PATH"
  fi
fi

command -v uv  >/dev/null 2>&1 || fail "'uv' not found on PATH"
command -v npm >/dev/null 2>&1 || fail "'npm' not found on PATH (nvm: 'nvm use 22'?)"
[ -n "$BUN" ] || fail "'bun' not found (PATH or ~/.bun/bin/bun) — install: curl -fsSL https://bun.sh/install | bash"

[ -d "$ROOT/open-pencil" ]   || fail "open-pencil/ missing — run: git submodule update --init open-pencil"
[ -d "$ROOT/frontend" ]      || fail "frontend/ directory missing"
[ -f "$ROOT/robo-analyzer/robo-data-frontend/package.json" ] || \
  fail "analyzer frontend missing — run: git submodule update --init robo-analyzer/robo-data-frontend"
[ -d "$ROOT/open-pencil/node_modules" ] || warn "open-pencil/node_modules missing — run: (cd open-pencil && bun install)"
[ -d "$ROOT/frontend/node_modules" ]    || warn "frontend/node_modules missing — run: (cd frontend && npm install)"
[ -d "$ROOT/robo-analyzer/robo-data-frontend/node_modules" ] || \
  warn "analyzer frontend/node_modules missing — run: (cd robo-analyzer/robo-data-frontend && npm install)"

COMPONENT_LIBRARY_PATH="${COMPONENT_LIBRARY_PATH:-docs/components.fig}"
[ -f "$ROOT/open-pencil/$COMPONENT_LIBRARY_PATH" ] || \
  warn "component library '$COMPONENT_LIBRARY_PATH' not found under open-pencil/ — wireframe service may start without components"

# ── Shutdown: SIGTERM then SIGKILL the well-known ports' listeners ───────────
# `kill 0` alone leaks uvicorn workers when async threads (httpx, asyncio) keep
# the interpreter alive past SIGTERM. We follow up with SIGKILL on whoever is
# still listening on our four ports, so a re-run of dev.sh doesn't fail with
# "Address already in use".
trap '
  echo; echo "[dev] stopping all services...";
  kill 0 2>/dev/null;
  sleep 1;
  for p in 8000 7610 5173 5001; do
    pids=$(lsof -ti :$p -sTCP:LISTEN 2>/dev/null);
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null;
  done
' EXIT

echo "[dev] starting stack — Ctrl+C to stop all"
echo "[dev]   backend   → http://localhost:8000"
echo "[dev]   wireframe → http://localhost:7610"
echo "[dev]   frontend  → http://localhost:5173"
echo "[dev]   analyzer  → http://localhost:5001"
echo

# ── 1. backend ───────────────────────────────────────────────────────────────
(
  cd "$ROOT"
  # --timeout-graceful-shutdown 3: workers stuck in Neo4j sessions / plugin
  # poll loops get SIGKILL after 3 s, preventing zombie workers from piling
  # up on port 8000 and stalling subsequent requests.
  uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --timeout-graceful-shutdown 3 2>&1 | sed -l 's/^/[backend ] /'
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

# ── 4. analyzer frontend (Module Federation remote) ──────────────────────────
# Federation exposes remoteEntry.js from the production build only. The Vite
# dev server on port 3000 cannot be mounted by the Architect host.
(
  cd "$ROOT/robo-analyzer/robo-data-frontend"
  (npm run build && npm run preview -- --host 127.0.0.1 --port 5001 --strictPort) 2>&1 | sed -l 's/^/[analyzFE] /'
) &

wait
