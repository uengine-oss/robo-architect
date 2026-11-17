#!/usr/bin/env bash
# Build the macOS (Apple Silicon) release runtime — the folder electron-builder packs as
# <app>/Contents/Resources/runtime and desktop/src/main/docker-stack.ts reads in a packaged app.
# The macOS counterpart of build-packaged-runtime-win.sh (Windows x64, cross-built on this Mac).
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
. "$ROOT/scripts/packaged-runtime-common.sh"      # say, die, copy_app_snapshot, write_runtime_files
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
copy_app_snapshot "$ROOT" "$OUT/architect/app"

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
write_runtime_files --root "$ROOT" --out "$OUT" --version "$VERSION" --registry "$REGISTRY" \
  --source-tag "$SOURCE_TAG" --digests "$DIGESTS" --python architect/python/bin/python3

# ── 7. the bundled backend imports ─────────────────────────────────────────────────────────
say "checking that the bundled backend imports"
CHECK_LOG=$(mktemp -t robo-runtime-import)
(cd "$OUT/architect/app" && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -c 'import api.main' >/dev/null 2>"$CHECK_LOG") \
  || { tail -20 "$CHECK_LOG" >&2; die "import api.main failed"; }
rm -f "$CHECK_LOG"
du -sh "$OUT" | awk '{print "[runtime] ready: " $2 " (" $1 ")"}'
