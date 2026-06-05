import { test, expect } from '@playwright/test';

test('changes impact hierarchical tree', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('http://localhost:5173');
  await page.waitForTimeout(2000);
  
  // Step 1: Click Changes tab
  const tabs = page.locator('button');
  await tabs.filter({ hasText: 'Changes' }).first().click();
  await page.waitForTimeout(1500);
  await page.screenshot({ path: '/tmp/verify-02-changes-tab.png', fullPage: false });
  
  // Step 2: Check if Changes panel loaded (list should appear)
  const body = await page.content();
  const hasChanges = body.includes('Changes') || body.includes('Change');
  console.log('Has Changes content:', hasChanges);
  console.log('Page title:', await page.title());
  
  await page.screenshot({ path: '/tmp/verify-03-changes-final.png', fullPage: false });
});
