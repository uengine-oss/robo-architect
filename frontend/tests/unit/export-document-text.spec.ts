/**
 * 산출물 문서의 **글자 적기** — 자르기와 참/거짓 (2026-10-08).
 *
 * `tests/unit/` 에 둔다 — 그 폴더는 `playwright.unit.config.ts` 가 glob 으로 집으므로
 * **이름을 따로 등록하지 않아도 돈다**(등록을 잊으면 검사가 조용히 사라진다).
 *
 * ## 왜 이 검사가 있나
 *
 * 내보낸 Word 문서를 msa-ez 기준 산출물과 견주다가, 우리 쪽에 **의미가 없어지는 자리**
 * 둘이 있었다. 둘 다 검사가 없었고, **화면 미리보기로는 보이지 않았다** — 화면은
 * 자르지 않기 때문이다.
 *
 * ```
 * ① 설명이 낱말 중간에서 끊겼다   .slice(0, 80) · 말줄임 없음
 * ② false 를 '-'(모른다)로 적었다  isMultipleResult || '-'
 * ```
 *
 * 아래 문자열은 꾸민 것이 아니라 **기준 프로젝트(`prj_16972790c0`) 의 실제 값**이다.
 * 어제 배운 것이 그것이었다 — 상상한 값으로 재면 결함을 재현하지 못한다.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { clip, resultKind } from '../../src/features/exportDocument/text.js'

/** 실제 BC 설명 — 178자. 80자에서 자르면 `approval lin` 으로 끊긴다. */
const REAL_BC_DESC =
  'Manages the approval workflow for leave requests, including dynamic approval line generation, ' +
  'approval/rejection actions, and maintaining approval history and status transitions.'

/** 실제 Read Model 설명 — 167자. */
const REAL_RM_DESC =
  'Detailed information about the dynamically generated approval line for a specific leave request, ' +
  'including each step, approver, and the current state of that step.'

test('낱말 중간에서 끊지 않는다 — 실제 BC 설명 178자', () => {
  expect(REAL_BC_DESC.length).toBe(178)
  // 고치기 전에 문서에 들어갔던 모습 — 이것이 결함이다.
  expect(REAL_BC_DESC.slice(0, 80)).toBe(
    'Manages the approval workflow for leave requests, including dynamic approval lin',
  )

  const out = clip(REAL_BC_DESC, 120)
  expect(out.endsWith('…')).toBe(true)
  // 말줄임을 뗀 몸통이 **공백에서 끝난 자리**여야 한다 = 낱말이 안 쪼개졌다.
  const body = out.slice(0, -1)
  expect(REAL_BC_DESC.startsWith(body)).toBe(true)
  expect(REAL_BC_DESC[body.length]).toBe(' ')
  expect(body.length).toBeLessThanOrEqual(120)
})

test('짧은 것은 **건드리지 않는다** — 말줄임도 안 붙인다', () => {
  expect(clip('짧다', 120)).toBe('짧다')
  expect(clip(REAL_RM_DESC, 300)).toBe(REAL_RM_DESC)
})

test('빈 값은 `-` 다 — 빈 칸은 "자리가 없는 것" 과 구별되지 않는다', () => {
  expect(clip(undefined, 80)).toBe('-')
  expect(clip(null, 80)).toBe('-')
  expect(clip('   ', 80)).toBe('-')
})

test('공백이 없는 한 덩이도 **자르고 말줄임을 붙인다** — 한글 설명이 그렇다', () => {
  const korean = '휴가신청의생성검증취소를포함한전체생애주기를관리한다'.repeat(6)
  const out = clip(korean, 30)
  expect(out.endsWith('…')).toBe(true)
  expect(out.length).toBe(31)
})

test('`false` 는 **단건이라는 사실**이다 — `-`(모른다)로 적지 않는다', () => {
  expect(resultKind(false)).toBe('단건')
  expect(resultKind(true)).toBe('다건')
  // 고치기 전 코드가 하던 것 — 둘이 같아져 **사실이 사라졌다**.
  expect(false || '-').toBe('-')
  expect(resultKind(false)).not.toBe(resultKind(null))
})

test('모르는 것은 `-` 로 남긴다 — 모르는 것을 아는 척하지 않는다', () => {
  expect(resultKind(null)).toBe('-')
  expect(resultKind(undefined)).toBe('-')
  expect(resultKind('')).toBe('-')
})

test('이미 사람 말로 적힌 값은 그대로 둔다 — 두 번 바꾸지 않는다', () => {
  // 화면 쪽은 `getReadModelsFromTree` 에서 한 번 바꿔 문자열로 들고 있다.
  expect(resultKind('단건')).toBe('단건')
  expect(resultKind('다건')).toBe('다건')
})
