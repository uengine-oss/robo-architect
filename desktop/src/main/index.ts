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

import { app, Menu, nativeImage, net, protocol, shell } from "electron";
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
import { adoptHostPath } from "./host-path";
import { IpcHandlerError, pushToRenderer, registerHandler } from "./ipc";
import {
  copy,
  listDir,
  mkdir,
  readFile,
  rename,
  stageProject,
  trash,
  writeFile,
} from "./fs-browser";
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
// Tabbed windows (Ontological Studio family): shell = tab strip + home, tabs = SPA views.
import { TabWindow, firstWindow, menuItems, reopenLastProject, setPreload, wireShellIpc } from "./tabs";
// English mode (runtime translator): language choice, the dictionary, <head> injection.
import { currentLang, i18nAsset, initLanguage, injectHtml, langSource, saveLanguage, tr, type Lang } from "./lang";

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

// UI language — before "ready": it also sets Chromium's --lang for every renderer.
initLanguage();

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
  const w = firstWindow();
  if (w) {
    if (w.win.isMinimized()) w.win.restore();
    w.win.focus();
  }
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** The window shell (tab strip + home): desktop/resources/shell, next to the app in a package. */
function resolveShellDir(): string {
  const dev = path.resolve(app.getAppPath(), "resources", "shell");
  if (fs.existsSync(dev)) return dev;
  return path.join(process.resourcesPath, "shell");
}

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

/**
 * A file of ours. HTML pages (the shell, the SPA, the analyzer) get English mode in their
 * <head> when the UI is English; everything else — and every page in Korean mode — is
 * served as it is.
 */
function serveFile(file: string): Promise<Response> | Response {
  if (currentLang() === "en" && file.endsWith(".html")) {
    return new Response(injectHtml(fs.readFileSync(file, "utf8")), {
      headers: { "content-type": "text/html; charset=utf-8" },
    });
  }
  return net.fetch(pathToFileURL(file).toString());
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

    // Proxy /api/** upstream. /api/gateway/** → analyzer API Gateway (9000);
    // every other /api/** → the spawned architect backend. Mirrors the vite
    // dev-server proxy (frontend/vite.config.js) for the app:// production path,
    // where there is no vite to route the analyzer's gateway calls.
    if (pathname === "/api" || pathname.startsWith("/api/")) {
      let upstreamBase: string;
      if (pathname === "/api/gateway" || pathname.startsWith("/api/gateway/")) {
        upstreamBase = process.env.ROBO_GATEWAY_URL ?? "http://127.0.0.1:9000";
      } else {
        const port = getRuntimeBackend().port;
        if (port === null) {
          return new Response("Backend not ready", { status: 503 });
        }
        upstreamBase = `http://127.0.0.1:${port}`;
      }
      const upstream = `${upstreamBase}${pathname}${url.search}`;
      // 진단: 렌더러가 Neo4j override 헤더를 실었는지 (여기서 끊기면 프록시 문제).
      log("info", "protocol.api_proxy.headers", {
        pathname,
        neo4jUri: request.headers.get("x-neo4j-uri") ?? "(none)",
        neo4jDb: request.headers.get("x-neo4j-database") ?? "(none)",
      });
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

    // English mode: the translator and the dictionary (lang.ts).
    if (pathname.startsWith("/__i18n/")) {
      const a = i18nAsset(pathname);
      if (!a) return new Response("Not Found", { status: 404 });
      return new Response(a.body, { headers: { "content-type": a.type, "cache-control": "no-store" } });
    }

    // The window shell (tab strip + home) — its own folder, same origin as the SPA so the two
    // share the theme setting and the /api proxy.
    if (pathname.startsWith("/__shell/")) {
      const shellDir = resolveShellDir();
      const file = path.normalize(path.join(shellDir, pathname.slice("/__shell/".length)));
      if (!file.startsWith(shellDir + path.sep) || !fs.existsSync(file)) {
        return new Response("Not Found", { status: 404 });
      }
      return serveFile(file);
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
      return serveFile(path.join(frontendDist, "index.html"));
    }
    return serveFile(filePath);
  });
}

// ---------------------------------------------------------------------------
// Windows — tabbed (tabs.ts). The SPA's own window handlers (open → browser, navigation
// guard, DevTools key) live on each tab there.
// ---------------------------------------------------------------------------

function iconPath(): string {
  return path.resolve(app.getAppPath(), "resources", "icons", "icon_512x512.png");
}

function createMainWindow(): TabWindow {
  setPreload(path.join(app.getAppPath(), "dist", "preload", "preload", "index.js"));
  return new TabWindow({ icon: iconPath() });
}

/** 언어 / Language: saved, then the app restarts in it (ROBO_LANG, when set, still wins). */
function chooseLanguage(next: Lang): void {
  if (next === currentLang()) return;
  saveLanguage(next);
  log("info", "lang.saved", { next, source: langSource() });
  // the relaunch must not carry a --lang that would override the saved choice
  app.relaunch({ args: process.argv.slice(1).filter((a) => !/^--lang(=|$)/.test(a)) });
  app.quit();
}

function installMenu(): void {
  const isMac = process.platform === "darwin";
  const langItem = (code: Lang, label: string): Electron.MenuItemConstructorOptions => ({
    label,
    type: "radio",
    checked: currentLang() === code,
    click: () => chooseLanguage(code),
  });
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      ...(isMac ? [{ role: "appMenu" as const }] : []),
      { role: "editMenu" },
      { label: tr("탭"), submenu: menuItems() },
      // the two names stay in their own language — whoever cannot read the other one finds theirs
      { label: currentLang() === "en" ? "Language" : "언어", submenu: [langItem("ko", "한국어"), langItem("en", "English")] },
      { role: "windowMenu" },
    ]),
  );
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

  // 014 analysis-scope-browser: 경로 모드 트리/미리보기 + 파일 작업(root 하위 한정).
  registerHandler("fs:listDir", listDir);
  registerHandler("fs:readFile", readFile);
  registerHandler("fs:rename", rename);
  registerHandler("fs:copy", copy);
  registerHandler("fs:trash", trash);
  registerHandler("fs:mkdir", mkdir);
  registerHandler("fs:writeFile", writeFile);
  registerHandler("fs:stageProject", stageProject);

  // Bridge backend status changes to the renderer.
  onBackendStatusChange((status, detail, progress) => {
    const be = getRuntimeBackend();
    pushToRenderer("app:onBackendStatus", {
      status,
      backendPort: be.port,
      boltPort: null,
      detail,
      progress,
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
  log("info", "app.ready", { appVersion: app.getVersion(), lang: currentLang(), langSource: langSource() });
  // Finder gives a .app a bare PATH — docker and claude must be found before anything spawns them.
  await adoptHostPath(app.isPackaged);

  // Set macOS Dock icon.
  if (process.platform === "darwin" && app.dock) {
    const iconPath = path.resolve(app.getAppPath(), "resources", "icons", "icon_512x512.png");
    if (fs.existsSync(iconPath)) {
      const img = nativeImage.createFromPath(iconPath);
      if (!img.isEmpty()) {
        app.dock.setIcon(img);
        log("info", "app.dock_icon_set", { iconPath });
      } else {
        log("warn", "app.dock_icon_empty", { iconPath });
      }
    } else {
      log("warn", "app.dock_icon_missing", { iconPath });
    }
  }

  registerAppProtocol();
  registerIpcHandlers();
  wireShellIpc();
  installMenu();

  // Create the window early so the home shows the start-up progress while the backend
  // (and the Docker stack) come up. The SPA proxy returns 503 for /api until then.
  createMainWindow();

  try {
    await startBackend();
    // Reopen the last project (graph + code folder) so the home's cards work right away.
    await reopenLastProject();
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
  // Set the Dock icon as early as possible — before bootstrap() so it appears
  // on first paint rather than being updated after the window is shown.
  if (process.platform === "darwin") {
    app.on("will-finish-launching", () => {
      // Compiled file is at dist/main/index.js → ../../resources/
      const iconPath = path.resolve(__dirname, "..", "..", "resources", "icons", "icon_512x512.png");
      if (fs.existsSync(iconPath)) {
        const img = nativeImage.createFromPath(iconPath);
        if (!img.isEmpty() && app.dock) {
          app.dock.setIcon(img);
        }
      }
    });
  }

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
