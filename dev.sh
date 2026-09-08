#!/usr/bin/env bash
#
# dev.sh — start everything the app needs, in one terminal (macOS / Linux).
#
#   graph store   Neo4j (Docker)           bolt 7687 · browser 7474
#   analyzer      remote · analyzer · catalog · fabric · parser · gateway
#                                          5001  5502  5503  8404  8081  9000
#   1. backend    FastAPI / uvicorn        http://localhost:8000
#   2. wireframe  open-pencil (Bun)        http://localhost:7610
#   3. frontend   Vue / Vite               http://localhost:5173
#
# The three numbered services run as children here — their logs are prefixed
# and interleaved, and Ctrl+C stops them. Neo4j and the analyzer stack are
# background services with their own lifecycle (Docker, scripts/analyzer-stack.sh);
# this script starts them if they are down and reports what it found.
#
# Why they belong in one script: the Analysis tab is a Module Federation remote
# on 5001 and every one of its calls goes through the gateway on 9000, so a
# frontend without that stack renders the tab and fails every request in it.
# And all of them read the same Neo4j server — the analyzer writes what the
# mapper later reads, so a missing database is not a degraded mode, it is no
# mode at all.
#
# On Windows use robo-workspace (`robo.cmd up architect-web`) instead: it does
# the same wiring, and the Electron packaging only exists there.
#
# ═══════════════════════════════════════════════════════════════════════════
# WHAT YOU NEED INSTALLED — once per machine
# ═══════════════════════════════════════════════════════════════════════════
#
#   Docker Desktop   Neo4j runs in a container; nothing else needs it
#   Python 3.11+     backend, analyzer, catalog, data-fabric
#   uv               backend dependency manager  (curl -LsSf https://astral.sh/uv/install.sh | sh)
#   Node.js 20+/npm  frontend and the analyzer remote
#   bun              open-pencil wireframe service (curl -fsSL https://bun.sh/install | bash)
#   Java 17          ANTLR parser and API gateway
#   Maven            builds those two jars
#
#   macOS:  brew install --cask docker && brew install python@3.11 node openjdk@17 maven
#
# ═══════════════════════════════════════════════════════════════════════════
# WHAT YOU NEED CHECKED OUT — once per clone
# ═══════════════════════════════════════════════════════════════════════════
#
#   1. this repository, with its submodules
#
#        git clone https://github.com/uengine-oss/robo-architect.git
#        cd robo-architect
#        git submodule update --init --recursive
#
#      open-pencil (the wireframe service) and robo-analyzer/* (analyzer,
#      catalog, data-fabric, frontend) are submodules. A submodule is a real
#      checkout at a commit this repository records — so you run the analyzer
#      version Architect was verified against, not the tip of its own main.
#      To take newer analyzer work you bump the submodule pointer here and
#      commit it; `git pull` in this repo alone will not do it.
#
#   2. the parser and the gateway — separate repositories, cloned as siblings
#
#        cd ..
#        git clone https://github.com/uengine-oss/antlr-code-parser.git
#        git clone https://github.com/uengine-oss/robo-api-gateway.git
#
#      `scripts/analyzer-stack.sh setup` clones both for you if they are
#      missing. Elsewhere on disk: set ROBO_PARSER_DIR / ROBO_GATEWAY_DIR.
#
#   3. dependencies and the Java build
#
#        cp .env.example .env          # fill NEO4J_*, LLM_PROVIDER/MODEL, API keys
#        uv sync
#        (cd frontend && npm install)
#        (cd open-pencil && bun install)
#        ./scripts/analyzer-stack.sh setup     # venvs, npm, two mvn builds
#
#      The last one builds Java and installs four dependency trees. Expect it
#      to run for several minutes the first time.
#
#   4. Neo4j schema, once the container is up
#
#        docker compose up -d
#        cypher-shell -f docs/cypher/schema/01_constraints.cypher
#        cypher-shell -f docs/cypher/schema/02_indexes.cypher
#
# ═══════════════════════════════════════════════════════════════════════════
# ONE THING TO GET RIGHT BEFORE RUNNING AN ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════
#
# The analyzer wipes its target database at the start of every run — literally
# `MATCH (n) DETACH DELETE n`. If it points at the database holding your
# design, one analysis erases the design.
#
# So the analyzer gets its own database, named by ANALYZER_NEO4J_DATABASE.
# Neo4j Community serves only `neo4j`, so separating them means the enterprise
# image (free for development) — scripts/analyzer-stack.sh documents the
# three-line change. Until they are separated, the stack refuses to start and
# tells you so; `WITH_ANALYZER=0 ./dev.sh` runs the app without it.
#
# ═══════════════════════════════════════════════════════════════════════════
#
# Usage:   ./dev.sh
#
#   WITH_DB=0        skip Neo4j (running elsewhere, or Aura)
#   WITH_ANALYZER=0  skip the analyzer stack (backend/frontend work only)
#   STOP_ALL=1       on exit, also stop the analyzer stack (default: leave up)
#
# Override the open-pencil component library:
#          COMPONENT_LIBRARY_PATH=docs/components.fig ./dev.sh
#
# Where things are afterwards:
#   analyzer logs    .robo-logs/<service>.log  ·  ./scripts/analyzer-stack.sh logs <service>
#   analyzer status  ./scripts/analyzer-stack.sh status
#   Neo4j browser    http://localhost:7474
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ── Resolve tooling ──────────────────────────────────────────────────────────
BUN="$(command -v bun 2>/dev/null || true)"
[ -z "$BUN" ] && [ -x "$HOME/.bun/bin/bun" ] && BUN="$HOME/.bun/bin/bun"

# `sed -l` (line-buffered) is BSD/macOS; GNU sed spells the same thing -u.
# Without it the three interleaved logs sit in a 4 KB buffer and arrive in
# bursts, which reads as a hung service.
SEDU="-l"; sed -l '' </dev/null >/dev/null 2>&1 || SEDU="-u"

fail() { echo "[dev] ✗ $1" >&2; exit 1; }
warn() { echo "[dev] ! $1" >&2; }

command -v uv  >/dev/null 2>&1 || fail "'uv' not found on PATH"
command -v npm >/dev/null 2>&1 || fail "'npm' not found on PATH (nvm: 'nvm use 22'?)"
[ -n "$BUN" ] || fail "'bun' not found (PATH or ~/.bun/bin/bun) — install: curl -fsSL https://bun.sh/install | bash"

[ -d "$ROOT/open-pencil" ]   || fail "open-pencil/ missing — run: git submodule update --init open-pencil"
[ -d "$ROOT/frontend" ]      || fail "frontend/ directory missing"
[ -d "$ROOT/open-pencil/node_modules" ] || warn "open-pencil/node_modules missing — run: (cd open-pencil && bun install)"
[ -d "$ROOT/frontend/node_modules" ]    || warn "frontend/node_modules missing — run: (cd frontend && npm install)"
[ -f "$ROOT/.env" ] || warn ".env missing — run: cp .env.example .env (services will use defaults)"

WITH_DB="${WITH_DB:-1}"
WITH_ANALYZER="${WITH_ANALYZER:-1}"
STOP_ALL="${STOP_ALL:-0}"

STACK="$ROOT/scripts/analyzer-stack.sh"
NEO4J_CONTAINER="${NEO4J_CONTAINER:-aesf-neo4j}"

listening() { lsof -ti :"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# ── graph store ──────────────────────────────────────────────────────────────
# docker-compose.yml owns the container and its named volumes, so this only
# ever brings it up — the data outlives any single dev session.
start_graph_store() {
  if listening 7687; then echo "[dev] Neo4j already up (bolt 7687)"; return; fi
  if ! command -v docker >/dev/null 2>&1; then
    warn "docker not found — skipping Neo4j (WITH_DB=0 to silence)"; return
  fi
  echo "[dev] starting Neo4j ($NEO4J_CONTAINER)..."
  docker compose -f "$ROOT/docker-compose.yml" up -d >/dev/null 2>&1 \
    || { warn "docker compose up failed — is Docker Desktop running?"; return; }
  # Bolt listens well before it accepts queries; the backend's first requests
  # would otherwise fail against a database still recovering.
  for _ in $(seq 1 60); do listening 7687 && break; sleep 1; done
  if listening 7687; then
    echo "[dev]   bolt 7687 ready · browser http://localhost:7474"
  else
    warn "Neo4j did not come up — docker compose logs neo4j"
  fi
}

# ── analyzer stack ───────────────────────────────────────────────────────────
# scripts/analyzer-stack.sh owns these six: it reads .env for the database
# target and the LLM config, and passes both NEO4J_* and ROBO_NEO4J_* because
# the services disagree on the prefix.
start_analyzer_stack() {
  [ -x "$STACK" ] || { warn "scripts/analyzer-stack.sh not found or not executable — skipping the analyzer stack"; return; }
  if listening 9000 && listening 5001; then echo "[dev] analyzer stack already up"; return; fi
  echo "[dev] starting the analyzer stack..."
  "$STACK" up 2>&1 | sed $SEDU 's/^/[analyzer] /'
}

COMPONENT_LIBRARY_PATH="${COMPONENT_LIBRARY_PATH:-docs/components.fig}"
[ -f "$ROOT/open-pencil/$COMPONENT_LIBRARY_PATH" ] || \
  warn "component library '$COMPONENT_LIBRARY_PATH' not found under open-pencil/ — wireframe service may start without components"

# ── Shutdown: SIGTERM then SIGKILL the well-known ports' listeners ───────────
# `kill 0` alone leaks uvicorn workers when async threads (httpx, asyncio) keep
# the interpreter alive past SIGTERM. We follow up with SIGKILL on whoever is
# still listening on our three ports, so a re-run of dev.sh doesn't fail with
# "Address already in use".
# The analyzer stack and Neo4j are deliberately left running: they are slow to
# start and nothing about them is per-session. STOP_ALL=1 takes the analyzer
# stack down too. Neo4j is never stopped here — that is a deliberate act, not
# a side effect of quitting a dev server.
trap '
  echo; echo "[dev] stopping backend / wireframe / frontend...";
  kill 0 2>/dev/null;
  sleep 1;
  for p in 8000 7610 5173; do
    pids=$(lsof -ti :$p -sTCP:LISTEN 2>/dev/null);
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null;
  done
  if [ "$STOP_ALL" = "1" ] && [ -x "$STACK" ]; then
    echo "[dev] stopping the analyzer stack...";
    "$STACK" down >/dev/null 2>&1;
  fi
' EXIT

# ── Preflight: free our own three ports ──────────────────────────────────────
# The exit trap already SIGKILLs whatever listens on 8000 / 7610 / 5173, so this
# script treats them as its own. What it did not do was check them on the way
# in — so a previous run killed mid-flight, or a uvicorn started by hand, left a
# listener behind and the backend died with "Address already in use" while Vite
# quietly moved to 5174. Both failures scroll past in an interleaved log and the
# app looks up until something calls the API.
for port in 8000 7610 5173; do
  pids="$(lsof -ti :$port -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "[dev] port $port already taken (pid $(echo $pids | tr '\n' ' ')) — reclaiming"
    kill $pids 2>/dev/null
    sleep 1
    pids="$(lsof -ti :$port -sTCP:LISTEN 2>/dev/null || true)"
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null
  fi
done

# ── 0. shared services ───────────────────────────────────────────────────────
# Started before the app so the backend does not spend its first requests
# retrying a database that is not there yet.
[ "$WITH_DB" = "1" ]       && start_graph_store
[ "$WITH_ANALYZER" = "1" ] && start_analyzer_stack

echo
echo "[dev] starting app — Ctrl+C to stop backend / wireframe / frontend"
echo "[dev]   backend   → http://localhost:8000"
echo "[dev]   wireframe → http://localhost:7610"
echo "[dev]   frontend  → http://localhost:5173"
[ "$WITH_ANALYZER" = "1" ] && echo "[dev]   analyzer  → gateway 9000, remote 5001 (stays up after Ctrl+C)"
[ "$WITH_DB" = "1" ]       && echo "[dev]   neo4j     → bolt 7687, browser 7474 (stays up)"
echo

# ── 1. backend ───────────────────────────────────────────────────────────────
(
  cd "$ROOT"
  # --timeout-graceful-shutdown 3: workers stuck in Neo4j sessions / plugin
  # poll loops get SIGKILL after 3 s, preventing zombie workers from piling
  # up on port 8000 and stalling subsequent requests.
  uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload --timeout-graceful-shutdown 3 2>&1 | sed $SEDU 's/^/[backend ] /'
) &

# ── 2. open-pencil wireframe service ─────────────────────────────────────────
(
  cd "$ROOT/open-pencil"
  COMPONENT_LIBRARY_PATH="$COMPONENT_LIBRARY_PATH" "$BUN" packages/cli/src/wireframe-service.ts 2>&1 | sed $SEDU 's/^/[wirefrm ] /'
) &

# ── 3. frontend ──────────────────────────────────────────────────────────────
(
  cd "$ROOT/frontend"
  npm run dev 2>&1 | sed $SEDU 's/^/[frontend] /'
) &

wait
