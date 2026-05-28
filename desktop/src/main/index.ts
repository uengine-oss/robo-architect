/**
 * Electron main entry — orchestrates Phase 2 + US1 (partial):
 *   T007 lifecycle skeleton, T014 single-instance lock, T015 BrowserWindow +
 *   app:// protocol (+ /api/* proxy to the backend port), T025 startup
 *   orchestration (port → backend spawn → wait ready → load window), T026
 *   IPC handlers (app:getRuntimeState, backend:retry, logs:reveal,
 *   app:openExternal) + push channel app:onBackendStatus.
 *
 * Pieces NOT yet implemented (deferred to their own tasks):
 *   - Strict CSP (T015 polish — needs SPA index.html injection or a
 *     defaultSession header rewrite; deferred to T027 with the splash UI)
 *   - Neo4j child lifecycle (T023) — for dev we rely on whatever Neo4j the
 *     existing project setup already runs (docker-compose)
 *   - Settings UI + secret store + apiBase rewrite (US3 T038–T047)
 *   - Auto-update (US2 T031–T037)
 */

import { app, BrowserWindow, net, protocol, shell } from "electron";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

import {
  IpcErrorCodes,
  type IpcResult,
  type RuntimeState,
} from "../shared/ipc-contract";

import { ensureDataDirs } from "./data-dir";
import { initLogging, log, revealLogs } from "./logging";
import { IpcHandlerError, pushToRenderer, registerHandler } from "./ipc";
import {
  getRuntimeBackend,
  onBackendStatusChange,
  retryBackend,
  startBackend,
  stopBackend,
} from "./backend";
// 032: register stub launcher handlers so the renderer's window.desktop
// surface answers (with a typed VALIDATION error) for every launcher channel
// until each gating task lands a real handler.
import { registerLauncherIpcStubs } from "./launcher/ipc-handlers";

let mainWindow: BrowserWindow | null = null;

// T015 (US1): register `app://` as a privileged scheme so the renderer can
// load the bundled SPA from disk with the same guarantees as https — fetch
// API, streams, secure context. MUST run before app.whenReady().
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

// ---------------------------------------------------------------------------
// T014 single-instance lock — must run synchronously at module load so the
// second-instance process exits before it spawns child processes of its own.
// ---------------------------------------------------------------------------

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  console.log("single-instance.already_running — exiting");
  app.quit();
  // Note: no `process.exit` — Electron tears down on `app.quit` and we
  // explicitly skip the rest of the wiring below in the second instance.
}

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function resolveFrontendDist(): string {
  // Dev: `<repo-root>/frontend/dist` lives one level up from `desktop/`.
  // Production (asar): T028 packs frontend/dist into the asar at this same
  // relative location, so the resolution is identical in both modes.
  return path.resolve(app.getAppPath(), "..", "frontend", "dist");
}

function buildRuntimeState(): RuntimeState {
  const be = getRuntimeBackend();
  return {
    appVersion: app.getVersion(),
    backendPort: be.port,
    boltPort: null, // T023 — Neo4j-managed mode not yet implemented
    backendPid: be.pid,
    neo4jPid: null,
    status: be.status,
    dataSource: "bundled",
    dataDir: app.getPath("userData"),
    updateState: "idle",
  };
}

// ---------------------------------------------------------------------------
// T015 protocol handler — serves the SPA from frontend/dist AND proxies
// `/api/*` to the live backend port. Putting the proxy here avoids editing
// the SPA's API client (T017 will replace this with a clean apiBase.js).
// ---------------------------------------------------------------------------

function registerAppProtocol(): void {
  const frontendDist = resolveFrontendDist();
  log("info", "protocol.app.registering", { frontendDist });

  protocol.handle("app", async (request) => {
    const url = new URL(request.url);
    let pathname = decodeURIComponent(url.pathname);
    if (!pathname || pathname === "/") {
      pathname = "/index.html";
    }

    // Proxy /api/** to the live backend.
    if (pathname === "/api" || pathname.startsWith("/api/")) {
      const port = getRuntimeBackend().port;
      if (port === null) {
        return new Response("Backend not ready", { status: 503 });
      }
      const upstream = `http://127.0.0.1:${port}${pathname}${url.search}`;
      try {
        return await net.fetch(upstream, {
          method: request.method,
          headers: request.headers,
          body: request.body,
          redirect: "manual",
          // duplex required when sending a streaming body — net.fetch follows
          // the Web Fetch spec.
          ...(request.body ? { duplex: "half" as const } : {}),
        });
      } catch (err) {
        log("error", "protocol.api_proxy.failed", {
          upstream,
          message: err instanceof Error ? err.message : String(err),
        });
        return new Response("Bad Gateway", { status: 502 });
      }
    }

    // Static SPA assets from frontend/dist.
    const filePath = path.normalize(path.join(frontendDist, pathname));
    if (!filePath.startsWith(frontendDist + path.sep) && filePath !== frontendDist) {
      log("warn", "protocol.app.forbidden", { pathname, filePath });
      return new Response("Forbidden", { status: 403 });
    }

    if (!fs.existsSync(filePath)) {
      const hasExtension = path.extname(filePath).length > 0;
      if (hasExtension) {
        log("warn", "protocol.app.missing_asset", { pathname });
        return new Response("Not Found", { status: 404 });
      }
      // SPA fallback for client-side routing.
      return net.fetch(pathToFileURL(path.join(frontendDist, "index.html")).toString());
    }
    return net.fetch(pathToFileURL(filePath).toString());
  });
}

// ---------------------------------------------------------------------------
// BrowserWindow
// ---------------------------------------------------------------------------

function createMainWindow(): BrowserWindow {
  const preloadPath = path.join(app.getAppPath(), "dist", "preload", "preload", "index.js");

  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    title: "Robo Architect",
    show: false,
    webPreferences: {
      preload: preloadPath,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  // T015 polish: deny new BrowserWindows; route http(s) to OS browser (FR-021).
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://") || url.startsWith("https://")) {
      void shell.openExternal(url);
    } else {
      log("warn", "window.open_blocked", { url });
    }
    return { action: "deny" };
  });
  // Block in-page navigations to non-`app://` origins (defence in depth).
  window.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("app://")) {
      event.preventDefault();
      if (url.startsWith("http://") || url.startsWith("https://")) {
        void shell.openExternal(url);
      } else {
        log("warn", "window.navigate_blocked", { url });
      }
    }
  });

  void window.loadURL("app://app/");

  // Cmd+Shift+I (macOS) / Ctrl+Shift+I opens DevTools for debugging.
  window.webContents.on("before-input-event", (_e, input) => {
    if (input.type === "keyDown" && input.key === "I" && input.shift && (input.meta || input.control)) {
      window.webContents.toggleDevTools();
    }
  });

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

// ---------------------------------------------------------------------------
// T026 IPC handlers
// ---------------------------------------------------------------------------

function registerIpcHandlers(): void {
  registerHandler("app:getRuntimeState", () => buildRuntimeState());

  registerHandler("backend:retry", async () => {
    try {
      await retryBackend();
      return { ok: true as const };
    } catch (err) {
      throw new IpcHandlerError(
        IpcErrorCodes.INTERNAL,
        err instanceof Error ? err.message : String(err),
      );
    }
  });

  registerHandler("logs:reveal", async () => {
    await revealLogs();
    return { ok: true as const };
  });

  registerHandler("app:openExternal", async ({ url }) => {
    if (!url.startsWith("http://") && !url.startsWith("https://")) {
      throw new IpcHandlerError(IpcErrorCodes.BLOCKED_SCHEME, `refused to open: ${url}`);
    }
    await shell.openExternal(url);
    return { ok: true as const };
  });

  // Bridge backend status changes to the renderer.
  onBackendStatusChange((status, detail) => {
    const be = getRuntimeBackend();
    pushToRenderer("app:onBackendStatus", {
      status,
      backendPort: be.port,
      boltPort: null,
      detail,
    });
  });

  // Stubs for 023 channels whose owning task hasn't shipped yet — kept here so
  // the renderer can call them without crashing the bridge. Each returns a
  // typed `VALIDATION` error pointing at the gating task.
  const unimplemented = [
    "settings:get",
    "settings:set",
    "settings:setSecret",
    "settings:testNeo4jConnection",
    "dataDir:get",
    "dataDir:choose",
    "update:check",
    "update:apply",
  ] as const;
  for (const channel of unimplemented) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (registerHandler as any)(channel, () => {
      throw new IpcHandlerError(
        IpcErrorCodes.VALIDATION,
        `${channel}: not implemented yet (deferred to US2/US3 tasks)`,
      );
    });
  }

  // 032 launcher channels — same pattern but in a separate module so each
  // gating task can opt out of the stub by passing its channel to the skip
  // set when it registers a real handler.
  registerLauncherIpcStubs();
}

// ---------------------------------------------------------------------------
// T025 startup orchestration
// ---------------------------------------------------------------------------

async function bootstrap(): Promise<void> {
  await ensureDataDirs();
  initLogging();
  log("info", "app.ready", { appVersion: app.getVersion() });

  registerAppProtocol();
  registerIpcHandlers();

  // Create the window early so the user gets a splash even while the backend
  // starts up. The SPA proxy returns 503 for /api calls until backend is
  // ready — the renderer will retry; full splash UI lands in T027.
  mainWindow = createMainWindow();

  try {
    await startBackend();
  } catch (err) {
    log("error", "app.backend_start_failed", {
      message: err instanceof Error ? err.message : String(err),
    });
    // status is already set to "fatal" by backend.ts; the renderer will see
    // the push and (post-T027) show the fatal screen.
  }
}

// ---------------------------------------------------------------------------
// App lifecycle
// ---------------------------------------------------------------------------

if (gotLock) {
  app.whenReady().then(() => {
    bootstrap().catch((err: unknown) => {
      log("error", "app.bootstrap.failed", {
        message: err instanceof Error ? err.message : String(err),
      });
    });
  });

  app.on("window-all-closed", () => {
    app.quit();
  });

  app.on("before-quit", async (event) => {
    log("info", "app.before-quit", {});
    // Best-effort: give the backend a graceful shutdown before Electron exits.
    if (getRuntimeBackend().pid !== null) {
      event.preventDefault();
      try {
        await stopBackend();
      } finally {
        app.exit(0);
      }
    }
  });
}
