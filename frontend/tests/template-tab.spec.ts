import { expect, test } from '@playwright/test'

/**
 * Template 탭이 실제로 그려지는지 본다.
 *
 * 빌드 통과만으로는 부족하다. 재귀 트리를 런타임 `template:` 문자열로 두면
 * 빌드는 지나가고 **실행할 때만** "runtime compilation is not supported" 가
 * 나면서 트리가 통째로 비어 버린다. 그래서 여기서는 콘솔 경고도 함께 본다.
 */
test('Template 탭 — 코드 생성이 트리와 뷰어를 그린다', async ({ page }) => {
  const warnings: string[] = []
  page.on('console', (m) => {
    const t = m.text()
    if (/runtime compilation is not supported|\[Vue warn\]/.test(t)) warnings.push(t)
  })
  page.on('pageerror', (e) => warnings.push(`pageerror: ${e.message}`))

  await page.goto('/')
  await page.getByRole('button', { name: 'Template', exact: true }).click()

  // 옵션 항목은 템플릿의 `_template/configuration.html` 이 선언한다.
  // 화면이 지어내면 안 되므로 그 파일의 label 이 그대로 보이는지 본다.
  await expect(page.locator('.tpl__field label', { hasText: '서비스 ID' })).toBeVisible()
  const serviceId = page.locator('.tpl__field input')
  await expect(serviceId).toBeVisible()
  await serviceId.fill('sample')

  await page.getByRole('button', { name: '코드 생성' }).click()

  // 트리가 그려진다 — 노드가 하나도 없으면 재귀 컴포넌트가 죽은 것이다.
  const rows = page.locator('.tpl__tree button')
  await expect(rows.first()).toBeVisible({ timeout: 60_000 })
  expect(await rows.count()).toBeGreaterThan(3)

  // 최상위는 BC 이름이어야 한다.
  await expect(page.locator('.tpl__tree button').first()).toContainText(/[a-zA-Z]/)

  // 디렉터리를 펼치면 자식이 늘어난다.
  const before = await rows.count()
  await rows.first().click()          // 접기
  expect(await rows.count()).toBeLessThan(before)
  await rows.first().click()          // 다시 펼치기
  expect(await rows.count()).toBe(before)

  // 파일·폴더 아이콘이 붙는다. 폴더는 SVG, 파일은 확장자 배지다.
  await expect(page.locator('.tpl__tree svg.fi--folder').first()).toBeVisible()
  const badges = page.locator('.tpl__tree span.fi--badge')
  expect(await badges.count()).toBeGreaterThan(0)

  // 뷰어에 코드가 보인다.
  await expect(page.locator('.gv .cm-content')).toBeVisible()
  await expect(page.locator('.gv__path')).not.toBeEmpty()

  // 설정 파일은 생성물이 아니다 — 결과 트리에 섞이면 안 된다.
  await expect(page.locator('.tpl__tree button', { hasText: '_template' })).toHaveCount(0)
  await expect(page.locator('.tpl__tree button', { hasText: 'configuration.html' })).toHaveCount(0)

  // 확장자별 구분이 실제로 먹는지 본다. 최상위에 있는 두 파일로 확인한다 —
  // 깊이 파고들면 트리 접힘 상태에 기대게 되어 잘 깨진다.
  //
  // `if (count)` 로 감싸지 않는다. 감싸면 대상이 없을 때 조용히 지나가고
  // 검사가 공회전한다 — 실제로 한 번 그렇게 썼다가 놓쳤다.
  const rowByText = (t: string) => page.locator('.tpl__tree button', { hasText: t }).first()
  await expect(rowByText('pom.xml').locator('span.fi--badge')).toHaveText('X')
  await expect(rowByText('README.md').locator('span.fi--badge')).toHaveText('MD')

  // ZIP 버튼이 살아난다.
  await expect(page.getByRole('button', { name: /ZIP 내려받기/ })).toBeEnabled()

  expect(warnings, `Vue 경고/오류:\n${warnings.join('\n')}`).toEqual([])
})
