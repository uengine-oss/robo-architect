#!/usr/bin/env bash
#
# analyzer-stack.sh — start / stop the analyzer stack on macOS and Linux.
#
# robo-workspace (`robo.cmd`) is Windows-only: its runner, bundled Python and
# NSIS packaging are all PowerShell. This script is the POSIX equivalent of
# `robo.cmd up architect-web` for the analyzer half — the same six services,
# started in the same order, wired to the same ports the gateway routes to.
#
#   ./scripts/analyzer-stack.sh setup    one-time: clone, deps, Java build
#   ./scripts/analyzer-stack.sh up       start the six services
#   ./scripts/analyzer-stack.sh down     stop what this script started
#   ./scripts/analyzer-stack.sh status   port-by-port health
#   ./scripts/analyzer-stack.sh logs <service>
#
# `dev.sh` calls `up` for you; run it directly when you want the stack without
# the Architect app, or to read logs after `dev.sh` has exited.
#
#   service        port   repo
#   remote         5001   robo-analyzer/robo-data-frontend  (built + previewed)
#   analyzer       5502   robo-analyzer/robo-data-analyzer
#   catalog        5503   robo-analyzer/robo-data-catalog
#   fabric         8404   robo-analyzer/robo-data-fabric
#   parser         8081   ../antlr-code-parser          (Java jar)
#   gateway        9000   ../robo-api-gateway           (Java jar)
#
# Prerequisites — see the header of dev.sh for the full list. In short:
# python3.11+, uv, node 20+, java 17, maven, docker (for Neo4j).
#
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ANALYZER_DIR="$ROOT/robo-analyzer"

# The parser and the gateway are separate repositories, not submodules. They
# default to siblings of this repo — the layout robo-workspace produces under
# `project/` — and can be pointed elsewhere.
PARSER="${ROBO_PARSER_DIR:-$(cd "$ROOT/.." && pwd)/antlr-code-parser}"
GATEWAY="${ROBO_GATEWAY_DIR:-$(cd "$ROOT/.." && pwd)/robo-api-gateway}"

LOGS="$ROOT/.robo-logs"
PIDS="$ROOT/.robo-pids"
mkdir -p "$LOGS" "$PIDS"

# ── Configuration ────────────────────────────────────────────────────────────
# The analyzer services are separate repositories with no .env of their own.
# Without the exports below each one falls back to its built-in defaults, finds
# an empty LLM config, and the UI comes up while every analysis quietly fails.
#
# The key names differ per service. The analyzer reads ROBO_NEO4J_*; catalog
# and data-fabric read unprefixed NEO4J_*. desktop/runtime/compose.yml splits
# them exactly the same way. Pass only one and the other silently falls back to
# bolt://localhost:7687 and reports "The Neo4j server is not reachable".
#
# Values already in the environment win — one-off overrides stay possible.
if [ -f "$ROOT/.env" ]; then
  while IFS= read -r line; do
    case "$line" in
      ROBO_NEO4J_*=*|ROBO_LLM_*=*|ROBO_AGENT_*=*|ROBO_PIPELINE_*=*|NEO4J_*=*|ANALYZER_NEO4J_*=*)
        key="${line%%=*}"
        [ -n "${!key:-}" ] && continue
        export "$key=${line#*=}"
        ;;
    esac
  done < "$ROOT/.env"
fi

# Fill the ROBO_ side from the unprefixed side when only the latter is set.
for suffix in URI USER PASSWORD; do
  robo="ROBO_NEO4J_$suffix"; plain="NEO4J_$suffix"
  [ -z "${!robo:-}" ] && [ -n "${!plain:-}" ] && export "$robo=${!plain}"
done

# ── Which database the analyzer writes to ────────────────────────────────────
# **The analyzer wipes its target database at the start of every run**
# (`MATCH (n) DETACH DELETE n`, robo-data-analyzer/README.md §1.2 — deliberate,
# so leftovers from an earlier run can't mask a failure). Point it at the
# database holding your Architect design and one analysis erases the design.
#
# So the analyzer's database is ANALYZER_NEO4J_DATABASE, never NEO4J_DATABASE.
# The Architect backend already knows this name — its mapper reads the analyzer
# graph cross-database through it (api/platform/env.py:get_analyzer_neo4j_database).
#
# Neo4j Community serves exactly one database, `neo4j`, so the two names cannot
# differ there. To separate them, switch docker-compose.yml to the enterprise
# image (free for development) and create the database once:
#
#   image: neo4j:5.15.0-enterprise
#   environment:
#     - NEO4J_ACCEPT_LICENSE_AGREEMENT=yes
#
#   docker compose up -d
#   docker exec -it aesf-neo4j cypher-shell -u neo4j -p aesf_password_2024 \
#     "CREATE DATABASE analyzer IF NOT EXISTS"
#
# then set ANALYZER_NEO4J_DATABASE=analyzer in .env.
#
# The three analyzer services are one unit: the analyzer writes what catalog
# and data-fabric read. They must all be given the same database name, so the
# unprefixed NEO4J_DATABASE that catalog and fabric read is overridden here for
# the stack's children only. This script never starts the Architect backend, so
# the design-side value in .env is untouched.
ANALYZER_DB="${ANALYZER_NEO4J_DATABASE:-${ROBO_NEO4J_DATABASE:-}}"
DESIGN_DB="${NEO4J_DATABASE:-neo4j}"

if [ -z "$ANALYZER_DB" ]; then
  ANALYZER_DB="$DESIGN_DB"
fi
export ROBO_NEO4J_DATABASE="$ANALYZER_DB"
export NEO4J_DATABASE="$ANALYZER_DB"

# Refuse to run against the design database unless the caller insists. This is
# the one failure here that destroys work rather than printing an error.
guard_shared_database() {
  [ "$ANALYZER_DB" = "$DESIGN_DB" ] || return 0
  [ "${ALLOW_SHARED_GRAPH:-0}" = "1" ] && {
    echo "  ! ALLOW_SHARED_GRAPH=1 — analysis will wipe '$DESIGN_DB', design included"
    return 0
  }
  cat >&2 <<EOF
[analyzer-stack] ✗ analyzer and design would share database '$DESIGN_DB'.

  Every analysis run starts with MATCH (n) DETACH DELETE n, so this erases the
  Architect design. Pick one:

    1. give the analyzer its own database (needs the enterprise image — see the
       comment block in this script), then set in .env:
         ANALYZER_NEO4J_DATABASE=analyzer
    2. accept the wipe on a throwaway graph:
         ALLOW_SHARED_GRAPH=1 ./scripts/analyzer-stack.sh up
    3. run the app without the analyzer:
         WITH_ANALYZER=0 ./dev.sh
EOF
  return 1
}

# The parser and the analyzer exchange files through this directory: the parser
# writes <root>/analysis/*.json and the analyzer's step2 reads them.
#
# Both read ROBO_DATA_DIR but **their defaults differ** — the analyzer uses the
# sibling `data` of its own repo, the parser the parent `data` of its working
# directory. Unset, the parser writes one place and the analyzer searches
# another: parsing succeeds and the next step dies with "antlr JSON directory
# not found". The analyzer's location wins; the Docker runtime mounts one
# shared volume onto both services for the same reason.
export ROBO_DATA_DIR="${ROBO_DATA_DIR:-$ANALYZER_DIR/data}"
mkdir -p "$ROBO_DATA_DIR"

# Service ports — these are the gateway's routing defaults.
PORT_ANALYZER=5502
PORT_CATALOG=5503
PORT_FABRIC=8404
PORT_PARSER=8081
PORT_GATEWAY=9000
PORT_ARCHITECT=8000
PORT_REMOTE=5001      # analyzer frontend, the Module Federation remote

# ─────────────────────────────────────────────────────────────────────────────

start_bg() {   # start_bg <name> <workdir> <command...>
  local name="$1" dir="$2"; shift 2
  if [ -f "$PIDS/$name.pid" ] && kill -0 "$(cat "$PIDS/$name.pid")" 2>/dev/null; then
    echo "  $name already running (pid $(cat "$PIDS/$name.pid"))"
    return
  fi
  # Redirect the **whole background subshell**, not the inner command. Applied
  # to the command alone, the wrapping shell keeps its own stdout/stderr open
  # for as long as the service lives, and a caller reading this script through
  # a pipe (dev.sh's `| sed`) never sees EOF and hangs forever.
  #
  # `exec` replaces the subshell with the command, so no intermediate bash is
  # left behind: `$!` is the service's own pid and `down` can signal it
  # directly. stdin is /dev/null so a background service never grabs the tty.
  ( cd "$dir" && exec nohup "$@" ) > "$LOGS/$name.log" 2>&1 < /dev/null &
  echo $! > "$PIDS/$name.pid"
  echo "  $name started (pid $(cat "$PIDS/$name.pid"))"
}

wait_http() {  # wait_http <port> <max seconds>
  local port="$1" max="${2:-30}" i=0
  while [ $i -lt "$max" ]; do
    curl -s -m 2 -o /dev/null "http://127.0.0.1:$port/" 2>/dev/null && return 0
    sleep 1; i=$((i+1))
  done
  return 1
}

need() { command -v "$1" >/dev/null 2>&1 || { echo "[analyzer-stack] ✗ '$1' not found on PATH" >&2; return 1; }; }

# ─────────────────────────────────────────────────────────────────────────────

cmd_setup() {
  echo "== setup =="
  need git || return 1; need uv || return 1; need npm || return 1
  need java || return 1; need mvn || return 1

  local parent; parent="$(cd "$ROOT/.." && pwd)"
  for spec in "antlr-code-parser:$PARSER" "robo-api-gateway:$GATEWAY"; do
    local repo="${spec%%:*}" path="${spec#*:}"
    if [ ! -d "$path/.git" ]; then
      echo "  cloning $repo → $path"
      git clone -q "https://github.com/uengine-oss/$repo.git" "$path" \
        || { echo "  ✗ clone failed: $repo" >&2; return 1; }
    else
      echo "  $repo present"
    fi
  done

  # The analyzer services are submodules pinned by this repo — checked out at
  # the commits Architect was verified against, not at their own main.
  echo "  initializing analyzer submodules"
  git -C "$ROOT" submodule update --init --recursive -- \
    robo-analyzer/robo-data-analyzer \
    robo-analyzer/robo-data-catalog \
    robo-analyzer/robo-data-fabric \
    robo-analyzer/robo-data-frontend >/dev/null 2>&1

  for svc in robo-data-analyzer robo-data-catalog robo-data-fabric; do
    echo "  $svc dependencies"
    ( cd "$ANALYZER_DIR/$svc" \
        && uv venv -q .venv 2>/dev/null \
        && uv pip install -q -r requirements.txt --python .venv/bin/python ) \
      || echo "  ! $svc dependency install failed — see above"
  done

  echo "  analyzer frontend dependencies"
  ( cd "$ANALYZER_DIR/robo-data-frontend" && npm install --silent )

  echo "  Java build (this takes a while)"
  ( cd "$GATEWAY" && mvn -q -DskipTests package ) || echo "  ! gateway build failed"
  ( cd "$PARSER"  && mvn -q -DskipTests package ) || echo "  ! parser build failed"

  # The Architect frontend pulls remoteEntry.js from this build at runtime.
  echo "  building the analyzer frontend remote"
  ( cd "$ANALYZER_DIR/robo-data-frontend" && npm run build >/dev/null 2>&1 ) \
    || echo "  ! remote build failed — the Analysis tab will be empty"

  echo "done. './scripts/analyzer-stack.sh up' to start."
}

jar_of() { ls "$1"/target/*.jar 2>/dev/null | grep -v -- '-sources\|-javadoc' | head -1; }

cmd_up() {
  echo "== up =="
  guard_shared_database || return 1

  local gw_jar parser_jar
  gw_jar="$(jar_of "$GATEWAY")"
  parser_jar="$(jar_of "$PARSER")"
  [ -n "$gw_jar" ] && [ -n "$parser_jar" ] || {
    echo "  ! Java jars missing — run './scripts/analyzer-stack.sh setup' first" >&2
  }

  # The remote must be the preview server (5001), not dev (3000): only the
  # preview config allows the cross-origin request Architect makes for
  # remoteEntry.js. `npm run preview` serves the last build — rebuild after
  # changing the analyzer frontend.
  start_bg remote "$ANALYZER_DIR/robo-data-frontend" \
    npm run preview -- --host 127.0.0.1 --port "$PORT_REMOTE" --strictPort

  start_bg analyzer "$ANALYZER_DIR/robo-data-analyzer" \
    .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port "$PORT_ANALYZER"

  ( export PORT=$PORT_CATALOG
    start_bg catalog "$ANALYZER_DIR/robo-data-catalog" .venv/bin/python main.py )

  ( export DATA_FABRIC_PORT=$PORT_FABRIC
    start_bg fabric "$ANALYZER_DIR/robo-data-fabric" .venv/bin/python main.py )

  [ -n "$parser_jar" ] && \
    ( export SERVER_PORT=$PORT_PARSER
      start_bg parser "$PARSER" java -jar "$parser_jar" )

  # The gateway goes last — routing means nothing until the upstreams answer.
  # Its defaults disagree with the services' actual ports, so they are set here.
  [ -n "$gw_jar" ] && \
    ( export ROBO_ANALYZER_URL="http://127.0.0.1:$PORT_ANALYZER"
      export ROBO_CATALOG_URL="http://127.0.0.1:$PORT_CATALOG"
      export ROBO_DATA_FABRIC_URL="http://127.0.0.1:$PORT_FABRIC"
      export ROBO_ANTLR_URL="http://127.0.0.1:$PORT_PARSER"
      export ROBO_ARCHITECT_URL="http://127.0.0.1:$PORT_ARCHITECT"
      start_bg gateway "$GATEWAY" java -jar "$gw_jar" )

  echo
  echo "waiting for the gateway..."
  wait_http "$PORT_GATEWAY" 60 && echo "  gateway responding" \
    || echo "  no response — check .robo-logs/gateway.log"
  echo
  cmd_status
}

cmd_down() {
  echo "== down =="
  for f in "$PIDS"/*.pid; do
    [ -e "$f" ] || continue
    local name pid
    name="$(basename "$f" .pid)"
    pid="$(cat "$f")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && echo "  $name stopped (pid $pid)"
      # children too (uvicorn reload workers, npm → vite)
      pkill -P "$pid" 2>/dev/null
    fi
    rm -f "$f"
  done
  echo "done. The Architect backend (8000) and Neo4j are left alone."
}

cmd_status() {
  printf "%-6s %-26s %s\n" "port" "service" "status"
  check() { # check <port> <name>
    local c; c="$(curl -s -m 3 -o /dev/null -w "%{http_code}" "http://127.0.0.1:$1/" 2>/dev/null)"
    printf "%-6s %-26s %s\n" "$1" "$2" "${c:-no response}"
  }
  check "$PORT_REMOTE"    "analyzer frontend (remote)"
  check "$PORT_ANALYZER"  "analyzer API"
  check "$PORT_CATALOG"   "catalog"
  check "$PORT_FABRIC"    "data fabric"
  check "$PORT_PARSER"    "ANTLR parser"
  check "$PORT_GATEWAY"   "API gateway"
  check "$PORT_ARCHITECT" "Architect API"
  echo
  echo "404/500 at the root is normal — most of these have no root route."
  echo "routing:"
  printf "  /api/gateway/robo/**  → %s\n" \
    "$(curl -s -m 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT_GATEWAY/api/gateway/robo/health" 2>/dev/null)"
  printf "  /api/gateway/antlr    → %s (matching a direct call means it routes)\n" \
    "$(curl -s -m 5 -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT_GATEWAY/api/gateway/antlr" 2>/dev/null)"
  echo
  echo "analyzer database: $ROBO_NEO4J_DATABASE   design database: $DESIGN_DB"
}

cmd_logs() {
  local name="${1:-}"
  if [ -z "$name" ]; then
    echo "usage: ./scripts/analyzer-stack.sh logs <remote|analyzer|catalog|fabric|parser|gateway>"
    ls "$LOGS" 2>/dev/null
    return
  fi
  tail -f "$LOGS/$name.log"
}

case "${1:-}" in
  setup)  cmd_setup ;;
  up)     cmd_up ;;
  down)   cmd_down ;;
  status) cmd_status ;;
  logs)   shift; cmd_logs "$@" ;;
  *)
    echo "usage: ./scripts/analyzer-stack.sh {setup|up|down|status|logs <service>}"
    exit 1
    ;;
esac
