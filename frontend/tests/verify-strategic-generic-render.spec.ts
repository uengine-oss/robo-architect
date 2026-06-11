import { test, expect } from '@playwright/test'

/**
 * Strategic Diff 렌더링이 (1) 1급 카테고리 Process를 명시적으로 표시하고
 * (2) 프로젝트별 맞춤 스킬이 추가한 미지의 카테고리(예: policies)를 제네릭하게
 * 렌더링하는지 검증한다. intent 스킬(LLM)을 거치지 않고 proposal API 응답을
 * fixture로 가로채 결정론적으로 확인한다.
 */

const PROPOSAL_ID = 'PRO-GEN1'

const SUMMARY = {
  id: PROPOSAL_ID,
  title: '제네릭 전략 카테고리 렌더 검증',
  status: 'DRAFT',
  author: 'tester',
  createdAt: '2026-06-10T00:00:00Z',
  originalPrompt: '부분 환불 + 프로세스 변경 + 커스텀 정책 카테고리',
  impactMap: [],
}

const DETAIL = {
  ...SUMMARY,
  statusHistory: [],
  strategicDiff: {
    version: 1,
    epics: [],
    features: [{ op: 'CREATE', entityType: 'feature', entityTitle: '부분 환불 요청' }],
    userStories: [{ op: 'CREATE', entityType: 'userStory', entityTitle: '고객이 일부 금액 환불을 요청' }],
    // 1급(고착) Process 카테고리
    processes: [
      {
        op: 'MODIFY',
        entityType: 'process',
        entityId: 'PROC-refund',
        entityTitle: '환불 처리 프로세스',
        fields: { steps: { before: '요청→승인→정산', after: '요청→부분검증→승인→정산' } },
      },
    ],
    // 미지/제네릭 카테고리 — 코드 수정 없이 렌더되어야 함
    policies: [{ op: 'CREATE', entityType: 'policy', entityTitle: '부분환불 한도 정책' }],
  },
  tacticalDiff: [],
  projectRoot: null,
}

test('Strategic Diff: Process(1급) + 미지 카테고리(policies) 제네릭 렌더', async ({ page }) => {
  // proposal API 가로채기 (list + detail)
  await page.route('**/api/proposals/**', async (route) => {
    const url = route.request().url()
    // 상세: /api/proposals/PRO-GEN1
    if (new RegExp(`/api/proposals/${PROPOSAL_ID}(\\?|$)`).test(url)) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(DETAIL) })
    }
    // 목록: /api/proposals/ 또는 /api/proposals/?...
    if (/\/api\/proposals\/(\?|$)/.test(url)) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([SUMMARY]) })
    }
    return route.continue()
  })

  await page.goto('http://localhost:5173')
  await page.waitForLoadState('networkidle')

  // Proposals 탭 진입
  const proposalsTab = page.locator('text=Proposals').first()
  await proposalsTab.waitFor({ timeout: 10000 })
  await proposalsTab.click()

  // 목록에서 fixture proposal 클릭
  const item = page.locator(`.proposal-item:has-text("${PROPOSAL_ID}")`).first()
  await item.waitFor({ timeout: 5000 })
  await item.click()

  // Strategic + Tactical Diff 탭이 기본 활성. diff 그룹이 렌더될 때까지 대기.
  const intentView = page.locator('.intent-view')
  await intentView.waitFor({ timeout: 5000 })

  // 그룹 제목 수집
  const headings = await intentView.locator('.diff-group h5').allTextContents()
  console.log('diff-group 제목:', headings)

  // (1) 1급 Process 그룹과 항목
  expect(headings).toContain('Process')
  await expect(intentView.getByText('환불 처리 프로세스')).toBeVisible()

  // (2) 미지 카테고리 policies → prettyLabel "Policies" 로 제네릭 렌더
  expect(headings).toContain('Policies')
  await expect(intentView.getByText('부분환불 한도 정책')).toBeVisible()

  // 기존 1급도 유지
  expect(headings).toContain('Feature')
  expect(headings).toContain('User Story')

  await page.screenshot({ path: 'test-results/strategic-generic-render.png', fullPage: true })
})
