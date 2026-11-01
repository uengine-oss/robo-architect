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

# Windows x64 (NSIS installer, cross-built on the Mac)

The same app with a Windows runtime: python-build-standalone CPython for `x86_64-pc-windows-msvc` of
the macOS runtime's version, the locked dependencies as `win_amd64` wheels, the same compose and
settings, and the linux/amd64 builds of the seven images. Nothing runs under wine; the bundled
backend's imports are traced on the Mac against the Windows file set instead of being run.
`desktop/resources/runtime` stays the macOS runtime — the Windows one is `desktop/out/win/runtime`, and
`desktop/electron-builder.win.js` packs it in place of the macOS one.

```bash
# 0. the linux/amd64 images uengine/*:lite-win (robo-lite-src/build/build-images-amd64.sh)

# 1. the runtime — without the images yet: --no-images now, --manifest-only once they are there
scripts/build-packaged-runtime-win.sh [--no-images]

# 2. push the amd64 images and record desktop/out/release/image-digests-amd64.json (same format as
#    image-digests.json), then pin the manifest to them (--image-tag if they are not :<version>)
scripts/build-packaged-runtime-win.sh --manifest-only --digests desktop/out/release/image-digests-amd64.json

# 3. the installer → desktop/out/dist/Robo-Architect-Lite-Setup-win-x64.exe (unsigned)
(cd desktop && env -u ELECTRON_RUN_AS_NODE npm run dist:win)
```
