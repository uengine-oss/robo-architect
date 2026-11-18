/**
 * 왼쪽 레일 → 새 탭 (라이트 지적 C-1 ④, `src/app/layout/railTabs.js`).
 *
 * 재는 것: **lite 탭 창에서만** 새 탭이고, 웹 판·enterprise 는 지금 동작(제자리)을 지킨다.
 */

import { expect, test } from '@playwright/test'

import {
  _resetShellTabsDetection,
  detectShellTabs,
  railTabTarget,
  wantsInPlace,
} from '../../src/app/layout/railTabs'

const state = (desktopProfile: string) => ({ ok: true, data: { desktopProfile } })
const win = (profile: string | null, withShell = true) => ({
  ...(withShell ? { raShell: { openTab: async () => 't1' } } : {}),
  ...(profile ? { desktop: { app: { getRuntimeState: async () => state(profile) } } } : {}),
})

test.beforeEach(() => _resetShellTabsDetection())

test.describe('detectShellTabs — 판·프로필 가르기', () => {
  test('웹 판(window.desktop 없음)은 탭이 아니다', async () => {
    expect(await detectShellTabs({} as never)).toBe(false)
  })

  test('enterprise 는 raShell 이 있어도 탭이 아니다 — 처리기가 없다', async () => {
    expect(await detectShellTabs(win('enterprise') as never)).toBe(false)
  })

  test('lite 탭 창이면 탭이다', async () => {
    expect(await detectShellTabs(win('lite') as never)).toBe(true)
  })

  test('getRuntimeState 가 터지면 모른다 → 지금 동작', async () => {
    const broken = { raShell: { openTab: async () => 't1' }, desktop: { app: { getRuntimeState: async () => { throw new Error('x') } } } }
    expect(await detectShellTabs(broken as never)).toBe(false)
  })
})

test.describe('railTabTarget', () => {
  test('lite: 다른 화면은 reuse 새 탭', () => {
    expect(railTabTarget({ tab: 'Design', current: false, shellTabs: true })).toEqual({ view: 'Design', reuse: true })
  })

  test('Ctrl/⌘-클릭은 제자리', () => {
    expect(railTabTarget({ tab: 'Design', current: false, shellTabs: true, inPlace: true })).toBeNull()
  })

  test('지금 보는 화면은 제자리(아무 데도 안 간다)', () => {
    expect(railTabTarget({ tab: 'Design', current: true, shellTabs: true })).toBeNull()
  })

  test('탭 줄이 모르는 화면(템플릿)은 제자리', () => {
    expect(railTabTarget({ tab: 'Template', current: false, shellTabs: true })).toBeNull()
  })

  test('웹·enterprise(shellTabs=false)는 늘 제자리', () => {
    for (const tab of ['Proposals', 'Design', 'Legacy']) {
      expect(railTabTarget({ tab, current: false, shellTabs: false })).toBeNull()
    }
  })

  test('수식키 — Ctrl 또는 ⌘', () => {
    expect(wantsInPlace({ ctrlKey: true })).toBe(true)
    expect(wantsInPlace({ metaKey: true })).toBe(true)
    expect(wantsInPlace({})).toBe(false)
    expect(wantsInPlace(undefined)).toBe(false)
  })
})
