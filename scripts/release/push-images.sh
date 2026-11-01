#!/usr/bin/env bash
# Push the seven stack images to the public GitHub Container Registry and record what was pushed.
#
#   scripts/release/push-images.sh [--version 0.1.0] [--arch arm64|amd64] [--source-tag lite-mac] [--dry-run]
#
#   uengine/<image>:lite-mac  →  ghcr.io/uengine-oss/robo-architect-lite-<component>:<version>
#   --arch amd64 (Windows):  uengine/<image>:lite-win  →  …:<version>-amd64, desktop/out/release/image-digests-amd64.json
#   (a tag of its own, so :<version> stays the arm64 image the macOS release pinned)
#
# Writes desktop/out/release/image-digests.json ({key: {ref, id, digest, size}}), which
# scripts/build-packaged-runtime.sh --digests reads: the release manifest then pins every pull to
# the pushed digest and knows each image's download size. Then asks GitHub to make each package
# public and checks that an anonymous client can pull every image — the app pulls without login.
#
# Needs: a gh login with the write:packages scope (once: gh auth refresh -h github.com -s write:packages,read:packages).
# Run it only when the images are final: the app verifies the image IDs the runtime recorded.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
VERSION=$(node -p "require('$ROOT/desktop/package.json').version")
SOURCE_TAG=
ARCH=arm64
ORG=uengine-oss
DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION=$2; shift 2 ;;
    --source-tag) SOURCE_TAG=$2; shift 2 ;;
    --arch) ARCH=$2; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
case "$ARCH" in
  arm64) SOURCE_TAG=${SOURCE_TAG:-lite-mac}; TAG_SUFFIX=""; DIGESTS_NAME=image-digests.json ;;
  amd64) SOURCE_TAG=${SOURCE_TAG:-lite-win}; TAG_SUFFIX="-amd64"; DIGESTS_NAME=image-digests-amd64.json ;;
  *) echo "--arch is arm64 or amd64" >&2; exit 2 ;;
esac
say() { printf '\033[36m[push]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[push]\033[0m %s\n' "$*" >&2; exit 1; }
run() { if [ "$DRY" = 1 ]; then echo "  (dry-run) $*"; else "$@"; fi; }

# manifest key | local image | release component (the compose service name)
IMAGES="graphDb|uengine/ontological-db|graph-db
graphBolt|uengine/ontological-bolt|graph-bolt
analyzer|uengine/robo-analyzer|analyzer
catalog|uengine/robo-data-catalog|catalog
fabric|uengine/robo-data-fabric|fabric
parser|uengine/robo-antlr-parser|parser
gateway|uengine/robo-api-gateway|gateway"

OUT_DIR="$ROOT/desktop/out/release"
OUT="$OUT_DIR/$DIGESTS_NAME"
mkdir -p "$OUT_DIR"

# ── preflight: every local image is there and arm64 ────────────────────────────────────────
while IFS='|' read -r key local component; do
  arch=$(docker image inspect "$local:$SOURCE_TAG" --format '{{.Architecture}}' 2>/dev/null) \
    || die "missing local image $local:$SOURCE_TAG"
  [ "$arch" = "$ARCH" ] || die "$local:$SOURCE_TAG is $arch, not $ARCH"
done <<< "$IMAGES"

# ── login (the gh token, never printed) ────────────────────────────────────────────────────
if [ "$DRY" = 0 ]; then
  scopes=$(gh auth status 2>&1 | sed -n 's/.*Token scopes: //p')
  case "$scopes" in *write:packages*) ;; *)
    die "the gh token lacks write:packages — run once: gh auth refresh -h github.com -s write:packages,read:packages" ;;
  esac
  gh auth token | docker login ghcr.io -u "$(gh api user --jq .login)" --password-stdin >/dev/null
  say "logged in to ghcr.io"
fi

# ── tag, push, record ──────────────────────────────────────────────────────────────────────
echo "{" > "$OUT.tmp"
first=1
while IFS='|' read -r key local component; do
  ref="ghcr.io/$ORG/robo-architect-lite-$component:$VERSION$TAG_SUFFIX"
  id=$(docker image inspect "$local:$SOURCE_TAG" --format '{{.Id}}')
  say "$local:$SOURCE_TAG → $ref"
  run docker image tag "$local:$SOURCE_TAG" "$ref"
  if [ "$DRY" = 1 ]; then
    digest=$id
  else
    pushed=$(docker push "$ref" 2>&1 | tee /dev/stderr | tail -5)
    digest=$(printf '%s\n' "$pushed" | sed -n 's/.*digest: \(sha256:[a-f0-9]\{64\}\).*/\1/p' | tail -1)
    [ -n "$digest" ] || digest=$(docker buildx imagetools inspect "$ref" --format '{{json .Manifest}}' \
      | python3 -c 'import json,sys; print(json.load(sys.stdin)["digest"])')
  fi
  # download size = config + layers of the $ARCH manifest in the registry (local content size as a fallback)
  size=$(python3 - "$ref" "$DRY" "$ARCH" <<'PY' || docker image inspect "$local:$SOURCE_TAG" --format '{{.Size}}'
import json, subprocess, sys
ref, dry, arch = sys.argv[1], sys.argv[2] == "1", sys.argv[3]
if dry:
    raise SystemExit(1)
raw = lambda r: json.loads(subprocess.check_output(["docker", "buildx", "imagetools", "inspect", "--raw", r]))
top = raw(ref)
repo = ref.rsplit(":", 1)[0]
if "manifests" in top:
    m = next(m for m in top["manifests"] if m.get("platform", {}).get("architecture") == arch
             and m.get("platform", {}).get("os") == "linux")
    top = raw(f"{repo}@{m['digest']}")
print(top["config"]["size"] + sum(l["size"] for l in top["layers"]))
PY
)
  [ $first = 1 ] || echo "," >> "$OUT.tmp"
  first=0
  printf '  "%s": {"ref": "%s", "id": "%s", "digest": "%s", "size": %s}' "$key" "$ref" "$id" "$digest" "$size" >> "$OUT.tmp"
  say "  digest ${digest:0:19}…  $((size / 1000000)) MB"
done <<< "$IMAGES"
printf '\n}\n' >> "$OUT.tmp"
if [ "$DRY" = 1 ]; then cat "$OUT.tmp"; rm -f "$OUT.tmp"; exit 0; fi
mv "$OUT.tmp" "$OUT"
say "recorded $OUT"

# ── public: GitHub has no documented API for package visibility — try it, then check what an
#    anonymous client sees (check-images-public.sh lists the settings pages still to click) ──────
while IFS='|' read -r key local component; do
  gh api -X PATCH "/orgs/$ORG/packages/container/robo-architect-lite-$component" -f visibility=public \
    >/dev/null 2>&1 || true
done <<< "$IMAGES"
"$ROOT/scripts/release/check-images-public.sh" --version "$VERSION$TAG_SUFFIX"
say "all seven images are pushed and public"
