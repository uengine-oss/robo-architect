#!/usr/bin/env bash
# Publish the macOS installer on the public releases repository.
#
#   scripts/release/publish-release.sh [--version 0.1.0] [--draft]
#
# 1. checks the built app: its runtime manifest names the images of this version, pinned to pushed
#    digests, and every image can be pulled anonymously (otherwise first launch fails for everyone)
# 2. creates the public repository uengine-oss/robo-architect-lite-releases if it does not exist and
#    puts releases-README.md there as README.md
# 3. creates release v<version> with Robo-Architect-Lite-mac-arm64.dmg — the fixed name the website links:
#    https://github.com/uengine-oss/robo-architect-lite-releases/releases/latest/download/Robo-Architect-Lite-mac-arm64.dmg
# 4. checks that the link answers
#
# Never replaces an asset of an existing release (no --clobber): bump the version instead.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
VERSION=$(node -p "require('$ROOT/desktop/package.json').version")
DRAFT=""
REPO=uengine-oss/robo-architect-lite-releases
ASSET=Robo-Architect-Lite-mac-arm64.dmg
while [ $# -gt 0 ]; do
  case "$1" in
    --version) VERSION=$2; shift 2 ;;
    --draft) DRAFT=--draft; shift ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done
say() { printf '\033[36m[publish]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[publish]\033[0m %s\n' "$*" >&2; exit 1; }

DMG="$ROOT/desktop/out/dist/$ASSET"
APP="$ROOT/desktop/out/dist/mac-arm64/Robo Architect Lite.app"
[ -f "$DMG" ] || die "no $DMG — build it: scripts/build-packaged-runtime.sh --digests … && (cd desktop && npm run dist:mac)"
[ "$(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "$APP/Contents/Info.plist")" = "$VERSION" ] \
  || die "the built app is not version $VERSION"
codesign --verify --deep --strict "$APP" || die "the built app's signature does not verify"

# ── 1. the packaged manifest ───────────────────────────────────────────────────────────────
python3 - "$APP/Contents/Resources/runtime/runtime-manifest.json" "$VERSION" <<'PY'
import json, sys
m = json.load(open(sys.argv[1]))
version = sys.argv[2]
problems = []
if not m.get("imagePull"):
    problems.append("imagePull is not set")
for key, ref in m["images"].items():
    if not ref.startswith("ghcr.io/uengine-oss/robo-architect-lite-") or not ref.endswith(f":{version}"):
        problems.append(f"{key}: {ref}")
if len(m.get("imageDigests", {})) != len(m["images"]):
    problems.append("not pinned to pushed digests — rebuild the runtime with --digests desktop/out/release/image-digests.json")
if problems:
    raise SystemExit("[publish] the packaged runtime is not a release runtime:\n  " + "\n  ".join(problems))
print(f"[publish] packaged runtime: {len(m['images'])} images of {version}, pinned, "
      f"{sum(m.get('imageSizes', {}).values()) / 1e9:.2f} GB to download")
PY
"$ROOT/scripts/release/check-images-public.sh" --version "$VERSION" >/dev/null \
  || die "not every image is public — run scripts/release/check-images-public.sh for the pages to change"
say "images are public"

# ── 2. the repository ──────────────────────────────────────────────────────────────────────
if ! gh repo view "$REPO" >/dev/null 2>&1; then
  say "creating public repository $REPO"
  gh repo create "$REPO" --public \
    --description "Robo Architect Lite desktop app installers (macOS Apple Silicon)" \
    --homepage "https://www.uengine.org/en/contents/roboarchitect.html"
fi
readme_sha=$(gh api "repos/$REPO/contents/README.md" --jq .sha 2>/dev/null || true)
gh api -X PUT "repos/$REPO/contents/README.md" \
  -f message="README: Robo Architect Lite $VERSION" \
  -f content="$(base64 < "$ROOT/scripts/release/releases-README.md" | tr -d '\n')" \
  ${readme_sha:+-f sha="$readme_sha"} >/dev/null
say "README.md updated"

# ── 3. the release ─────────────────────────────────────────────────────────────────────────
TAG="v$VERSION"
gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1 && die "release $TAG already exists — bump the version"
NOTES=$(mktemp -t robo-release-notes)
cat > "$NOTES" <<EOF
Robo Architect Lite $VERSION for macOS (Apple Silicon).

**Download:** \`$ASSET\` below — open it and drag the app to Applications.

**Requirements:** Docker Desktop (running) and Claude Code (installed and signed in). The first launch
downloads the stack's Docker images, about 1.2 GB (about 5 GB on disk); the home screen shows the progress.

**First launch:** the app is not notarized yet. When macOS says it could not verify the app, open
System Settings › Privacy & Security and click **Open Anyway**.

Images: \`ghcr.io/uengine-oss/robo-architect-lite-*:$VERSION\`.
EOF
gh release create "$TAG" "$DMG" --repo "$REPO" --title "Robo Architect Lite $VERSION" \
  --notes-file "$NOTES" --latest $DRAFT
rm -f "$NOTES"
say "released $TAG"

# ── 4. the link the website uses ───────────────────────────────────────────────────────────
if [ -z "$DRAFT" ]; then
  URL="https://github.com/$REPO/releases/latest/download/$ASSET"
  code=$(curl -s -o /dev/null -L -r 0-0 -w '%{http_code}' "$URL")
  case "$code" in 200|206) say "download link answers: $URL" ;; *) die "download link answered $code: $URL" ;; esac
fi
