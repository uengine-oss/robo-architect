/**
 * Smoke test for the Electron shell.
 *
 * Phase 2 (T012) skeleton: launches the (dev) app and asserts a window opens.
 * T030 (US1) extends this to cover:
 *   - single-instance behaviour (second launch focuses the first)
 *   - backend reaches `ready`
 *   - the `app://` window loads the SPA
 *   - a clean quit leaves 0 app-owned child processes (SC-003)
 *
 * Run from the desktop/ directory:  `npm test`
 */

import { _electron as electron, expect, test } from "@playwright/test";
import path from "node:path";

const APP_ROOT = path.resolve(__dirname, "..");

test("electron app launches and opens a window", async () => {
  const app = await electron.launch({ args: [APP_ROOT] });
  try {
    const window = await app.firstWindow();
    expect(window).toBeTruthy();
    // The Phase-2 stub loads `about:blank`; assert we got *some* URL back.
    const url = window.url();
    expect(typeof url).toBe("string");
    expect(url.length).toBeGreaterThan(0);
  } finally {
    await app.close();
  }
});
