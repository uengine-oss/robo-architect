import { test, expect } from '@playwright/test';

test('impact tree after analysis', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForTimeout(2000);
  
  // Go to Changes tab
  await page.locator('button').filter({ hasText: 'Changes' }).first().click();
  await page.waitForTimeout(1200);
  
  // Click CHG-009 (SUBMITTED - likely has prompt for analysis)
  await page.locator('.cp-item').filter({ hasText: 'CHG-009' }).first().click();
  await page.waitForTimeout(1000);
  
  // Click 영향도 tab
  await page.locator('.cd-tab').filter({ hasText: '영향도' }).first().click();
  await page.waitForTimeout(1000);
  
  // Click 분석 시작 or 재분석
  const analyzeBtn = page.locator('button').filter({ hasText: /분석 시작|재분석/ }).first();
  const btnVisible = await analyzeBtn.isVisible().catch(() => false);
  console.log('Analyze button visible:', btnVisible);
  
  if (btnVisible) {
    await analyzeBtn.click();
    console.log('Clicked analyze button, waiting for SSE...');
    // Wait up to 60 seconds for analysis to complete
    await page.waitForSelector('.civ-root-node', { timeout: 90000 }).catch(() => {
      console.log('civ-root-node not found within timeout');
    });
  }
  
  await page.screenshot({ path: '/tmp/verify-07-impact-analyzed.png', fullPage: false });
  
  const rootNode = page.locator('.civ-root-node');
  const layerBlocks = page.locator('.civ-layer');
  const rootVisible = await rootNode.isVisible().catch(() => false);
  const layerCount = await layerBlocks.count();
  
  console.log('Root node visible:', rootVisible);
  console.log('Layer count:', layerCount);
  
  for (let i = 0; i < layerCount; i++) {
    const headerText = await layerBlocks.nth(i).locator('.civ-layer__name').textContent().catch(() => '?');
    const nodeCount = await layerBlocks.nth(i).locator('.civ-node').count();
    console.log(`Layer ${i}: "${headerText}" — ${nodeCount} nodes`);
  }
  
  // Click first node to see reason expand
  const nodeCards = page.locator('.civ-node');
  if (await nodeCards.count() > 0) {
    await nodeCards.first().click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: '/tmp/verify-08-node-expanded.png', fullPage: false });
    console.log('Clicked first node card');
  }
});
