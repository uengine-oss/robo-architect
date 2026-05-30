/**
 * E2E Playwright spec — Desktop Launcher (spec 032).
 *
 * Covers the implemented slice (US1 Q1–Q4, Q7-web-mode):
 *   C1 Cold start — fresh userData, launcher renders with empty connection list
 *   C2 Returning user — pre-saved connection + lastProfile shows pre-selected
 *   C3 Git identity — global gitconfig resolves to displayName in welcome banner
 *   C4 Unknown user — no gitconfig → inline git-config form appears
 *   C5 Web mode — frontend dev server has no launcher (window.desktop absent)
 *
 * Screenshots saved to: specs/032-desktop-startup-picker/manual/screenshots/
 *
 * Run from desktop/ directory:
 *   npx playwright test desktop-launcher-e2e.spec.ts --headed
 */

import { _electron as electron, chromium, expect, test } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const APP_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(APP_ROOT, "..");
const SCREENSHOTS = path.resolve(
  REPO_ROOT,
  "specs/032-desktop-startup-picker/manual/screenshots"
);

// Ensure screenshots directory exists
fs.mkdirSync(SCREENSHOTS, { recursive: true });

/** Minimal v2 settings with no saved connections. */
function emptySettings(): object {
  return {
    schemaVersion: 2,
    dataSource: "external",
    externalNeo4j: null,
    dataDir: null,
    llm: { provider: "openai", model: "gpt-4o-mini" },
    update: { autoCheck: true, lastCheckedAt: null },
    window: { bounds: null, maximized: false },
    lastPorts: { backend: null, bolt: null },
    savedConnections: [],
    recentProjectRoots: [],
    lastProfile: null,
  };
}

/** Settings with one pre-saved connection + lastProfile (returning user). */
function returningUserSettings(projectRoot: string): object {
  return {
    schemaVersion: 2,
    dataSource: "external",
    externalNeo4j: null,
    dataDir: null,
    llm: { provider: "openai", model: "gpt-4o-mini" },
    update: { autoCheck: true, lastCheckedAt: null },
    window: { bounds: null, maximized: false },
    lastPorts: { backend: null, bolt: null },
    savedConnections: [
      {
        id: "test-conn-001",
        label: "Local Dev",
        uri: "bolt://localhost:7687",
        user: "neo4j",
        database: null,
        source: "manual",
        lastConnectedAt: "2026-05-27T10:00:00.000Z",
        createdAt: "2026-05-20T09:00:00.000Z",
      },
    ],
    recentProjectRoots: [projectRoot],
    lastProfile: {
      connectionId: "test-conn-001",
      projectRoot,
      enteredAt: "2026-05-27T10:00:00.000Z",
    },
  };
}

interface IsolatedEnv {
  userDataDir: string; // Electron userData (settings.json lives here)
  home: string;       // HOME dir (git config lives here)
}

/**
 * Create a fully isolated test environment.
 * On macOS, Electron's app.getPath('userData') uses the Cocoa API which ignores
 * the HOME env var. We must pass --user-data-dir to truly isolate settings.
 */
function setupIsolatedEnv(opts: {
  settings?: object;
  gitName?: string;
  gitEmail?: string;
}): IsolatedEnv {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), "robo-e2e-"));
  const userDataDir = path.join(base, "user-data");
  const home = path.join(base, "home");
  fs.mkdirSync(userDataDir, { recursive: true });
  fs.mkdirSync(home, { recursive: true });

  if (opts.settings) {
    fs.writeFileSync(
      path.join(userDataDir, "settings.json"),
      JSON.stringify(opts.settings, null, 2),
    );
  }
  if (opts.gitName || opts.gitEmail) {
    const lines = ["[user]"];
    if (opts.gitName) lines.push(`\tname = ${opts.gitName}`);
    if (opts.gitEmail) lines.push(`\temail = ${opts.gitEmail}`);
    fs.writeFileSync(path.join(home, ".gitconfig"), lines.join("\n") + "\n");
  }
  return { userDataDir, home };
}

function cleanup(dir: string) {
  try {
    fs.rmSync(path.dirname(dir), { recursive: true, force: true });
  } catch {}
}

/** Launch Electron with a fully isolated userData and HOME. */
async function launchIsolated(env: IsolatedEnv) {
  return electron.launch({
    args: [APP_ROOT, `--user-data-dir=${env.userDataDir}`],
    env: {
      ...process.env,
      HOME: env.home,
      ROBO_SKIP_UPDATE_CHECK: "1",
    },
    timeout: 30_000,
  });
}

// ---------------------------------------------------------------------------
// C1 — Cold start: no settings, no git config
// ---------------------------------------------------------------------------
test("C1 — Cold start: empty connection list + Add form expanded", async () => {
  const env = setupIsolatedEnv({ settings: emptySettings() });
  const app = await launchIsolated(env);
  try {
    const win = await app.firstWindow();
    await win.waitForSelector(".launcher", { timeout: 20_000 });
    // Wait for identity resolve to settle (welcome banner appears)
    await win.waitForSelector(".welcome h1", { timeout: 10_000 });
    await win.waitForTimeout(1_500); // let Vue finish reactive updates

    // Assertions
    const h1 = await win.locator(".welcome h1").textContent();
    // Cold start with no gitconfig in isolated home → unknown user or whatever git global says
    expect(h1).toBeTruthy();

    // Add-connection form should be open (no saved connections)
    const addForm = win.locator("details.add-form");
    await expect(addForm).toBeVisible();

    // Enter button should be disabled (nothing selected)
    const enterBtn = win.locator("button.enter");
    await expect(enterBtn).toBeDisabled();

    // Screenshot
    await win.screenshot({
      path: path.join(SCREENSHOTS, "01_cold_start.png"),
      fullPage: true,
    });
  } finally {
    await app.close();
    cleanup(env.userDataDir);
  }
});

// ---------------------------------------------------------------------------
// C2 — Returning user: pre-saved connection pre-selected
// ---------------------------------------------------------------------------
test("C2 — Returning user: saved connection pre-selected", async () => {
  // Use a real directory as the fake project root so validate passes
  const fakeRoot = os.tmpdir();
  const env = setupIsolatedEnv({
    settings: returningUserSettings(fakeRoot),
    gitName: "Jane Doe",
    gitEmail: "jane@example.com",
  });
  const app = await launchIsolated(env);
  try {
    const win = await app.firstWindow();
    await win.waitForSelector(".launcher", { timeout: 20_000 });
    await win.waitForSelector(".welcome h1", { timeout: 10_000 });
    await win.waitForTimeout(2_000);

    // Welcome banner should show "Jane Doe"
    const h1 = await win.locator(".welcome h1").textContent();
    expect(h1).toContain("Jane Doe");

    // Saved connection should appear in list
    const connLabel = win.locator(".connection-label").first();
    await expect(connLabel).toBeVisible();
    await expect(connLabel).toHaveText("Local Dev");

    // Connection should be pre-selected (has .selected class)
    const selectedItem = win.locator(".connection-item.selected");
    await expect(selectedItem).toBeVisible();

    // Project root should be pre-filled (last profile)
    const rootDisplay = win.locator(".root-display");
    await expect(rootDisplay).toBeVisible();

    await win.screenshot({
      path: path.join(SCREENSHOTS, "02_returning_user.png"),
      fullPage: true,
    });
  } finally {
    await app.close();
    cleanup(env.userDataDir);
  }
});

// ---------------------------------------------------------------------------
// C3 — Git identity: global gitconfig resolves to name in welcome banner
// ---------------------------------------------------------------------------
test("C3 — Git identity: global gitconfig shown in welcome banner", async () => {
  const env = setupIsolatedEnv({
    settings: emptySettings(),
    gitName: "홍길동",
    gitEmail: "gildong@uengine.org",
  });
  const app = await launchIsolated(env);
  try {
    const win = await app.firstWindow();
    await win.waitForSelector(".launcher", { timeout: 20_000 });
    await win.waitForSelector(".welcome h1", { timeout: 10_000 });
    await win.waitForTimeout(2_000);

    // Welcome banner uses git global config
    const h1 = await win.locator(".welcome h1").textContent();
    expect(h1).toContain("홍길동");

    // Identity source badge visible
    const badge = win.locator(".source-badge");
    await expect(badge).toBeVisible();
    const badgeText = await badge.textContent();
    expect(badgeText).toContain("gildong@uengine.org");

    await win.screenshot({
      path: path.join(SCREENSHOTS, "03_git_identity.png"),
      fullPage: true,
    });
  } finally {
    await app.close();
    cleanup(env.userDataDir);
  }
});

// ---------------------------------------------------------------------------
// C4 — Unknown user: no gitconfig → inline git-config form appears
// ---------------------------------------------------------------------------
test("C4 — Unknown user: no gitconfig shows inline setup form", async () => {
  // No gitName/gitEmail → no .gitconfig in HOME → unknown-fallback
  const env = setupIsolatedEnv({ settings: emptySettings() });
  const app = await launchIsolated(env);
  try {
    const win = await app.firstWindow();
    await win.waitForSelector(".launcher", { timeout: 20_000 });
    await win.waitForSelector(".welcome h1", { timeout: 10_000 });
    await win.waitForTimeout(2_000);

    // Welcome banner shows "unknown user"
    const h1 = await win.locator(".welcome h1").textContent();
    expect(h1?.toLowerCase()).toContain("unknown");

    // Inline git-config form must be visible
    const gitForm = win.locator(".git-identity-form");
    await expect(gitForm).toBeVisible();

    // Form fields present
    await expect(win.locator(".git-identity-fields input[type=text]")).toBeVisible();
    await expect(win.locator(".git-identity-fields input[type=email]")).toBeVisible();

    await win.screenshot({
      path: path.join(SCREENSHOTS, "04_unknown_user.png"),
      fullPage: true,
    });
  } finally {
    await app.close();
    cleanup(env.userDataDir);
  }
});

// ---------------------------------------------------------------------------
// C5 — Web mode: localhost:5173 has no launcher (window.desktop absent)
// ---------------------------------------------------------------------------
test("C5 — Web mode: main SPA loads without launcher", async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1280, height: 800 },
  });
  try {
    await page.goto("http://localhost:5173", { timeout: 15_000, waitUntil: "networkidle" });
    await page.waitForTimeout(2_000);

    // No launcher div should exist in web mode
    const launcher = page.locator(".launcher");
    await expect(launcher).toHaveCount(0);

    // window.desktop should be undefined in web mode
    const hasDesktop = await page.evaluate(() => typeof window.desktop !== "undefined");
    expect(hasDesktop).toBe(false);

    // No console errors about window.desktop
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.screenshot({
      path: path.join(SCREENSHOTS, "05_web_mode.png"),
      fullPage: false,
    });

    // No errors about window.desktop being undefined
    const desktopErrors = consoleErrors.filter((e) => e.includes("desktop"));
    expect(desktopErrors).toHaveLength(0);
  } finally {
    await browser.close();
  }
});
