/**
 * 서비스설계서 파일 이름 규칙 (2026-11-16).
 *
 *   설계_{프로젝트명}_서비스설계서_YYYYMMDD_HHmmss.docx
 *
 * 시각은 **브라우저 현지 시각** — `new Date(y, m, d, h, mi, s)` 로 현지 시각을 만들어
 * 넣으므로 검사 기계의 시간대와 상관없이 같은 값이 나와야 한다. 전에는 `toISOString()`
 * 이라 한국 09시 전엔 전날 날짜가 붙었다.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { serviceDesignDocFileName, sanitizeFileNamePart, formatLocalTimestamp, buildDeliverableFileName } from '../../src/features/exportDocument/fileName.js'

const AT = new Date(2026, 10, 20, 14, 35, 7) // 2026-11-20 14:35:07 현지

test('정상 — 규칙 그대로', () => {
  expect(serviceDesignDocFileName('휴가관리', AT)).toBe('설계_휴가관리_서비스설계서_20261120_143507.docx')
})

test('한 자리 월·일·시·분·초는 0 을 채운다', () => {
  const d = new Date(2027, 0, 5, 3, 4, 9) // 2027-01-05 03:04:09
  expect(formatLocalTimestamp(d)).toBe('20270105_030409')
  expect(serviceDesignDocFileName('P', d)).toBe('설계_P_서비스설계서_20270105_030409.docx')
})

test('현지 자정 직후도 그날 날짜다 — UTC 로 하루 당겨지지 않는다', () => {
  const d = new Date(2026, 10, 20, 0, 10, 0)
  expect(formatLocalTimestamp(d)).toBe('20261120_001000')
})

test('파일명 금지 문자·제어문자는 `_`', () => {
  expect(sanitizeFileNamePart('a\\b/c:d*e?f"g<h>i|j')).toBe('a_b_c_d_e_f_g_h_i_j')
  expect(sanitizeFileNamePart('탭\t줄\n끝\u0000')).toBe('탭_줄_끝_')
  expect(serviceDesignDocFileName('POSCO/ERP:2차', AT)).toBe('설계_POSCO_ERP_2차_서비스설계서_20261120_143507.docx')
})

test('앞뒤 공백·끝의 점은 `_`, 가운데 공백은 그대로', () => {
  expect(sanitizeFileNamePart('  포스코 ERP  ')).toBe('_포스코 ERP_')
  expect(sanitizeFileNamePart('프로젝트v1...')).toBe('프로젝트v1_')
  expect(sanitizeFileNamePart('a.b')).toBe('a.b')
})

test('빈 이름은 `프로젝트`', () => {
  for (const v of [undefined, null, '', '   ']) {
    expect(serviceDesignDocFileName(v, AT)).toBe('설계_프로젝트_서비스설계서_20261120_143507.docx')
  }
})

test('일반형 — 다른 산출물도 docType 만 바꾸면 된다', () => {
  expect(buildDeliverableFileName({ projectName: 'X', docType: 'Aggregate정의서', date: AT }))
    .toBe('설계_X_Aggregate정의서_20261120_143507.docx')
})
