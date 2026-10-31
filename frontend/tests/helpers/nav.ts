// 화면 전환 공용 도우미 — 상단 탭 막대(.top-bar__tab, 'Proposals'/'Requirements' 영문 버튼)는 없어지고
// 왼쪽 레일(src/app/layout/SideRail.vue, nav.rail · .rail__item · 한국어 이름)로 옮겨졌다.
// 시험은 화면 이름(레일 글자)으로 옮겨 다닌다: await gotoView(page, '프로포절')
import { expect, type Page } from '@playwright/test'

export type RailView = '프로포절' | '요구사항' | '프로세스' | '설계' | '데이터' | '코드' | '레거시'

/** 레일 단추 하나(화면 이름과 정확히 같은 것). */
export function railItem(page: Page, label: RailView) {
  return page
    .getByRole('navigation', { name: '화면' })
    .locator('.rail__item')
    .filter({ has: page.getByText(label, { exact: true }) })
}

/**
 * 레일에서 화면을 고른다. 고른 단추가 켜질(is-active) 때까지 기다린다.
 * '코드' 는 프로젝트 홈(localStorage claude_code_workspace_root)이 없으면 화면 대신 PRD 창을 연다 —
 * 그 경우를 시험하려면 { expectActive: false } 로 부른다.
 */
export async function gotoView(page: Page, label: RailView, { expectActive = true } = {}) {
  const item = railItem(page, label)
  await item.click()
  if (expectActive) await expect(item).toHaveClass(/is-active/)
}

/** 프로세스 화면의 Event Modeling 쪽(상단 서브토글 'Event Modeling'). */
export async function gotoEventModeling(page: Page) {
  await gotoView(page, '프로세스')
  const seg = page.locator('.top-bar__seg', { hasText: 'Event Modeling' })
  await seg.click()
  await expect(seg).toHaveClass(/is-active/)
}
