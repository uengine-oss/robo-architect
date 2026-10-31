#!/usr/bin/env bash
# Build the macOS (Apple Silicon) release runtime — the folder electron-builder packs as
# <app>/Contents/Resources/runtime and desktop/src/main/docker-stack.ts reads in a packaged app.
# The macOS counterpart of build-packaged-runtime.ps1 (Windows, bundled Python only).
#
#   scripts/build-packaged-runtime.sh [--version 0.1.0] [--python 3.14] [--out <dir>]
#                                     [--registry ghcr.io/uengine-oss] [--source-tag lite-mac]
#                                     [--digests <image-digests.json>]
#
# What it writes (default --out desktop/resources/runtime, gitignored):
#   runtime-manifest.json   images = <registry>/robo-architect-lite-<component>:<version> with the
#                           IDs of the local uengine/*:<source-tag> images they are pushed from
#                           (scripts/release/push-images.sh), imagePull=true, no image archive —
#                           the app pulls what is missing on first launch (docker-images.ts).
#                           With --digests (written by push-images.sh) also the registry digests
#                           (pulls are pinned to them) and the compressed sizes (progress totals).
#   compose.yml             desktop/runtime/compose.yml
#   config/*.env            per-service settings, no secrets (analyzer: Claude Code bridge,
#                           embeddings off — no OpenAI key needed)
#   architect/python/       a relocatable CPython (uv-managed, python-build-standalone) with the
#                           locked dependencies (uv.lock, no dev extras) installed into it
#   architect/app/          api/ + skills/ + pyproject.toml + uv.lock (no tests, caches, .venv),
#                           and a settings .env with no secrets
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
VERSION=$(node -p "require('$ROOT/desktop/package.json').version")
PYTHON_VERSION=""
OUT="$ROOT/desktop/resources/runtime"
REGISTRY="ghcr.io/uengine-oss"
SOURCE_TAG="lite-mac"
DIGESTS=""

while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION=$2; shift 2 ;;
    --python) PYTHON_VERSION=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --registry) REGISTRY=$2; shift 2 ;;
    --source-tag) SOURCE_TAG=$2; shift 2 ;;
    --digests) DIGESTS=$2; shift 2 ;;
    -h|--help) sed -n '2,26p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\033[36m[runtime]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[runtime]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(uname -s)/$(uname -m)" = "Darwin/arm64" ] || die "build on an Apple Silicon Mac (the runtime is arm64 macOS)"
command -v uv >/dev/null || die "uv is required (https://docs.astral.sh/uv/)"
command -v docker >/dev/null || die "docker is required (image IDs are read from the local images)"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac
[ "$OUT" != "/" ] && [ "$(basename "$OUT")" = "runtime" ] || die "--out must be a folder named runtime: $OUT"

# the development venv's Python, so the release runs on what the backend is tested with
if [ -z "$PYTHON_VERSION" ]; then
  PYTHON_VERSION=$(sed -n 's/^version_info = \([0-9]*\.[0-9]*\).*/\1/p' "$ROOT/.venv/pyvenv.cfg" 2>/dev/null || true)
  PYTHON_VERSION=${PYTHON_VERSION:-3.14}
fi

say "release $VERSION → $OUT (Python $PYTHON_VERSION, images $REGISTRY/robo-architect-lite-*:$VERSION from *:$SOURCE_TAG)"
find "$OUT" -mindepth 1 -maxdepth 1 ! -name .gitkeep -exec rm -rf {} + 2>/dev/null || true
mkdir -p "$OUT/config" "$OUT/architect/app"

# ── 1. relocatable CPython ─────────────────────────────────────────────────────────────────
uv python install "$PYTHON_VERSION" >/dev/null
# --no-project and a neutral cwd: inside the repo uv would answer with the project's .venv, which
# points back at this machine's interpreter (pyvenv.cfg) and is not relocatable
MANAGED=$(cd / && uv python find --managed-python --no-project "$PYTHON_VERSION")
PYROOT=$(cd "$(dirname "$MANAGED")/.." && pwd)
[ -f "$PYROOT/pyvenv.cfg" ] && die "$PYROOT is a virtual environment, not an interpreter"
say "Python from $PYROOT"
cp -R "$PYROOT" "$OUT/architect/python"            # BSD cp -R keeps the bin/ symlinks
PY="$OUT/architect/python/bin/python3"
"$PY" -c 'import sys; assert sys.prefix == sys.base_prefix and sys.prefix.endswith("architect/python"), sys.prefix' \
  || die "the copied interpreter does not run from its new place"
PYMM=$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')

# ── 2. locked dependencies ─────────────────────────────────────────────────────────────────
say "installing the locked dependencies"
(cd "$ROOT" && uv export --locked --no-dev --no-emit-project --no-header --format requirements-txt \
  --output-file "$OUT/architect/requirements.lock.txt" >/dev/null)
uv pip install --quiet --python "$PY" --requirements "$OUT/architect/requirements.lock.txt" \
  --require-hashes --break-system-packages --link-mode copy --strict

# ── 3. application snapshot ────────────────────────────────────────────────────────────────
say "copying api/ and skills/"
for dir in api skills; do
  rsync -a --delete \
    --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'tests' --exclude 'logs' \
    --exclude '*.pyc' --exclude '*.pyo' --exclude '.DS_Store' \
    "$ROOT/$dir/" "$OUT/architect/app/$dir/"
done
cp "$ROOT/pyproject.toml" "$ROOT/uv.lock" "$OUT/architect/app/"

# ── 4. trim what a server never runs ───────────────────────────────────────────────────────
PYOUT="$OUT/architect/python"
rm -rf "$PYOUT/include" "$PYOUT/share" "$PYOUT/lib/pkgconfig" \
  "$PYOUT/lib/python$PYMM/idlelib" "$PYOUT/lib/python$PYMM/turtledemo" "$PYOUT/lib/python$PYMM/tkinter" \
  "$PYOUT/lib/python$PYMM/test" "$PYOUT/lib/python$PYMM/ensurepip" \
  "$PYOUT"/lib/tcl* "$PYOUT"/lib/tk* "$PYOUT"/lib/itcl* "$PYOUT"/lib/thread* \
  "$PYOUT"/lib/libtcl* "$PYOUT"/lib/libtk* "$PYOUT"/lib/python$PYMM/lib-dynload/_tkinter*
# console scripts carry this machine's absolute path in their shebang — the app runs `python -m`
find "$PYOUT/bin" -mindepth 1 ! -name 'python' ! -name 'python3' ! -name "python$PYMM" -exec rm -f {} +
find "$OUT/architect" -name '__pycache__' -type d -prune -exec rm -rf {} +

# ── 5. bytecode: the bundle is read-only to the app (PYTHONDONTWRITEBYTECODE in a packaged app) ─
say "compiling bytecode"
"$PY" -m compileall -q -j 0 --invalidation-mode unchecked-hash "$PYOUT/lib/python$PYMM" >/dev/null || true
"$PY" -m compileall -q -j 0 --invalidation-mode checked-hash "$OUT/architect/app/api" >/dev/null

# ── 6. compose, service settings, the backend's settings file, manifest ────────────────────
cp "$ROOT/desktop/runtime/compose.yml" "$OUT/compose.yml"
python3 - "$ROOT" "$OUT" "$VERSION" "$REGISTRY" "$SOURCE_TAG" "$DIGESTS" <<'PY'
import hashlib, json, os, subprocess, sys
from pathlib import Path

root, out, version, registry, source_tag, digests_file = sys.argv[1:7]
root, out = Path(root), Path(out)

# manifest key → (local image it is pushed from, release component name)
IMAGES = {
    "graphDb":   ("uengine/ontological-db",    "graph-db"),
    "graphBolt": ("uengine/ontological-bolt",  "graph-bolt"),
    "analyzer":  ("uengine/robo-analyzer",     "analyzer"),
    "catalog":   ("uengine/robo-data-catalog", "catalog"),
    "fabric":    ("uengine/robo-data-fabric",  "fabric"),
    "parser":    ("uengine/robo-antlr-parser", "parser"),
    "gateway":   ("uengine/robo-api-gateway",  "gateway"),
}

# Per-service settings (the same values as the development runtime, robo-lite-src/build/make-runtime.py).
# The analyzer's LLM is the user's Claude Code through the host API (/api/llm-bridge/v1), embeddings
# off (no semantic search). Secrets appear as bare names: compose passes the launching
# environment's value, and a packaged app has none.
ENV = {
    "analyzer": """ROBO_LLM_CONFIG=claude_code_bridge
ROBO_LLM_API_KEY=claude-code-bridge
ROBO_LLM_REPETITION_GUARD=true
ROBO_LLM_RESPONSE_CACHE=true
ROBO_LLM_RESPONSE_CACHE_REQUIRE_HIT=false
ROBO_BUDGET_RUN_USD=20
ROBO_PIPELINE_MAX_CONCURRENCY=16
ROBO_PIPELINE_LLM_MAX_CONCURRENCY=4
ROBO_PIPELINE_BATCH_MAX_TOKENS=1500
ROBO_PIPELINE_EMBED_ENABLED=false
ROBO_CATALOG_ENABLED=true
ROBO_CATALOG_TIMEOUT_SECONDS=120
ROBO_NEO4J_RETRY_MAX_ATTEMPTS=5
ROBO_NEO4J_RETRY_BACKOFF_SECONDS=2
ROBO_RUNTIME_EVENT_FILE_ENABLED=true
ROBO_RUNTIME_EVENT_LEVEL=INFO
ROBO_RUN_OUTPUT_DIR=/data/logs
ROBO_EMBED_PROVIDER=openai
ROBO_EMBED_MODEL=text-embedding-3-small
ROBO_EMBED_API_BASE=https://api.openai.com/v1
ROBO_EMBED_API_KEY
ROBO_SEARCH_LLM_CONFIG=claude_code_bridge
ROBO_SEARCH_LLM_API_KEY=claude-code-bridge
""",
    "catalog": """LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY
OPENAI_API_KEY
EMBEDDING_MODEL=text-embedding-3-small
FK_INFERENCE_ENABLED=true
FK_SAMPLE_SIZE=25
FK_SIMILARITY_THRESHOLD=0.8
FK_MATCH_RATIO_THRESHOLD=0.8
FK_CONCURRENCY=5
METADATA_TIMEOUT_CONNECT=5
METADATA_TIMEOUT_REQUEST=30
""",
    "fabric": """DATA_FABRIC_QUERY_TIMEOUT_SECONDS=30
OPENAI_API_KEY
ROBO_DATASOURCE_REPLACE_LOCALHOST=host.docker.internal
""",
    "parser": """PARSER_REPAIR_APPLY_TO_SOURCE=false
PARSER_REPAIR_AGENT_ENABLED=false
""",
    "gateway": "",
}

# The host Architect API's settings (api/main.py load_dotenv). Proposals, plans and implementation
# run as skills through the local Claude Code CLI; Neo4j/Bolt settings come from the app at start.
ARCHITECT_ENV = """# Robo Architect Lite — host Architect API settings (no secrets).
SKILL_RUNNER_PROVIDER=claude_cli
LLM_PROVIDER=openai
"""


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def head(path) -> str:
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "0" * 40


def image_id(ref: str) -> str:
    try:
        return subprocess.check_output(["docker", "image", "inspect", ref, "--format", "{{.Id}}"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        raise SystemExit(f"[runtime] the local image {ref} is missing — build it first")


def image_size(ref: str) -> int:
    return int(subprocess.check_output(["docker", "image", "inspect", ref, "--format", "{{.Size}}"], text=True).strip())


for name, text in ENV.items():
    (out / "config" / f"{name}.env").write_text(text, encoding="utf-8")
(out / "architect" / "app" / ".env").write_text(ARCHITECT_ENV, encoding="utf-8")

pushed = {}
if digests_file:
    pushed = json.loads(Path(digests_file).read_text(encoding="utf-8"))

images, ids, digests, sizes = {}, {}, {}, {}
for key, (local, component) in IMAGES.items():
    ref = f"{registry}/robo-architect-lite-{component}:{version}"
    images[key] = ref
    ids[key] = image_id(f"{local}:{source_tag}")
    entry = pushed.get(key)
    if entry:
        if entry.get("ref") != ref:
            raise SystemExit(f"[runtime] {digests_file}: {key} was pushed as {entry.get('ref')}, not {ref}")
        if entry.get("id") != ids[key]:
            raise SystemExit(f"[runtime] {key}: {local}:{source_tag} is {ids[key]} but {entry.get('id')} was pushed — push again")
        digests[key] = entry["digest"]
        sizes[key] = int(entry["size"])
    else:
        sizes[key] = image_size(f"{local}:{source_tag}")

lite_src = Path("/Users/uengine/robo-lite-src")
environment = {k: {"file": f"config/{k}.env", "sha256": sha(out / "config" / f"{k}.env")} for k in ENV}
environment["architect"] = {"file": "architect/app/.env", "sha256": sha(out / "architect" / "app" / ".env")}
manifest = {
    "schemaVersion": 3,
    "releaseId": f"lite-{version}",
    "releaseChannel": "stable",
    "releaseVariant": "lite",
    "authEnforced": False,
    "authProvider": "none",
    "credentialNames": ["OPENAI_API_KEY", "LLM_API_KEY", "ROBO_LLM_API_KEY", "ROBO_EMBED_API_KEY",
                        "ROBO_SEARCH_LLM_API_KEY"],
    "composeFile": "compose.yml",
    "imagePull": True,
    "images": images,
    "imageIds": ids,
    **({"imageDigests": digests} if len(digests) == len(IMAGES) else {}),
    "imageSizes": sizes,
    "architect": {"python": "architect/python/bin/python3", "app": "architect/app", "entrypoint": "api.main:app"},
    "environment": environment,
    "source": {
        "workspace": "0" * 40,
        "ontological": head(lite_src / "ontological-db"),
        "architect": head(root),
        "openPencil": head(root / "open-pencil"),
        "analyzer": head(root / "robo-analyzer/robo-data-analyzer"),
        "catalog": head(root / "robo-analyzer/robo-data-catalog"),
        "fabric": head(root / "robo-analyzer/robo-data-fabric"),
        "frontend": head(root / "robo-analyzer/robo-data-frontend"),
        "parser": head(lite_src / "antlr-code-parser"),
        "gateway": head(lite_src / "api-gateway"),
    },
}
if digests_file and len(digests) != len(IMAGES):
    raise SystemExit(f"[runtime] {digests_file} lists {len(digests)} of {len(IMAGES)} images")
(out / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
total = sum(sizes.values())
print(f"[runtime] manifest: {len(images)} images, download {total / 1e9:.2f} GB"
      f"{' (pinned to pushed digests)' if digests else ' (no digests yet — pull by tag)'}")
for k in IMAGES:
    print(f"  {k:10} {images[k]}  {ids[k][:19]}  {sizes[k] / 1e6:6.0f} MB")
PY

# ── 7. the bundled backend imports ─────────────────────────────────────────────────────────
say "checking that the bundled backend imports"
CHECK_LOG=$(mktemp -t robo-runtime-import)
(cd "$OUT/architect/app" && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -c 'import api.main' >/dev/null 2>"$CHECK_LOG") \
  || { tail -20 "$CHECK_LOG" >&2; die "import api.main failed"; }
rm -f "$CHECK_LOG"
du -sh "$OUT" | awk '{print "[runtime] ready: " $2 " (" $1 ")"}'
