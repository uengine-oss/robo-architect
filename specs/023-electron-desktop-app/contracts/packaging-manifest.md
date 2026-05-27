# Contract: Packaging, Signing & Update Feed

**Feature**: `023-electron-desktop-app` | **Date**: 2026-05-11

Defines the **build inputs → artifacts → distribution** contract. This is what `electron-builder` is configured to consume/produce and what `electron-updater` reads at runtime. It is a contract in the sense that CI, the signing step, and the update server must all agree on these shapes.

---

## Build inputs (assembled by `desktop/scripts/*` before `electron-builder` runs)

| Input | Produced by | Notes |
|-------|-------------|-------|
| `frontend/dist/**` | `npm --prefix frontend ci && npm --prefix frontend run build`, then `desktop/scripts/build-frontend.*` copies it into the asar payload | The renderer is served from this via the `app://` protocol (research D4). Requires the one minimal `frontend/` change: read the injected backend base URL instead of assuming a same-origin `/api`. |
| `desktop/resources/python/<os-arch>/**` | `desktop/scripts/bundle-backend.*` — a relocatable CPython 3.11 (`python-build-standalone`) into which `uv` installs deps from the repo's `pyproject.toml` + `uv.lock`, plus a copy of the `api/` source tree | Per target (`win-x64`, `mac-arm64`, `mac-x64`). The backend is launched as `python -m uvicorn api.main:app` (research D3). `api/` source is unmodified. |
| `desktop/resources/neo4j/<os-arch>/**` | `desktop/scripts/bundle-neo4j.*` — Neo4j Community 5.x + a minimal JRE | **Present only in the "bundled DB" build variant** (research D2 ⚠). The "download-on-first-run" variant ships a small shim instead and fetches Neo4j into the user's data dir on first launch. `electron-builder` config selects the variant via a build flag. |
| `desktop/resources/icons/**` | committed | `.ico` (Windows), `.icns` (macOS), plus PNGs. |
| `desktop/src/main`, `desktop/src/preload` (compiled JS), `desktop/src/shared` | `tsc` | The Electron main/preload bundles. |

The asar payload = compiled `main`/`preload` + `frontend/dist`. The `resources/python` and `resources/neo4j` trees are shipped **unpacked** (`asarUnpack`) because they contain native executables/JARs that must run from disk.

---

## Artifacts produced (per release, per OS)

| Platform | Artifact(s) | Installer type | Signed with |
|----------|-------------|----------------|-------------|
| Windows x64 | `Robo-Architect-Setup-<version>.exe` | NSIS (per-user install by default; no admin needed) | Authenticode (EV or OV code-signing cert) |
| macOS arm64 | `Robo-Architect-<version>-arm64.dmg` **and** `Robo-Architect-<version>-arm64-mac.zip` | drag-to-Applications dmg; the `.zip` is what `electron-updater` consumes for in-place update | Apple Developer ID Application cert, **notarized + stapled** |
| macOS x64 | `Robo-Architect-<version>-x64.dmg` **and** `...-x64-mac.zip` | same | same |

(A universal macOS build is acceptable in lieu of separate arm64/x64 if preferred — the contract only requires that Apple Silicon and Intel Macs both get a working, notarized artifact.)

**Signing requirement (FR-019)**: on a default-trust machine, running the installer must **not** show a SmartScreen "unrecognized app" / Gatekeeper "unidentified developer" prompt. Windows ⇒ valid Authenticode signature (reputation builds over time with OV; immediate with EV). macOS ⇒ Developer ID signature **plus successful notarization with the ticket stapled** — signing alone is not sufficient on macOS 13+.

---

## Update feed (consumed by `electron-updater` at runtime)

Hosted at a stable HTTPS "known location" (the Q3=A direct-download channel — e.g. a versioned bucket/site). Layout per channel (`latest`, optionally `beta`):

```
<feed-root>/
├── latest.yml                       # Windows feed metadata (version, files, sha512)
├── latest-mac.yml                   # macOS feed metadata
├── Robo-Architect-Setup-<v>.exe
├── Robo-Architect-<v>-arm64-mac.zip
├── Robo-Architect-<v>-x64-mac.zip
└── ... (current + at least the previous release retained)
```

Contract guarantees:
- `latest*.yml` lists each file with a **sha512** that `electron-updater` verifies after download; a mismatch ⇒ the update is rejected and the running version stays intact (FR-015).
- The downloaded artifact's **code signature** is verified before it is applied (Authenticode on Windows; the signed/notarized `.zip` on macOS).
- Downloads are resumable and staged in a temp area; an interrupted download never mutates the installed app — next launch simply re-checks (FR-015).
- Publishing a release = upload the artifacts + regenerate `latest*.yml` atomically (write new, then swap) so a client never sees a `.yml` pointing at a not-yet-uploaded file.
- Rollback = re-point `latest*.yml` at the prior version's files (the prior artifacts are retained).

**Out of scope (Q3=A)**: Microsoft Store / Mac App Store distribution and their update mechanisms. Differential/delta updates are optional and not required for v1 (the feed format already supports adding them later).

---

## CI obligations (new "desktop" job; existing jobs untouched)

1. Run `desktop/scripts/build-frontend.*`, `bundle-backend.*`, and (for the bundled-DB variant) `bundle-neo4j.*`.
2. `tsc` the Electron sources; run `desktop/tests/smoke.spec.ts` (Playwright-for-Electron: launches the packaged app on the CI OS, asserts single-instance, backend reaches `ready`, window loads the SPA, clean quit leaves 0 child processes).
3. `electron-builder` for the CI's OS target; on a tagged release, sign + (macOS) notarize using secrets from the CI vault, then publish artifacts + `latest*.yml` to the feed.
4. Signing secrets (certs, Apple API key, feed credentials) live only in the CI secret store — never in the repo, never in the shipped app (consistent with the constitution's "secrets in `.env`, never committed" stance, extended to build secrets).

The backend (`pytest`) and frontend builds run as they do today; the desktop job depends on the frontend build artifact and on `pyproject.toml`/`uv.lock`, nothing else.
