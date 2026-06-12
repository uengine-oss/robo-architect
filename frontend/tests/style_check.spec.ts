import { test } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SHOTS = path.resolve(__dirname, '../../specs/038-change-management/manual/screenshots');

test.use({ viewport: { width: 1400, height: 900 } });

test('Changes tab styled', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2500);
  const changesTab = page.getByRole('button', { name: 'Changes' });
  await changesTab.click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${SHOTS}/09_changes_styled.png` });
});

test('Changes item click - detail styled', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  const changesTab = page.getByRole('button', { name: 'Changes' });
  await changesTab.click();
  await page.waitForTimeout(2500);
  const firstItem = page.locator('.cp-item').first();
  if (await firstItem.isVisible()) {
    await firstItem.click();
    await page.waitForTimeout(1500);
  }
  await page.screenshot({ path: `${SHOTS}/10_changes_detail_styled.png` });
});
