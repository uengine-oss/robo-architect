/**
 * Electron app-lifecycle skeleton for Robo-Architect Desktop.
 *
 * Phase 2 (T007) scope only: app.whenReady → ready, window-all-closed,
 * before-quit, activate. Placeholder hooks marked TODO are filled in by US1:
 *   - single-instance lock (T014)
 *   - app:// protocol + SPA load (T015)
 *   - Neo4j + backend start orchestration (T025)
 *   - IPC handler registration (T026)
 *
 * What runs today: opens an empty hardened BrowserWindow so the checkpoint
 * `npm --prefix desktop run dev` produces a window we can verify in T012.
 */

import { app, BrowserWindow, net, protocol } from "electron";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import { ensureDataDirs } from "./data-dir";
import { initLogging, log } from "./logging";

let mainWindow: BrowserWindow | null = null;

// T015 (US1, partial): register `app://` as a privileged scheme so the renderer
// can load the bundled SPA from disk with the same guarantees as https — fetch
// API, streams, secure-context. MUST run before app.whenReady().
protocol.registerSchemesAsPrivileged([
  {
    scheme: "app",
    privileges: {
      standard: true,
      secure: true,
      supportFetchAPI: true,
      stream: true,
      corsEnabled: true,
    },
  },
]);

function resolveFrontendDist(): string {
  // Dev: `<repo-root>/frontend/dist` lives one level up from `desktop/`.
  // Production (asar): T028 packs frontend/dist into the asar at this same
  // relative location, so the resolution is identical in both modes.
  return path.resolve(app.getAppPath(), "..", "frontend", "dist");
}

function createMainWindow(): BrowserWindow {
  // Project references produce dist/main/main/ and dist/preload/preload/; resolve
  // the preload relative to the app root so the path survives any outDir tweak.
  const preloadPath = path.join(app.getAppPath(), "dist", "preload", "preload", "index.js");

  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  void window.loadURL("app://app/");

  window.once("ready-to-show", () => window.show());
  window.webContents.on("did-fail-load", (_e, errorCode, errorDescription, validatedURL) => {
    log("error", "window.did_fail_load", { errorCode, errorDescription, validatedURL });
  });
  window.on("closed", () => {
    if (mainWindow === window) {
      mainWindow = null;
    }
  });

  return window;
}

function registerAppProtocol(): void {
  const frontendDist = resolveFrontendDist();
  log("info", "protocol.app.registering", { frontendDist });

  protocol.handle("app", async (request) => {
    const url = new URL(request.url);
    let pathname = decodeURIComponent(url.pathname);
    if (!pathname || pathname === "/") {
      pathname = "/index.html";
    }

    // Resolve under the dist root and verify the result stays inside it
    // (defence in depth — net.fetch on a file:// URL also enforces this,
    // but explicit beats implicit here).
    const filePath = path.normalize(path.join(frontendDist, pathname));
    if (!filePath.startsWith(frontendDist + path.sep) && filePath !== frontendDist) {
      log("warn", "protocol.app.forbidden", { pathname, filePath });
      return new Response("Forbidden", { status: 403 });
    }

    // SPA fallback: if a route-like path (no extension) is requested and the
    // file does not exist on disk, serve index.html so client-side routing
    // can take over. Asset requests (with extensions) 404 normally.
    const exists = fs.existsSync(filePath);
    if (!exists) {
      const hasExtension = path.extname(filePath).length > 0;
      if (hasExtension) {
        log("warn", "protocol.app.missing_asset", { pathname });
        return new Response("Not Found", { status: 404 });
      }
      return net.fetch(pathToFileURL(path.join(frontendDist, "index.html")).toString());
    }

    return net.fetch(pathToFileURL(filePath).toString());
  });
}

async function bootstrap(): Promise<void> {
  await ensureDataDirs();
  initLogging();
  log("info", "app.ready", { appVersion: app.getVersion() });

  registerAppProtocol();

  // TODO(US1·T014): app.requestSingleInstanceLock() / second-instance focus.
  // TODO(US1·T025): startup orchestration — data-dir → Neo4j → ports → backend.
  // TODO(US1·T026): IPC handler registration via ./ipc.ts.

  mainWindow = createMainWindow();
}

app.whenReady().then(() => {
  bootstrap().catch((err: unknown) => {
    log("error", "app.bootstrap.failed", {
      message: err instanceof Error ? err.message : String(err),
    });
    // Phase 2: no user-facing fatal screen yet; that lands in US1·T027.
  });
});

app.on("window-all-closed", () => {
  // macOS convention: keep the app process alive when all windows close.
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    mainWindow = createMainWindow();
  }
});

app.on("before-quit", () => {
  log("info", "app.before-quit", {});
  // TODO(US1·T020/T023): SIGTERM → grace → SIGKILL on backend & Neo4j children.
});
