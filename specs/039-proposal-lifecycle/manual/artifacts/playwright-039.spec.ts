import { test, expect } from '@playwright/test';
import path from 'path';

const SHOTS = path.resolve(__dirname, '../../screenshots');
const APP = process.env.APP_URL || 'http://localhost:5173';

test.use({ viewport: { width: 1400, height: 900 } });

test('01 — 앱 초기 화면 (Proposals 탭 진입)', async ({ page }) => {
  await page.goto(APP);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);

  // Proposals 탭 클릭
  const proposalsTab = page.getByRole('button', { name: 'Proposals' })
    .or(page.locator('.top-bar__tab').filter({ hasText: 'Proposals' }));
  await proposalsTab.first().click();
  await page.waitForTimeout(1000);

  // 전체 앱 화면 (탑바 포함)
  await page.screenshot({ path: `${SHOTS}/01_proposals_tab_initial.png` });
});

test('02 — Proposals 탭 패널 (목록 영역)', async ({ page }) => {
  await page.goto(APP);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);

  // Proposals 탭으로 이동
  const proposalsTab = page.locator('.top-bar__tab').filter({ hasText: 'Proposals' });
  await proposalsTab.first().click();
  await page.waitForTimeout(1200);

  // ProposalsPanel 영역 캡처
  const panel = page.locator('.proposals-panel').first();
  if (await panel.isVisible()) {
    await panel.screenshot({ path: `${SHOTS}/02_proposals_panel.png` });
  } else {
    await page.screenshot({ path: `${SHOTS}/02_proposals_panel.png` });
  }
});

test('03 — 새 Proposal 생성 다이얼로그', async ({ page }) => {
  await page.goto(APP);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);

  // Proposals 탭
  const proposalsTab = page.locator('.top-bar__tab').filter({ hasText: 'Proposals' });
  await proposalsTab.first().click();
  await page.waitForTimeout(1000);

  // '+ 새 Proposal' 버튼 클릭
  const createBtn = page.getByRole('button', { name: /새 Proposal/ })
    .or(page.locator('button').filter({ hasText: '새 Proposal' }));
  await createBtn.first().click();
  await page.waitForTimeout(800);

  // 다이얼로그/Create 폼 캡처
  const wrapper = page.locator('.create-wrapper').first();
  const inner = page.locator('.proposal-create').first();
  const dialog = await wrapper.isVisible() ? wrapper : inner;
  if (await dialog.isVisible()) {
    await dialog.screenshot({ path: `${SHOTS}/03_proposal_create_dialog.png` });
  } else {
    await page.screenshot({ path: `${SHOTS}/03_proposal_create_dialog.png` });
  }
});

test('04 — 자연어 입력 후 AI 분석 시작', async ({ page }) => {
  await page.goto(APP);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);

  // Proposals 탭
  const proposalsTab = page.locator('.top-bar__tab').filter({ hasText: 'Proposals' });
  await proposalsTab.first().click();
  await page.waitForTimeout(800);

  // 새 Proposal 다이얼로그 열기
  const createBtn = page.locator('button').filter({ hasText: '새 Proposal' });
  await createBtn.first().click();
  await page.waitForTimeout(600);

  // 자연어 입력
  const textarea = page.locator('textarea').first();
  await textarea.fill('결제 시스템에 부분 환불 기능을 추가해줘. 고객이 주문 금액의 일부만 환불 요청할 수 있어야 해.');
  await page.waitForTimeout(300);

  // 입력 후 폼 상태 캡처
  const createArea = page.locator('.proposal-create').first();
  if (await createArea.isVisible()) {
    await createArea.screenshot({ path: `${SHOTS}/04_proposal_input_filled.png` });
  } else {
    await page.screenshot({ path: `${SHOTS}/04_proposal_input_filled.png` });
  }
});

test('05 — 상태 필터 탭 동작', async ({ page }) => {
  await page.goto(APP);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(1500);

  // Proposals 탭
  const proposalsTab = page.locator('.top-bar__tab').filter({ hasText: 'Proposals' });
  await proposalsTab.first().click();
  await page.waitForTimeout(1200);

  // DRAFT 필터 탭 클릭
  const draftFilter = page.locator('.status-tab').filter({ hasText: 'DRAFT' }).first();
  if (await draftFilter.isVisible()) {
    await draftFilter.click();
    await page.waitForTimeout(600);
  }

  // 필터 상태 패널 캡처
  const panel = page.locator('.proposals-panel').first();
  if (await panel.isVisible()) {
    await panel.screenshot({ path: `${SHOTS}/05_proposals_status_filter.png` });
  } else {
    await page.screenshot({ path: `${SHOTS}/05_proposals_status_filter.png` });
  }
});
