/**
 * Tabbed windows — the same structure as Ontological Studio's desktop (its src/main/tabs.js),
 * so the two apps look and behave as one family.
 *
 * Each window's own page is the shell (tab strip in the title bar + the home); every tab is a
 * WebContentsView laid over it below the strip, running the Robo Architect SPA on one view
 * (`app://app/?view=Proposals` …). Tabs can be moved to a window of their own without reloading.
 *
 * The home replaces the old launcher: it opens a project (a graph in the bundled Ontological
 * DB + a code folder). Every tab works on that one project — the backend serves one graph at
 * a time — so switching the project reloads the open tabs.
 */

import { BrowserWindow, Menu, WebContentsView, ipcMain, shell, type WebContents } from "electron";
import fs from "node:fs";
import path from "node:path";

import { getDataDir, getLogsDir } from "./data-dir";
import { getDockerStackRuntime } from "./docker-stack";
import { log } from "./logging";
import { handleLauncherEnter } from "./launcher/enter";
import { resolveSessionUser } from "./launcher/identity";
import { activeProfile, currentPhase, markPending } from "./launcher/launcher-state";
import { getRuntimeBackend } from "./backend";
import { loadSettings } from "./settings";
import { tr } from "./lang";

const BAR = 38; // the shell's strip; the traffic lights sit inside it (macOS)
const SHELL_URL = "app://app/__shell/index.html";
const VIEWS: Record<string, string> = {
  Proposals: "프로포절",
  Stories: "요구사항",
  Process: "프로세스",
  Design: "설계",
  Data: "데이터",
  Code: "코드",
  Legacy: "레거시",
};

export interface TabTarget {
  view?: string;
  proposal?: string;
  constitution?: boolean;
  title?: string;
  /** 같은 화면만 띄운 탭이 이미 있으면 새로 열지 않고 그 탭으로 간다 */
  reuse?: boolean;
}

interface Tab {
  id: string;
  target: TabTarget;
  view: WebContentsView;
  title: string;
  loading: boolean;
}

export interface ShellSession {
  graph: string | null;
  projectRoot: string;
  connectionId: string;
  identity: Awaited<ReturnType<typeof resolveSessionUser>>;
}

const windows = new Set<TabWindow>();
let seq = 0;
let preloadPath = "";
let session: ShellSession | null = null;

function urlFor(t: TabTarget): string {
  const q = new URLSearchParams();
  if (t.view && VIEWS[t.view]) q.set("view", t.view);
  if (t.proposal) q.set("proposal", t.proposal);
  if (t.constitution) q.set("constitution", "1");
  const qs = q.toString();
  return `app://app/${qs ? `?${qs}` : ""}`;
}

function titleFor(t: TabTarget): string {
  return t.title || (t.view && VIEWS[t.view]) || "Robo Architect";
}

const isOurs = (url: string) => url.startsWith("app://app/") && !url.startsWith(SHELL_URL);

export class TabWindow {
  tabs: Tab[] = [];
  active = "home";
  win: BrowserWindow;

  constructor(opts: { bounds?: Partial<Electron.Rectangle>; icon?: string } = {}) {
    this.win = new BrowserWindow({
      width: 1440,
      height: 900,
      minWidth: 1024,
      minHeight: 640,
      ...(opts.bounds || {}),
      title: "Robo Architect",
      icon: opts.icon,
      backgroundColor: "#14171c",
      show: true,
      ...(process.platform === "darwin" ? { titleBarStyle: "hidden" as const, trafficLightPosition: { x: 14, y: 13 } } : {}),
      ...(process.platform === "win32"
        ? { titleBarStyle: "hidden" as const, titleBarOverlay: { color: "#191d24", symbolColor: "#e6eaf0", height: BAR } }
        : {}),
      webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, preload: preloadPath },
    });
    windows.add(this);
    this.win.on("resize", () => this.layout());
    for (const [ev, on] of [["enter-full-screen", true], ["leave-full-screen", false]] as const) {
      this.win.on(ev as "enter-full-screen", () => this.win.webContents.send("shell:fullscreen", on));
    }
    this.win.on("page-title-updated", (e) => e.preventDefault());
    this.win.on("closed", () => {
      for (const t of this.tabs) t.view.webContents.close();
      this.tabs = [];
      windows.delete(this);
    });
    this.win.webContents.on("did-finish-load", () => this.sync());
    this.win.webContents.setWindowOpenHandler(({ url }) => this.routeOpen(url));
    this.win.webContents.on("will-navigate", (e, url) => {
      if (!url.startsWith(SHELL_URL)) e.preventDefault();
    });
    void this.win.loadURL(SHELL_URL);
  }

  tab(id: string): Tab | undefined {
    return this.tabs.find((t) => t.id === id);
  }

  /** A link that wants a new window: ours becomes a tab, anything else goes to the browser. */
  routeOpen(url: string): { action: "deny" } {
    if (isOurs(url)) {
      const u = new URL(url);
      this.open({ view: u.searchParams.get("view") || undefined, proposal: u.searchParams.get("proposal") || undefined });
    } else if (url.startsWith("http://") || url.startsWith("https://")) {
      void shell.openExternal(url);
    }
    return { action: "deny" };
  }

  open(target: TabTarget, { activate = true } = {}): string {
    if (target.reuse && target.view) {
      const same = this.tabs.find((x) => x.target.view === target.view && !x.target.proposal && !x.target.constitution);
      if (same) { this.activate(same.id); return same.id; }
    }
    const t: TabTarget = {};
    if (target.view && VIEWS[target.view]) t.view = target.view;
    if (target.proposal && /^[A-Za-z0-9_-]{1,40}$/.test(target.proposal)) t.proposal = target.proposal;
    if (target.constitution) t.constitution = true;
    if (target.title) t.title = String(target.title).slice(0, 80);
    const view = new WebContentsView({
      webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, preload: preloadPath },
    });
    view.setBackgroundColor("#14171c");
    const tab: Tab = { id: `t${++seq}`, target: t, view, title: titleFor(t), loading: true };
    this.adopt(tab, activate);
    void view.webContents.loadURL(urlFor(t));
    return tab.id;
  }

  /** Put an existing tab (new, or moved from another window) into this window. */
  adopt(tab: Tab, activate = true): void {
    const wc = tab.view.webContents;
    wc.removeAllListeners("page-title-updated");
    wc.removeAllListeners("did-start-loading");
    wc.removeAllListeners("did-stop-loading");
    // The SPA keeps document.title = its current view, so the tab reads what it shows.
    // (the embedded analyzer sets its own title — only the SPA's view names are taken)
    // (English mode: the translator renames the SPA's title too — its English names count)
    wc.on("page-title-updated", (_e, title) => {
      if (title && Object.values(VIEWS).some((v) => v === title || tr(v) === title)) {
        tab.title = title;
        this.sync();
      }
    });
    wc.on("did-start-loading", () => {
      tab.loading = true;
      this.sync();
    });
    wc.on("did-stop-loading", () => {
      tab.loading = false;
      this.sync();
    });
    wc.setWindowOpenHandler(({ url }) => this.routeOpen(url));
    wc.on("will-navigate", (e, url) => {
      if (!isOurs(url)) {
        e.preventDefault();
        if (url.startsWith("http://") || url.startsWith("https://")) void shell.openExternal(url);
      }
    });
    wc.on("before-input-event", (_e, input) => {
      if (input.type === "keyDown" && input.key === "I" && input.shift && (input.meta || input.control)) wc.toggleDevTools();
    });
    this.win.contentView.addChildView(tab.view);
    this.tabs.push(tab);
    if (activate) this.activate(tab.id);
    else {
      tab.view.setVisible(false);
      this.layout();
      this.sync();
    }
  }

  activate(id: string): void {
    if (id !== "home" && !this.tab(id)) id = "home";
    this.active = id;
    for (const t of this.tabs) t.view.setVisible(t.id === id);
    this.layout();
    const t = this.tab(id);
    if (t) t.view.webContents.focus();
    else this.win.webContents.focus();
    this.sync();
  }

  /** Remove from this window without destroying it (close or move). */
  take(id: string): Tab | null {
    const i = this.tabs.findIndex((t) => t.id === id);
    if (i < 0) return null;
    const t = this.tabs.splice(i, 1)[0]!;
    this.win.contentView.removeChildView(t.view);
    if (this.active === id) this.activate((this.tabs[i] || this.tabs[i - 1] || { id: "home" }).id);
    else this.sync();
    return t;
  }

  close(id: string): void {
    const t = this.take(id);
    if (t) t.view.webContents.close();
  }

  detach(id: string): void {
    const t = this.tab(id);
    if (!t) return;
    const [x = 0, y = 0] = this.win.getPosition();
    const [width = 1440, height = 900] = this.win.getSize();
    this.take(id);
    const w = new TabWindow({ bounds: { x: x + 40, y: y + 40, width, height } });
    w.win.webContents.once("did-finish-load", () => w.adopt(t, true));
  }

  cycle(step: number): void {
    const ids = ["home", ...this.tabs.map((t) => t.id)];
    const i = ids.indexOf(this.active);
    this.activate(ids[(i + step + ids.length) % ids.length] ?? "home");
  }

  nth(n: number): void {
    // ⌘1 = home, ⌘2.. = tabs, ⌘9 = last
    const ids = ["home", ...this.tabs.map((t) => t.id)];
    this.activate((n >= 9 ? ids[ids.length - 1] : ids[n - 1] || ids[ids.length - 1]) ?? "home");
  }

  layout(): void {
    const [width = 0, height = 0] = this.win.getContentSize();
    for (const t of this.tabs) t.view.setBounds({ x: 0, y: BAR, width, height: Math.max(0, height - BAR) });
  }

  state() {
    return {
      active: this.active,
      tabs: this.tabs.map((t) => ({ id: t.id, title: t.title, view: t.target.view || "", loading: t.loading })),
    };
  }

  sync(): void {
    if (this.win.isDestroyed()) return;
    this.win.webContents.send("shell:tabs", this.state());
  }

  activeContents(): WebContents {
    const t = this.tab(this.active);
    return t ? t.view.webContents : this.win.webContents;
  }

  tabMenu(id: string): void {
    const t = this.tab(id);
    if (!t) return;
    Menu.buildFromTemplate([
      { label: tr("새로고침"), click: () => t.view.webContents.reload() },
      { label: tr("새 창으로 분리"), click: () => this.detach(id) },
      { type: "separator" },
      { label: tr("탭 닫기"), click: () => this.close(id) },
      {
        label: tr("다른 탭 닫기"),
        enabled: this.tabs.length > 1,
        click: () => this.tabs.filter((x) => x.id !== id).forEach((x) => this.close(x.id)),
      },
    ]).popup({ window: this.win });
  }
}

function owner(sender: WebContents): { w: TabWindow; from: "shell" | "tab" } | null {
  for (const w of windows) {
    if (w.win.webContents === sender) return { w, from: "shell" };
    if (w.tabs.some((t) => t.view.webContents === sender)) return { w, from: "tab" };
  }
  return null;
}

function focused(): TabWindow | null {
  const bw = BrowserWindow.getFocusedWindow();
  for (const w of windows) if (w.win === bw) return w;
  return [...windows][0] || null;
}

function broadcastSession(): void {
  for (const w of windows) if (!w.win.isDestroyed()) w.win.webContents.send("shell:session", session);
}

/**
 * Open (or switch to) a project: the bundled connection + a graph + a code folder. Runs the
 * launcher's enter (validation, backend graph switch, lastProfile) and reloads open tabs.
 */
export async function openProject(graph: string, projectRoot: string): Promise<ShellSession> {
  const settings = await loadSettings();
  const bundled = settings.savedConnections.find((c) => c.source === "bundled");
  if (!bundled) throw new Error("번들 그래프 DB 가 아직 준비되지 않았습니다.");
  const identity = await resolveSessionUser(projectRoot);
  if (currentPhase() === "entered") markPending();
  const r = await handleLauncherEnter({ connectionId: bundled.id, projectRoot, identity, graph });
  const changed = !session || session.graph !== (r.graph ?? null) || session.projectRoot !== projectRoot;
  session = { graph: r.graph ?? null, projectRoot, connectionId: r.activeConnectionId, identity: r.identity };
  log("info", "shell.project_open", { graph: session.graph, projectRoot });
  broadcastSession();
  if (changed) for (const w of windows) for (const t of w.tabs) t.view.webContents.reload();
  return session;
}

/** On start: reopen the last project if its graph and folder are still there. */
export async function reopenLastProject(): Promise<void> {
  if (session) return;
  const profile = (await loadSettings()).lastProfile;
  if (!profile?.graph || !profile.projectRoot || !fs.existsSync(profile.projectRoot)) {
    broadcastSession();
    return;
  }
  try {
    await openProject(profile.graph, profile.projectRoot);
  } catch (err) {
    log("warn", "shell.reopen_failed", { message: err instanceof Error ? err.message : String(err) });
    broadcastSession();
  }
}

async function claudeCli(): Promise<string | null> {
  for (const dir of (process.env.PATH || "").split(path.delimiter)) {
    const p = path.join(dir, process.platform === "win32" ? "claude.exe" : "claude");
    if (dir && fs.existsSync(p)) return p;
  }
  return null;
}

/**
 * Whether this PC has an OpenAI key, for the shell's status row — **the name only, never the value**.
 *
 * Most of the LLM work needs no key: the analyzer and the search LLM are `claude_code_bridge` and
 * the Architect's skill runner is `claude_cli`, so the CLI on this PC does it. What is still on
 * OpenAI in a default install, measured 2026-11-05:
 *
 *   catalog    `config/catalog.env` sets `LLM_PROVIDER=openai` and `FK_INFERENCE_ENABLED=true`,
 *              and passes the key through as a bare name. Its settings read
 *              `os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")`, so **either name
 *              works** — the table descriptions and the FK inference are what break without it.
 *   architect  `architect/app/.env` is `LLM_PROVIDER=openai` with no key, so the OpenAI SDK reads
 *              `OPENAI_API_KEY` out of this process's environment.
 *
 * Not reported here: `ROBO_EMBED_API_KEY`. `config/analyzer.env` ships
 * `ROBO_PIPELINE_EMBED_ENABLED=false`, so embeddings are off by design and search falls back to
 * lexical (`search/corpus/corpus.py` calls that "임베딩을 끈 설치(키 없는 Lite)"). Setting that key
 * alone would change nothing, so saying it is "missing" would be a false alarm.
 */
function openAiKey(): { names: string[]; set: boolean } {
  const names = ["LLM_API_KEY", "OPENAI_API_KEY"];
  return { names, set: names.some((n) => (process.env[n] || "").trim() !== "") };
}

export function wireShellIpc(): void {
  const shellOnly =
    <A extends unknown[], R>(fn: (w: TabWindow, ...a: A) => R) =>
    (e: Electron.IpcMainInvokeEvent, ...a: A) => {
      const o = owner(e.sender);
      if (o && o.from === "shell") return fn(o.w, ...a);
      return null;
    };
  const anyOfOurs =
    <A extends unknown[], R>(fn: (w: TabWindow, ...a: A) => R) =>
    (e: Electron.IpcMainInvokeEvent, ...a: A) => {
      const o = owner(e.sender);
      if (o) return fn(o.w, ...a);
      return null;
    };
  ipcMain.handle("shell:tabs:get", shellOnly((w) => w.state()));
  ipcMain.handle("shell:tabs:open", anyOfOurs((w, target: TabTarget) => (session ? w.open(target || {}) : null)));
  ipcMain.handle("shell:tabs:activate", shellOnly((w, id: string) => w.activate(String(id))));
  ipcMain.handle("shell:tabs:close", shellOnly((w, id: string) => w.close(String(id))));
  ipcMain.handle("shell:tabs:menu", shellOnly((w, id: string) => w.tabMenu(String(id))));
  ipcMain.handle("shell:window:new", anyOfOurs(() => void new TabWindow()));
  ipcMain.handle("shell:is-fullscreen", anyOfOurs((w) => w.win.isFullScreen()));
  ipcMain.handle("shell:session", anyOfOurs(() => session));
  ipcMain.handle(
    "shell:project:open",
    shellOnly(async (_w, input: { graph: string; projectRoot: string }) => {
      try {
        return { ok: true, data: await openProject(String(input.graph), String(input.projectRoot)) };
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    }),
  );
  ipcMain.handle(
    "shell:open",
    anyOfOurs(async (_w, what: string) => {
      const dir = what === "code" ? session?.projectRoot : what === "logs" ? getLogsDir() : what === "data" ? getDataDir() : null;
      if (dir) await shell.openPath(dir);
    }),
  );
  ipcMain.handle(
    "shell:info",
    anyOfOurs(async () => {
      const be = getRuntimeBackend();
      return {
        session,
        backend: be.status,
        graphUser: "robo",
        claude: await claudeCli(),
        openAiKey: openAiKey(),
        // 화면이 "Docker 컨테이너 N개" 를 손으로 적고 있었다 — 서비스가 늘면 틀린 말이
        // 된다. 매니페스트의 이미지 수를 세서 넘긴다(스택에 뜨는 컨테이너와 1:1 이다).
        stackServices: Object.keys(getDockerStackRuntime()?.manifest.images ?? {}).length || null,
        platform: process.platform,
        enteredProfile: activeProfile(),
      };
    }),
  );
}

/** Menu items that act on the focused window's tabs. */
export function menuItems(): Electron.MenuItemConstructorOptions[] {
  const on = (fn: (w: TabWindow) => void) => () => {
    const w = focused();
    if (w) fn(w);
  };
  return [
    { label: tr("홈"), accelerator: "CmdOrCtrl+T", click: on((w) => w.activate("home")) },
    { label: tr("새 창"), accelerator: "CmdOrCtrl+N", click: () => void new TabWindow() },
    { label: tr("탭 닫기"), accelerator: "CmdOrCtrl+W", click: on((w) => (w.active === "home" ? w.win.close() : w.close(w.active))) },
    { label: tr("탭 새로고침"), accelerator: "CmdOrCtrl+R", click: on((w) => w.activeContents().reload()) },
    { type: "separator" },
    { label: tr("다음 탭"), accelerator: "Ctrl+Tab", click: on((w) => w.cycle(1)) },
    { label: tr("이전 탭"), accelerator: "Ctrl+Shift+Tab", click: on((w) => w.cycle(-1)) },
    ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => ({
      label: tr(`탭 ${n}`),
      accelerator: `CmdOrCtrl+${n}`,
      visible: false,
      click: on((w) => w.nth(n)),
    })),
    { type: "separator" },
    { label: tr("개발자 도구 (현재 탭)"), accelerator: "Alt+CmdOrCtrl+I", click: on((w) => w.activeContents().toggleDevTools()) },
  ];
}

export function setPreload(p: string): void {
  preloadPath = p;
}

export function allWindows(): TabWindow[] {
  return [...windows];
}

export function firstWindow(): TabWindow | null {
  return [...windows][0] || null;
}

// Test/capture hook (demo scripts, Playwright `app.evaluate`): the windows and their tabs.
(globalThis as Record<string, unknown>).__raShell = { allWindows, firstWindow };
