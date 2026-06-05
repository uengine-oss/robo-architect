import { test } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SHOTS = path.resolve(__dirname, '../../specs/038-change-management/manual/screenshots');

test.use({ viewport: { width: 1400, height: 900 } });

test('new nav menu', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2500);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `${SHOTS}/07_new_nav_menu.png` });
});

test('Changes tab as top level', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  const changesTab = page.getByRole('button', { name: 'Changes' });
  await changesTab.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SHOTS}/08_changes_as_top_tab.png` });
});
