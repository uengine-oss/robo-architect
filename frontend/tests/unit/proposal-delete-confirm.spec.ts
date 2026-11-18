/**
 * Proposal 영구 삭제 확인 비교(A-2 ②).
 *
 * 되돌릴 수 없는 작업이라 엄격 일치는 그대로 둔다 — 앞뒤 공백만 걷는다.
 */
import { expect, test } from '@playwright/test'

// @ts-expect-error 플레인 JS 모듈
import { deleteConfirmMatches, normalizeDeleteConfirm } from '../../src/features/proposals/delete-confirm.js'

test('같은 id 면 켜진다', () => {
  expect(deleteConfirmMatches('PRO-001', 'PRO-001')).toBe(true)
})

test('복사·붙여넣기로 따라 들어온 앞뒤 공백·개행은 걷는다', () => {
  expect(deleteConfirmMatches('  PRO-001\n', 'PRO-001')).toBe(true)
  expect(deleteConfirmMatches('\tPRO-001 ', 'PRO-001')).toBe(true)
  expect(normalizeDeleteConfirm(' PRO-001 ')).toBe('PRO-001')
})

test('엄격 일치는 유지한다 — 대소문자·부분·가운데 공백은 안 켜진다', () => {
  expect(deleteConfirmMatches('pro-001', 'PRO-001')).toBe(false)
  expect(deleteConfirmMatches('PRO-00', 'PRO-001')).toBe(false)
  expect(deleteConfirmMatches('PRO-0011', 'PRO-001')).toBe(false)
  expect(deleteConfirmMatches('PRO- 001', 'PRO-001')).toBe(false)
})

test('빈 값·빈 id 는 늘 꺼져 있다', () => {
  expect(deleteConfirmMatches('', 'PRO-001')).toBe(false)
  expect(deleteConfirmMatches(null, 'PRO-001')).toBe(false)
  expect(deleteConfirmMatches(undefined, 'PRO-001')).toBe(false)
  expect(deleteConfirmMatches('', '')).toBe(false)
  expect(deleteConfirmMatches('x', null)).toBe(false)
})
