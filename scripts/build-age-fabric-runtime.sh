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
# Images (key=ref; --image replaces one). Build the two that are not on this machine yet:
#   graphDb    uengine/supabase-postgres-age:15.8.1.060-age1.8.0   (age-supabase/build.sh)
#   graphBolt  uengine/ontological-bolt:age                        (age-supabase/gateway/build.sh)
#   fabric     ogfab-service:stage4                                (og-fabric stage4: docker build -t ogfab-service:stage4 service/)
#   fabricDb   ogfab-db:stage4                                     (og-fabric stage4: image/build-local.sh; bake it from the same commit as the service)
#   catalog    uengine/robo-data-catalog:age-fabric                (from the submodule BRANCH, not the pin:
#              git -C robo-analyzer/robo-data-catalog archive feat/age-fabric | docker build -t uengine/robo-data-catalog:age-fabric -)
#              The superproject keeps the catalog pin at 1f1aaa6 so the default configuration does not change.
#   analyzer · parser · gateway  uengine/robo-analyzer · robo-antlr-parser · robo-api-gateway :lite-mac
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
  --python architect/python/bin/python3 --no-images >/dev/null
rm -f "$OUT/compose.yml"
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
images = {
    "graphDb":   "uengine/supabase-postgres-age:15.8.1.060-age1.8.0",
    "graphBolt": "uengine/ontological-bolt:age",
    "analyzer":  "uengine/robo-analyzer:lite-mac",
    "catalog":   "uengine/robo-data-catalog:age-fabric",
    "fabric":    "ogfab-service:stage4",
    "fabricDb":  "ogfab-db:stage4",
    "parser":    "uengine/robo-antlr-parser:lite-mac",
    "gateway":   "uengine/robo-api-gateway:lite-mac",
}
for o in overrides:
    key, _, ref = o.partition("=")
    if key not in images or not ref:
        raise SystemExit(f"[runtime] --image {o}: key=ref with key one of {', '.join(images)}")
    images[key] = ref

# og-fabric's settings (FABRIC-PROGRESS.md §9 #2). The DSNs, the service token and the channel token
# are not here: compose.age-fabric.yml builds them from what the app passes at start.
(out / "config" / "fabric.env").write_text("""OG_FABRIC_LOCALHOST_AS=host.docker.internal
OG_FABRIC_INLINE_PASSWORDS=refuse
OG_FABRIC_QUERY_TIMEOUT_MS=30000
OG_FABRIC_QUERY_TIMEOUT_MS_MAX=300000
OG_FABRIC_ADMIN_TIMEOUT_MS=120000
OG_FABRIC_INTERNAL_LOOPBACK_ONLY=0
""", encoding="utf-8")
shutil.copyfile(root / "desktop" / "runtime" / "compose.age-fabric.yml", out / "compose.age-fabric.yml")


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
    "schemaVersion": 3,
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
