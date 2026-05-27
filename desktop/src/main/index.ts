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

import { app, BrowserWindow } from "electron";
import path from "node:path";

import { ensureDataDirs } from "./data-dir";
import { initLogging, log } from "./logging";

let mainWindow: BrowserWindow | null = null;

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

  // Phase 2 stub: load a blank document. T015 replaces this with the
  // `app://` protocol registration and the bundled Vue SPA.
  void window.loadURL("about:blank");

  window.once("ready-to-show", () => window.show());
  window.on("closed", () => {
    if (mainWindow === window) {
      mainWindow = null;
    }
  });

  return window;
}

async function bootstrap(): Promise<void> {
  await ensureDataDirs();
  initLogging();
  log("info", "app.ready", { appVersion: app.getVersion() });

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
