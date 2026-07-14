/** 스키마 탭 실물 확인 — 테이블·컬럼이 몇 개나 보이는지. */
import { test } from '@playwright/test'

const OUT = 'D:/work/robo/_ui-verification/schema'

test('스키마 탭 실물', async ({ page }) => {
  test.setTimeout(3 * 60 * 1000)

  await page.goto('/')
  await page.locator('[title="데이터 스키마"]').click()
  await page.waitForTimeout(12_000)
  await page.screenshot({ path: `${OUT}/00-스키마탭-전체.png`, fullPage: true })

  const text = await page.locator('body').innerText()
  console.log('─── 화면 텍스트 (앞 1200자) ───')
  console.log(text.slice(0, 1200))

  // 화면에 뜬 테이블 이름 개수
  const tables = ['comm_code','audit_log','member','member_auth_hst','member_grade_pol',
    'member_ship_addr','product','product_stock','product_price_hst','cart','orders',
    'order_item','order_chk_hst','payment','pg_company','settlement','shipping',
    'delivery_company','shipping_trace','review','point_hst','point_policy']
  const shown = tables.filter(t => new RegExp(`\\b${t}\\b`).test(text))
  console.log(`\n─── DDL 테이블 22개 중 화면에 보이는 것: ${shown.length}개 ───`)
  console.log('  보임 :', shown.join(', '))
  console.log('  안보임:', tables.filter(t => !shown.includes(t)).join(', ') || '(없음)')
})
