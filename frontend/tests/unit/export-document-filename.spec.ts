/**
 * 산출물 파일 이름 — 틀(고객 확장 값)과 코어 기본 이름.
 *
 * 포스코 틀(`extensions/posco/frontend/index.js` 의 `deliverables.fileNameTemplate`):
 *   설계_{프로젝트명}_서비스설계서_YYYYMMDD_HHmmss.docx
 *
 * 시각은 **브라우저 현지 시각** — `new Date(y, m, d, h, mi, s)` 로 현지 시각을 만들어
 * 넣으므로 검사 기계의 시간대와 상관없이 같은 값이 나와야 한다. 전에는 `toISOString()`
 * 이라 한국 09시 전엔 전날 날짜가 붙었다.
 *
 * 틀이 없으면(기본 빌드) 코어 기본 이름 `설계산출물-YYYY-MM-DD.docx` (옛 형식, UTC 날짜).
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { serviceDesignDocFileName, sanitizeFileNamePart, formatLocalTimestamp, buildDeliverableFileName, legacyFileName } from '../../src/features/exportDocument/fileName.js'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// 포스코 틀은 확장 파일에서 **글자로** 읽는다 — 확장 폴더에는 package.json(type: module)이
// 없어 시험 러너가 ES 모듈로 불러오지 못한다. 틀을 시험에 베껴 두면 확장 값이 바뀌어도 모른다.
const POSCO_EXT = fileURLToPath(new URL('../../../extensions/posco/frontend/index.js', import.meta.url))
const TEMPLATE = (readFileSync(POSCO_EXT, 'utf8').match(/fileNameTemplate:\s*'([^']+)'/) || [])[1] as string
const AT = new Date(2026, 10, 20, 14, 35, 7) // 2026-11-20 14:35:07 현지
const name = (project: unknown, date = AT) => serviceDesignDocFileName(project, { template: TEMPLATE, date })

test('포스코 틀 — 규칙 그대로', () => {
  expect(TEMPLATE).toBe('설계_{project}_{kind}_{yyyyMMdd}_{HHmmss}')
  expect(name('휴가관리')).toBe('설계_휴가관리_서비스설계서_20261120_143507.docx')
})

test('한 자리 월·일·시·분·초는 0 을 채운다', () => {
  const d = new Date(2027, 0, 5, 3, 4, 9) // 2027-01-05 03:04:09
  expect(formatLocalTimestamp(d)).toBe('20270105_030409')
  expect(name('P', d)).toBe('설계_P_서비스설계서_20270105_030409.docx')
})

test('현지 자정 직후도 그날 날짜다 — UTC 로 하루 당겨지지 않는다', () => {
  const d = new Date(2026, 10, 20, 0, 10, 0)
  expect(formatLocalTimestamp(d)).toBe('20261120_001000')
  expect(name('P', d)).toBe('설계_P_서비스설계서_20261120_001000.docx')
})

test('파일명 금지 문자·제어문자는 `_`', () => {
  expect(sanitizeFileNamePart('a\\b/c:d*e?f"g<h>i|j')).toBe('a_b_c_d_e_f_g_h_i_j')
  expect(sanitizeFileNamePart('탭\t줄\n끝\u0000')).toBe('탭_줄_끝_')
  expect(name('POSCO/ERP:2차')).toBe('설계_POSCO_ERP_2차_서비스설계서_20261120_143507.docx')
})

test('앞뒤 공백·끝의 점은 `_`, 가운데 공백은 그대로', () => {
  expect(sanitizeFileNamePart('  포스코 ERP  ')).toBe('_포스코 ERP_')
  expect(sanitizeFileNamePart('프로젝트v1...')).toBe('프로젝트v1_')
  expect(sanitizeFileNamePart('a.b')).toBe('a.b')
})

test('빈 이름은 `프로젝트`', () => {
  for (const v of [undefined, null, '', '   ']) {
    expect(name(v)).toBe('설계_프로젝트_서비스설계서_20261120_143507.docx')
  }
})

test('일반형 — 다른 산출물도 kind 만 바꾸면 된다', () => {
  expect(buildDeliverableFileName({ template: TEMPLATE, projectName: 'X', kind: 'Aggregate정의서', date: AT }))
    .toBe('설계_X_Aggregate정의서_20261120_143507.docx')
})

test('틀에 모르는 칸은 그대로 남는다', () => {
  expect(buildDeliverableFileName({ template: '{project}-{nope}', projectName: 'X', kind: 'k', date: AT }))
    .toBe('X-{nope}.docx')
})

test('틀이 없으면 코어 기본 이름(옛 형식, UTC 날짜)', () => {
  const d = new Date(Date.UTC(2026, 10, 19, 23, 30, 0)) // UTC 11-19 23:30
  expect(serviceDesignDocFileName('휴가관리', { date: d })).toBe('설계산출물-2026-11-19.docx')
  expect(serviceDesignDocFileName('휴가관리', { template: null, date: d })).toBe('설계산출물-2026-11-19.docx')
  expect(legacyFileName('Aggregate정의서', 'docx', d)).toBe('Aggregate정의서-2026-11-19.docx')
})
