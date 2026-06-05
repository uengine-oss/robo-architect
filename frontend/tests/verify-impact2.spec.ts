import { test, expect } from '@playwright/test';

test('impact hierarchical tree rendering', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.waitForTimeout(2000);
  
  // Navigate to Changes tab
  await page.locator('button').filter({ hasText: 'Changes' }).first().click();
  await page.waitForTimeout(1200);

  // Click on CHG-008 (APPROVED - likely has effect data)
  await page.locator('.cp-item').filter({ hasText: 'CHG-008' }).first().click();
  await page.waitForTimeout(1000);
  await page.screenshot({ path: '/tmp/verify-04-change-selected.png', fullPage: false });
  
  // Click 영향도 tab
  await page.locator('.cd-tab').filter({ hasText: '영향도' }).first().click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: '/tmp/verify-05-impact-tab.png', fullPage: false });
  
  // Check for hierarchical elements
  const rootNode = page.locator('.civ-root-node');
  const layerBlocks = page.locator('.civ-layer');
  const connector = page.locator('.civ-connector');
  
  const rootVisible = await rootNode.isVisible().catch(() => false);
  const layerCount = await layerBlocks.count();
  const connectorCount = await connector.count();
  
  console.log('Root node visible:', rootVisible);
  console.log('Layer count:', layerCount);
  console.log('Connector count:', connectorCount);
  
  // Check layer labels
  for (let i = 0; i < layerCount; i++) {
    const layerText = await layerBlocks.nth(i).locator('.civ-layer__name').textContent();
    console.log('Layer', i, ':', layerText);
  }
  
  // Click a node card to expand reason
  const nodeCards = page.locator('.civ-node');
  const nodeCount = await nodeCards.count();
  console.log('Node cards count:', nodeCount);
  if (nodeCount > 0) {
    await nodeCards.first().click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: '/tmp/verify-06-node-expanded.png', fullPage: false });
    const reason = page.locator('.civ-node__reason');
    const reasonVisible = await reason.isVisible().catch(() => false);
    console.log('Reason visible after click:', reasonVisible);
  }
});
