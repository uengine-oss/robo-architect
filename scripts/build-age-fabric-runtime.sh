#!/usr/bin/env bash
# A runtime folder for the age-fabric configuration (Apache AGE + og-fabric), from local images —
# what desktop/src/main/docker-stack.ts reads (ROBO_DOCKER_RUNTIME_DIR, or <app>/Contents/Resources/runtime).
# The default configuration's folder is still made by build-packaged-runtime.sh; this changes nothing there.
#
#   scripts/build-age-fabric-runtime.sh --out <dir>/runtime [--version 0.1.1] [--image key=ref ...]
#                                       [--venv <virtualenv>] [--link-app]
#
# What it writes
#   compose.age-fabric.yml  desktop/runtime/compose.age-fabric.yml
#   config/*.env            analyzer · catalog · parser · gateway: the release's (packaged-runtime-common.sh),
#                           fabric: og-fabric's settings (no secrets: those come from the app at start)
#   architect/app/.env      the release's
#   --venv / --link-app     for a development start of the app on this folder (the Architect API runs from it):
#                           architect/python → the virtualenv (with the backend's packages), architect/app/{api,
#                           skills,pyproject.toml,uv.lock} → this checkout. A release copies them instead
#                           (build-packaged-runtime.sh).
#   runtime-manifest.json   deployVariant age-fabric, the local images by reference and ID, no pull
#
# Images: scripts/age-fabric-images.txt (key=ref with --image replaces one) — how each is built is there.
# analyzer · parser · gateway · wireframe are the regular release's images: pull them first
#   (docker pull ghcr.io/uengine-oss/robo-architect-lite-<component>:0.1.4).
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
. "$ROOT/scripts/packaged-runtime-common.sh"      # say, die, write_runtime_files
VERSION=$(node -p "require('$ROOT/desktop/package.json').version")
OUT=""
VENV=""
LINK_APP=0
IMAGES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT=$2; shift 2 ;;
    --version) VERSION=$2; shift 2 ;;
    --venv) VENV=$2; shift 2 ;;
    --link-app) LINK_APP=1; shift ;;
    --image) IMAGES+=("$2"); shift 2 ;;
    -h|--help) sed -n '2,29p' "$0"; exit 0 ;;
    *) die "unknown option: $1" ;;
  esac
done
[ -n "$OUT" ] || die "give --out <dir>/runtime"
case "$OUT" in /*) ;; *) OUT="$PWD/$OUT" ;; esac
[ "$(basename "$OUT")" = "runtime" ] || die "--out must be a folder named runtime: $OUT"
command -v docker >/dev/null || die "docker is required (image IDs are read from the local images)"

mkdir -p "$OUT/config" "$OUT/architect/app"
# the release's service settings and the backend's settings file, no manifest (images differ here)
write_runtime_files --root "$ROOT" --out "$OUT" --version "$VERSION" --registry local --source-tag none \
  --python architect/python/bin/python3 --no-images --variant age-fabric >/dev/null
if [ -n "$VENV" ]; then
  [ -x "$VENV/bin/python3" ] || die "--venv $VENV has no bin/python3"
  rm -rf "$OUT/architect/python"
  ln -s "$(cd "$VENV" && pwd)" "$OUT/architect/python"   # the folder, so the venv's pyvenv.cfg is found
fi
if [ "$LINK_APP" = 1 ]; then
  for f in api skills pyproject.toml uv.lock; do ln -sfn "$ROOT/$f" "$OUT/architect/app/$f"; done
fi

python3 - "$ROOT" "$OUT" "$VERSION" "${IMAGES[@]+"${IMAGES[@]}"}" <<'PY'
import hashlib, json, shutil, subprocess, sys
from pathlib import Path

root, out, version, overrides = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4:]
images = {}
for line in (root / "scripts" / "age-fabric-images.txt").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#"):
        key, ref, _ = line.split("|")
        images[key] = ref
for o in overrides:
    key, _, ref = o.partition("=")
    if key not in images or not ref:
        raise SystemExit(f"[runtime] --image {o}: key=ref with key one of {', '.join(images)}")
    images[key] = ref

# compose.age-fabric.yml and og-fabric's settings (config/fabric.env) came from write_runtime_files above

def image_id(ref: str) -> str:
    try:
        return subprocess.check_output(["docker", "image", "inspect", ref, "--format", "{{.Id}}"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        raise SystemExit(f"[runtime] the local image {ref} is missing — build it first (see the header)")


def head(path: Path, ref: str = "HEAD") -> str:
    try:
        return subprocess.check_output(["git", "-C", str(path), "rev-parse", ref], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "0" * 40


sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
env = {k: {"file": f"config/{k}.env", "sha256": sha(out / "config" / f"{k}.env")}
       for k in ("analyzer", "catalog", "fabric", "parser", "gateway")}
env["architect"] = {"file": "architect/app/.env", "sha256": sha(out / "architect" / "app" / ".env")}
og_fabric = Path("/Users/uengine/og-fabric")
age_main = Path("/Users/uengine/worktrees/age-main")
manifest = {
    "schemaVersion": 4,  # MANIFEST_SCHEMA_VERSION in desktop/src/main/docker-stack.ts
    "deployVariant": "age-fabric",
    "releaseId": f"lite-{version}-age-fabric",
    "releaseChannel": "local",
    "releaseVariant": "lite",
    "authEnforced": False,
    "authProvider": "none",
    "credentialNames": ["OPENAI_API_KEY", "LLM_API_KEY", "ROBO_LLM_API_KEY", "ROBO_EMBED_API_KEY",
                        "ROBO_SEARCH_LLM_API_KEY"],
    "composeFile": "compose.age-fabric.yml",
    "imagePull": False,
    "images": images,
    "imageIds": {k: image_id(v) for k, v in images.items()},
    "architect": {"python": "architect/python/bin/python3", "app": "architect/app", "entrypoint": "api.main:app"},
    "environment": env,
    "source": {
        "workspace": "0" * 40,
        "ontological": head(age_main),           # the Bolt gateway's AGE backend (ontological-fabric age/main)
        "architect": head(root),
        "openPencil": head(root / "open-pencil"),
        "analyzer": head(root / "robo-analyzer/robo-data-analyzer"),
        "catalog": head(root / "robo-analyzer/robo-data-catalog", "feat/age-fabric"),  # image is built from this branch
        "fabric": head(og_fabric),               # og-fabric, not robo-data-fabric
        "frontend": head(root / "robo-analyzer/robo-data-frontend"),
        "parser": "0" * 40,
        "gateway": "0" * 40,
    },
}
(out / "runtime-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(f"[runtime] age-fabric runtime: {out}")
for k, v in images.items():
    print(f"  {k:10} {v}  {manifest['imageIds'][k][:19]}")
PY
