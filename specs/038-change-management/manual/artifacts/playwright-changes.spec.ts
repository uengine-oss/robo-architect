import { test, expect } from '@playwright/test';
import path from 'path';

const SHOTS = path.resolve(__dirname, '../screenshots');
const APP = process.env.APP_URL || 'http://localhost:5173';

test.use({ viewport: { width: 1400, height: 900 } });

test.describe('038 — Requirement Change Management', () => {

  test('01 — Requirements 탭 초기 화면', async ({ page }) => {
    await page.goto(APP);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Requirements 탭 클릭
    const reqTab = page.getByRole('tab', { name: /요구사항|Requirement/i }).first();
    if (await reqTab.isVisible()) {
      await reqTab.click();
      await page.waitForTimeout(1500);
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `${SHOTS}/01_requirements_initial.png` });
  });

  test('02 — Changes 버튼 클릭 → Changes 패널 표시', async ({ page }) => {
    await page.goto(APP);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Requirements 탭으로 이동
    const reqTab = page.getByRole('tab', { name: /요구사항|Requirement/i }).first();
    if (await reqTab.isVisible()) {
      await reqTab.click();
      await page.waitForTimeout(1000);
    }

    // 🔄 Changes 버튼 찾아 클릭
    const changesBtn = page.getByRole('button', { name: /Changes/i });
    if (await changesBtn.isVisible()) {
      await changesBtn.click();
      await page.waitForTimeout(2000);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: `${SHOTS}/02_changes_panel_open.png` });
    } else {
      // Changes 버튼이 없으면 전체 화면 캡처
      await page.screenshot({ path: `${SHOTS}/02_changes_panel_open.png` });
    }
  });

  test('03 — Changes 목록 표시', async ({ page }) => {
    await page.goto(APP);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    // Requirements 탭으로 이동
    const reqTab = page.getByRole('tab', { name: /요구사항|Requirement/i }).first();
    if (await reqTab.isVisible()) {
      await reqTab.click();
      await page.waitForTimeout(1000);
    }

    // Changes 패널 열기
    const changesBtn = page.getByRole('button', { name: /Changes/i });
    if (await changesBtn.isVisible()) {
      await changesBtn.click();
      await page.waitForTimeout(2500);
    }

    // Changes 목록 영역 캡처
    const changesList = page.locator('.changes-list').first();
    if (await changesList.isVisible()) {
      await changesList.screenshot({ path: `${SHOTS}/03_changes_list.png` });
    } else {
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: `${SHOTS}/03_changes_list.png` });
    }
  });

  test('04 — 추가 Change 다이얼로그', async ({ page }) => {
    await page.goto(APP);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const reqTab = page.getByRole('tab', { name: /요구사항|Requirement/i }).first();
    if (await reqTab.isVisible()) {
      await reqTab.click();
      await page.waitForTimeout(1000);
    }

    const changesBtn = page.getByRole('button', { name: /Changes/i });
    if (await changesBtn.isVisible()) {
      await changesBtn.click();
      await page.waitForTimeout(2000);
    }

    // 추가 Change 버튼 클릭
    const addBtn = page.getByRole('button', { name: /추가 Change/i });
    if (await addBtn.isVisible()) {
      await addBtn.click();
      await page.waitForTimeout(1000);
      // 다이얼로그 캡처
      const dialog = page.locator('.v-dialog, [role="dialog"]').first();
      if (await dialog.isVisible()) {
        await dialog.screenshot({ path: `${SHOTS}/04_add_change_dialog.png` });
      } else {
        await page.screenshot({ path: `${SHOTS}/04_add_change_dialog.png` });
      }
    } else {
      await page.screenshot({ path: `${SHOTS}/04_add_change_dialog.png` });
    }
  });

  test('05 — Change 상세 화면 (상태 이력 포함)', async ({ page }) => {
    await page.goto(APP);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const reqTab = page.getByRole('tab', { name: /요구사항|Requirement/i }).first();
    if (await reqTab.isVisible()) {
      await reqTab.click();
      await page.waitForTimeout(1000);
    }

    const changesBtn = page.getByRole('button', { name: /Changes/i });
    if (await changesBtn.isVisible()) {
      await changesBtn.click();
      await page.waitForTimeout(2500);
    }

    // 첫 번째 Change 항목 클릭
    const firstItem = page.locator('.change-item').first();
    if (await firstItem.isVisible()) {
      await firstItem.click();
      await page.waitForTimeout(1500);
      // Change 상세 패널 캡처
      const detail = page.locator('.change-detail').first();
      if (await detail.isVisible()) {
        await detail.screenshot({ path: `${SHOTS}/05_change_detail.png` });
      } else {
        await page.screenshot({ path: `${SHOTS}/05_change_detail.png` });
      }
    } else {
      await page.screenshot({ path: `${SHOTS}/05_change_detail.png` });
    }
  });

  test('06 — Changes 패널 전체 (목록 + 상세)', async ({ page }) => {
    await page.goto(APP);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(2000);

    const reqTab = page.getByRole('tab', { name: /요구사항|Requirement/i }).first();
    if (await reqTab.isVisible()) {
      await reqTab.click();
      await page.waitForTimeout(1000);
    }

    const changesBtn = page.getByRole('button', { name: /Changes/i });
    if (await changesBtn.isVisible()) {
      await changesBtn.click();
      await page.waitForTimeout(2500);
    }

    // 첫 번째 아이템 클릭
    const firstItem = page.locator('.change-item').first();
    if (await firstItem.isVisible()) {
      await firstItem.click();
      await page.waitForTimeout(1500);
    }

    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `${SHOTS}/06_changes_full_view.png` });
  });
});
