# macOS release (Apple Silicon)

The installer is a DMG on the public repository `uengine-oss/robo-architect-lite-releases`, always
under the same asset name, so the website can link
`https://github.com/uengine-oss/robo-architect-lite-releases/releases/latest/download/Robo-Architect-Lite-mac-arm64.dmg`.
The app ships without Docker images: on first launch it pulls the seven stack images from the public
GitHub Container Registry (`ghcr.io/uengine-oss/robo-architect-lite-<component>:<version>`, about
1.1 GB) and shows the progress on the home screen (`desktop/src/main/docker-images.ts`). Images that
are already on the machine with the recorded ID are reused (tagged), not downloaded.

## Steps (version = `desktop/package.json`)

```bash
# 0. the images are final (uengine/*:lite-mac, robo-lite-src/build/build-images.sh) and the front end
#    is built with the analyzer remote (robo-lite-src/build/build-frontend.sh → frontend/dist)

# 1. push the seven images, record their digests and sizes, make the packages public
#    (once before: gh auth refresh -h github.com -s write:packages,read:packages)
scripts/release/push-images.sh            # --dry-run shows what it would do
scripts/release/check-images-public.sh    # after switching any package to Public by hand

# 2. the runtime folder the app packs, pinned to the pushed digests
scripts/build-packaged-runtime.sh --digests desktop/out/release/image-digests.json

# 3. the DMG (ad-hoc signed) → desktop/out/dist/Robo-Architect-Lite-mac-arm64.dmg
(cd desktop && env -u ELECTRON_RUN_AS_NODE npm run dist:mac)

# 4. the releases repository (created public if missing, README from releases-README.md) + release v<version>
scripts/release/publish-release.sh        # --draft to look before it becomes Latest
```

## Checking a build without disturbing a running stack

A fresh data folder means new ports and a new database password; under the usual Compose project
name that would recreate the running containers. Give the test its own project:

```bash
env -i HOME="$HOME" USER="$USER" SHELL="$SHELL" PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  ROBO_COMPOSE_PROJECT=ra-pkgtest \
  "<copy>/Robo Architect Lite.app/Contents/MacOS/Robo Architect Lite" --user-data-dir=<empty folder>
# … <folder>/logs/desktop.log reaches backend.status ready; then quit the app and
docker compose -p ra-pkgtest down -v
```

The bare `PATH` is what Finder gives an app; the app adds the login shell's PATH and the usual
install places to find `docker` and `claude` (`desktop/src/main/host-path.ts`).

Pull path tests: `cd desktop && npx playwright test tests/unit/docker-images.spec.ts` (no Docker) and
`node scripts/test-image-pull.mjs` (a throwaway local registry and image).
