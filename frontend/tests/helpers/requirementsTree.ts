// 요구사항 화면 트리(RequirementsTree.vue) 도우미.
// 034 이후 트리에서 이름을 누르면 그 노드를 고르고(오른쪽 상세) 펼치지는 않는다 — 펼침은 ▸(caret).
import type { Page } from '@playwright/test'

/** 이름이 정확히 같은 트리 행의 ▸ 를 눌러 펼친다(아무것도 고르지 않는다). */
export async function expandTreeNode(page: Page, label: string) {
  const row = page
    .locator('.req-tree .tree-row')
    .filter({ has: page.locator('.node-label').getByText(label, { exact: true }) })
    .first()
  await row.locator('.caret').click()
}
