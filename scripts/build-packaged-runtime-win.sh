#!/usr/bin/env bash
# Build the Windows x64 release runtime on a Mac — the folder the NSIS installer packs as
# <install dir>\resources\runtime (desktop/electron-builder.win.js) and desktop/src/main/docker-stack.ts
# reads in a packaged app. The cross-built counterpart of build-packaged-runtime.sh: nothing here runs
# the Windows interpreter (build-packaged-runtime.ps1 is the older build on Windows itself).
#
#   scripts/build-packaged-runtime-win.sh [--version 0.1.0] [--python 3.14] [--out <dir>]
#                                         [--registry ghcr.io/uengine-oss] [--source-tag lite-win]
#                                         [--image-tag <version>] [--context desktop-linux]
#                                         [--digests <image-digests-amd64.json>]
#                                         [--no-images | --manifest-only]
#
# What it writes (default --out desktop/out/win/runtime, gitignored; desktop/resources/runtime is the
# macOS runtime and is left alone):
#   runtime-manifest.json   as on macOS, from the local linux/amd64 uengine/*:<source-tag> images read
#                           through docker --context <context>; with --digests pinned to the pushed
#                           digests. --no-images leaves it out (the images are not built yet);
#                           --manifest-only rewrites it, compose.yml and config/ in a built folder.
#   compose.yml, config/*.env   the same files as on macOS
#   architect/python/       the python-build-standalone CPython for x86_64-pc-windows-msvc of the version
#                           and build uv installs on this Mac (python.exe at the top, Lib\, DLLs\), with
#                           the locked dependencies installed as win_amd64 wheels into Lib\site-packages
#   architect/app/          api/ + skills/ + pyproject.toml + uv.lock, and a settings .env with no secrets
# The bytecode is compiled with this Mac's CPython of the same version (the same pyc magic number), and
# `import api.main` is traced here and every module it loads is looked up in the Windows file set.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/packaged-runtime-common.sh"      # say, die, copy_app_snapshot, write_runtime_files
VERSION=$(node -p "require('$ROOT/desktop/package.json').version")
PYTHON_VERSION=""
OUT="$ROOT/desktop/out/win/runtime"
REGISTRY="ghcr.io/uengine-oss"
SOURCE_TAG="lite-win"
IMAGE_TAG=""
CONTEXT="desktop-linux"
DIGESTS=""
MODE=full

while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION=$2; shift 2 ;;
    --python) PYTHON_VERSION=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --registry) REGISTRY=$2; shift 2 ;;
    --source-tag) SOURCE_TAG=$2; shift 2 ;;
    --image-tag) IMAGE_TAG=$2; shift 2 ;;
    --context) CONTEXT=$2; shift 2 ;;
    --digests) DIGESTS=$2; shift 2 ;;
    --no-images) MODE=no-images; shift ;;
    --manifest-only) MODE=manifest-only; shift ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

for tool in uv curl tar rsync shasum python3 node; do
  command -v "$tool" >/dev/null || die "$tool is required"
done
[ "$MODE" = no-images ] || command -v docker >/dev/null || die "docker is required (image IDs are read from the local images)"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac
[ "$OUT" != "/" ] && [ "$(basename "$OUT")" = "runtime" ] || die "--out must be a folder named runtime: $OUT"
mkdir -p "$OUT"
[ "$(cd "$OUT" && pwd -P)" != "$(cd "$ROOT/desktop/resources/runtime" 2>/dev/null && pwd -P)" ] \
  || die "$OUT is the macOS runtime — give the Windows one its own folder"
[ -z "$DIGESTS" ] || [ -f "$DIGESTS" ] || die "no such digests file: $DIGESTS"
case "$DIGESTS" in ""|/*) ;; *) DIGESTS="$PWD/$DIGESTS" ;; esac
PYOUT="$OUT/architect/python"

MANIFEST_ARGS=(--root "$ROOT" --out "$OUT" --version "$VERSION" --registry "$REGISTRY" --source-tag "$SOURCE_TAG"
  --image-tag "${IMAGE_TAG:-$VERSION}" --context "$CONTEXT" --arch amd64 --digests "$DIGESTS"
  --python architect/python/python.exe)

if [ "$MODE" = manifest-only ]; then
  [ -f "$PYOUT/python.exe" ] && [ -f "$OUT/architect/app/api/main.py" ] \
    || die "no Windows runtime in $OUT — build it first (without --manifest-only)"
  write_runtime_files "${MANIFEST_ARGS[@]}"
  exit 0
fi
# the images before the long part: a missing one would only show at step 7
[ "$MODE" = no-images ] || write_runtime_files "${MANIFEST_ARGS[@]}" --check-images \
  || die "the linux/amd64 images are not all there (docker --context $CONTEXT, *:$SOURCE_TAG) — or --no-images now and --manifest-only later"

# the development venv's Python, so the release runs on what the backend is tested with
if [ -z "$PYTHON_VERSION" ]; then
  PYTHON_VERSION=$(sed -n 's/^version_info = \([0-9]*\.[0-9]*\).*/\1/p' "$ROOT/.venv/pyvenv.cfg" 2>/dev/null || true)
  PYTHON_VERSION=${PYTHON_VERSION:-3.14}
fi

say "release $VERSION → $OUT (Windows x64, Python $PYTHON_VERSION, images $REGISTRY/robo-architect-lite-*:${IMAGE_TAG:-$VERSION} from *:$SOURCE_TAG)"
find "$OUT" -mindepth 1 -maxdepth 1 ! -name .gitkeep -exec rm -rf {} + 2>/dev/null || true
mkdir -p "$OUT/config" "$OUT/architect/app"
WORK=$(mktemp -d -t robo-runtime-win)
trap 'rm -rf "$WORK"' EXIT

# ── 1. this Mac's CPython: the version to match, the bytecode compiler, the import trace ───────
uv python install "$PYTHON_VERSION" >/dev/null
# --no-project and a neutral cwd: inside the repo uv would answer with the project's .venv
MACPY=$(cd / && uv python find --managed-python --no-project "$PYTHON_VERSION")
PYFULL=$("$MACPY" -c 'import platform; print(platform.python_version())')

# ── 2. the Windows CPython: the same version from the same python-build-standalone release ─────
KEY="cpython-$PYFULL-windows-x86_64-none"
URL=$(cd / && uv python list --all-platforms --only-downloads --output-format json \
  | python3 -c 'import json, sys; print(next((e["url"] for e in json.load(sys.stdin) if e["key"] == sys.argv[1]), ""))' "$KEY")
case "$URL" in *-install_only_stripped.tar.gz|*-install_only.tar.gz) ;; *) die "uv lists no install_only download for $KEY: '$URL'" ;; esac
NAME=$(basename "$URL" | sed 's/%2B/+/g')
CACHE="$ROOT/desktop/out/win/cache"
mkdir -p "$CACHE"
if [ ! -f "$CACHE/$NAME" ]; then
  say "downloading $NAME"
  curl -fsSL -o "$CACHE/$NAME.part" "$URL" && mv "$CACHE/$NAME.part" "$CACHE/$NAME"
fi
# the release's own checksum list (uv checks the same digests when it installs one)
curl -fsSL -o "$WORK/SHA256SUMS" "$(dirname "$URL")/SHA256SUMS"
WANT=$(awk -v n="$NAME" '$2 == n { print $1 }' "$WORK/SHA256SUMS")
GOT=$(shasum -a 256 "$CACHE/$NAME" | awk '{ print $1 }')
[ -n "$WANT" ] && [ "$WANT" = "$GOT" ] || { rm -f "$CACHE/$NAME"; die "$NAME: sha256 $GOT, the release lists '${WANT}'"; }
say "Python $PYFULL for Windows from $NAME"
tar -xzf "$CACHE/$NAME" -C "$WORK"
[ -f "$WORK/python/python.exe" ] && [ -d "$WORK/python/Lib" ] || die "$NAME is not laid out as python/python.exe + Lib/"
mv "$WORK/python" "$PYOUT"
# the bytecode compiled on this Mac must be what the Windows interpreter reads: the build ships pyc
"$MACPY" -I - "$PYOUT" <<'PY' || die "the Windows interpreter reads other bytecode than this Mac's"
import glob, importlib.util, sys
tag = f"cpython-{sys.version_info[0]}{sys.version_info[1]}"
seen = {open(p, "rb").read(4) for p in glob.glob(f"{sys.argv[1]}/Lib/__pycache__/*.{tag}.pyc")}
if not seen:
    print(f"[runtime] the Windows build ships no {tag} pyc to compare — trusting the equal version")
elif seen != {importlib.util.MAGIC_NUMBER}:
    raise SystemExit(f"[runtime] pyc magic: Windows {sorted(seen)}, this Mac {importlib.util.MAGIC_NUMBER}")
PY

# ── 3. locked dependencies, win_amd64 wheels only ──────────────────────────────────────────
say "installing the locked dependencies (x86_64-pc-windows-msvc, Python $PYFULL)"
(cd "$ROOT" && uv export --locked --no-dev --no-emit-project --no-header --format requirements-txt \
  --output-file "$OUT/architect/requirements.lock.txt" >/dev/null)
# a package without a wheel for this platform fails here, named — it is never built or left out
(cd "$ROOT" && uv pip install --quiet --python "$MACPY" --target "$PYOUT/Lib/site-packages" \
  --python-platform x86_64-pc-windows-msvc --python-version "$PYFULL" --only-binary :all: \
  --requirements "$OUT/architect/requirements.lock.txt" --require-hashes --link-mode copy --strict)

# ── 4. application snapshot ────────────────────────────────────────────────────────────────
say "copying api/ and skills/"
copy_app_snapshot "$ROOT" "$OUT/architect/app"

# ── 5. trim what a server never runs ───────────────────────────────────────────────────────
rm -rf "$PYOUT/include" "$PYOUT/libs" "$PYOUT/tcl" "$PYOUT/Scripts" \
  "$PYOUT/Lib/idlelib" "$PYOUT/Lib/turtledemo" "$PYOUT/Lib/tkinter" "$PYOUT/Lib/test" "$PYOUT/Lib/ensurepip" \
  "$PYOUT"/DLLs/_tkinter* "$PYOUT"/DLLs/tcl* "$PYOUT"/DLLs/tk* \
  "$PYOUT/Lib/site-packages/include"
# --target writes console scripts for this Mac's interpreter (bin/, shebangs) — the app runs `python -m`
rm -rf "$PYOUT/Lib/site-packages/bin"
find "$OUT/architect" -name '__pycache__' -type d -prune -exec rm -rf {} +

# ── 6. bytecode: the bundle is read-only to the app (PYTHONDONTWRITEBYTECODE in a packaged app) ─
say "compiling bytecode (this Mac's Python $PYFULL)"
"$MACPY" -I -W ignore::SyntaxWarning -m compileall -q -j 0 --invalidation-mode unchecked-hash "$PYOUT/Lib" >/dev/null || true
"$MACPY" -I -m compileall -q -j 0 --invalidation-mode checked-hash "$OUT/architect/app/api" >/dev/null

# ── 7. compose, service settings, the backend's settings file, manifest ────────────────────
if [ "$MODE" = no-images ]; then
  write_runtime_files "${MANIFEST_ARGS[@]}" --no-images
else
  write_runtime_files "${MANIFEST_ARGS[@]}"
fi

# ── 8. the bundled backend's imports, traced on this Mac ───────────────────────────────────
# The Windows interpreter cannot run here: `import api.main` runs in a macOS venv of the same locked
# dependencies, and every module it loads must exist in the Windows set (a .pyd for each extension).
# What Windows lacks — the stdlib's POSIX side, packages locked for macOS only — may be imported by
# the stdlib itself, or by the application and its dependencies only under an if or a try.
say "tracing the backend's imports against the Windows files"
(cd / && uv venv --quiet --python "$MACPY" "$WORK/venv" \
  && uv pip install --quiet --python "$WORK/venv/bin/python" --requirements "$OUT/architect/requirements.lock.txt" \
       --require-hashes --strict)
(cd "$OUT/architect/app" && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  "$WORK/venv/bin/python" -I -W ignore - "$PYOUT" <<'PY') || die "the backend imports something Windows does not have"
import ast, os, sys

win, app = os.path.realpath(sys.argv[1]), os.path.realpath(os.getcwd())
first = {}                                        # module → the module whose import loaded it


class Recorder:
    @staticmethod
    def find_spec(name, path=None, target=None):
        if name not in first:
            f = sys._getframe(1)
            while f is not None and f.f_globals.get("__name__", "").startswith(("importlib", "_frozen_importlib")):
                f = f.f_back
            first[name] = f.f_globals.get("__name__") if f is not None else None
        return None


sys.meta_path.insert(0, Recorder)
sys.path.insert(0, app)
import api.main  # noqa: E402,F401
sys.meta_path.remove(Recorder)

V = f"{sys.version_info[0]}{sys.version_info[1]}"
stdlib = os.path.realpath(os.path.join(sys.base_prefix, "lib", f"python{sys.version_info[0]}.{sys.version_info[1]}"))
site = sorted({os.path.realpath(p) for p in sys.path if p.endswith("site-packages")})
win_site = os.path.join(win, "Lib", "site-packages")
POSIX_ONLY = {"posix", "pwd", "grp", "termios", "tty", "pty", "fcntl", "resource", "syslog", "_posixsubprocess",
              "_posixshmem", "readline", "curses", "_curses", "_curses_panel", "_scproxy", "_dbm", "_gdbm"}


def where(origin):
    """(kind, the Windows counterpart or None) of a module file loaded on this Mac"""
    o = os.path.realpath(origin)
    if o.startswith(app + os.sep):
        return "app", o
    for base, dest, kind in [(s, win_site, "dependency") for s in site] + [(stdlib, os.path.join(win, "Lib"), "stdlib")]:
        if not o.startswith(base + os.sep):
            continue
        rel = os.path.relpath(o, base)
        if rel.endswith(".so"):                   # x.cpython-314-darwin.so → x.pyd / x.cp314-win_amd64.pyd
            folder = os.path.join(win, "DLLs") if rel.startswith("lib-dynload" + os.sep) else os.path.join(dest, os.path.dirname(rel))
            stem = os.path.basename(rel).split(".")[0]
            hits = [c for c in (f"{stem}.pyd", f"{stem}.cp{V}-win_amd64.pyd") if os.path.exists(os.path.join(folder, c))]
            return kind + " extension", (os.path.join(folder, hits[0]) if hits else None)
        p = os.path.join(dest, rel)
        return kind, (p if os.path.exists(p) else None)
    return "elsewhere", None


# 1. every module the import loaded, looked up in the Windows set
counts, absent, sources = {}, set(), []
for name, mod in sorted(sys.modules.items()):
    origin = getattr(getattr(mod, "__spec__", None), "origin", None)
    if not origin or not os.path.isabs(origin):   # built-in, frozen, namespace
        counts["built-in"] = counts.get("built-in", 0) + 1
        if name.split(".")[0] in POSIX_ONLY:
            absent.add(name)
        continue
    kind, found = where(origin)
    counts[kind] = counts.get(kind, 0) + 1
    if (found is None or name.split(".")[0] in POSIX_ONLY) and not name.startswith("_virtualenv"):
        absent.add(name)                          # (_virtualenv: uv's venv hook, not in the bundle)
    if kind in ("app", "dependency") and origin.endswith(".py"):
        sources.append((name, origin))

# 2. who imports what Windows lacks: POSIX-only modules, packages locked for macOS only, the absent ones
mac_only = set()
for s in site:
    for entry in os.listdir(s):
        top = entry.split(".")[0]
        if entry.endswith((".dist-info", ".pth")) or top.startswith(("_virtualenv", "__")):
            continue
        if not any(e.split(".")[0] == top for e in os.listdir(win_site)):
            mac_only.add(top)
tops, exact = POSIX_ONLY | mac_only, absent


def wanted(n):
    return n.split(".")[0] in tops or any(n == t or n.startswith(t + ".") for t in exact)


def guard(node, parents):
    child, p = node, parents.get(node)
    while p is not None:
        if isinstance(p, ast.If):
            return "if"
        if isinstance(p, ast.Try) and child in p.body and any(
                h.type is None or {getattr(e, "id", "") for e in getattr(h.type, "elts", [h.type])}
                & {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"} for h in p.handlers):
            return "try"
        child, p = p, parents.get(p)
    return "unguarded"


found_by = {}
bad = []
for name, origin in sources:
    tree = ast.parse(open(origin, encoding="utf-8").read())
    parents = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}
    for node in ast.walk(tree):
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and node.level == 0 else []
        for n in filter(wanted, names):
            how = guard(node, parents)
            found_by.setdefault(n, []).append(f"{name}:{node.lineno} {how}")
            if how == "unguarded":
                bad.append(f"{name}:{node.lineno} imports {n}")
for n in sorted(absent - set(found_by)):
    importer = first.get(n)
    ifile = os.path.realpath(getattr(sys.modules.get(importer), "__file__", None) or "")
    if importer is not None and not (ifile.startswith(stdlib + os.sep) and "site-packages" not in ifile):
        bad.append(f"{n} is loaded by {importer} without an import statement to check")
    else:
        found_by[n] = [f"stdlib ({importer or 'startup'})"]
for n in sorted(found_by):
    print(f"     {n:30} ← {', '.join(found_by[n])}")
print("[runtime] " + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + " modules; Windows lacks "
      + f"{len(absent)} of them and {', '.join(sorted(mac_only)) or 'no package'} (macOS only)")
for b in bad:
    print(f"[runtime] !! {b}")
sys.exit(1 if bad else 0)
PY
du -sh "$OUT" | awk '{print "[runtime] ready: " $2 " (" $1 ")"}'
[ "$MODE" = full ] || say "finish once the images are pushed: scripts/build-packaged-runtime-win.sh --manifest-only --digests desktop/out/release/image-digests-amd64.json"
