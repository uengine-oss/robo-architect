/**
 * 만들 때 고른 의도 → DDD 마법사 기본값 (라이트 지적 C-5 ⑩, `projectIntent.js`).
 * 웹 판·enterprise·옛 프로젝트는 `null` 이어야 한다 — 그래야 마법사의 지금 기본값이 지켜진다.
 */

import { expect, test } from '@playwright/test'

import { loadProjectTypeDefault, projectTypeFor } from '../../src/features/requirements/projectIntent'

const projects = [
  { name: 'shop', projectType: 'greenfield' },
  { name: 'erp', projectType: 'brownfield' },
  { name: 'old', projectType: null },
  { name: 'odd', projectType: 'learning' },
]
const lite = { desktop: { projects: { list: async () => ({ ok: true, data: projects }) } } }

test('목록에서 그 그래프의 의도를 읽는다', () => {
  expect(projectTypeFor(projects, 'erp')).toBe('brownfield')
  expect(projectTypeFor(projects, 'shop')).toBe('greenfield')
})

test('모르면 null — 옛 프로젝트·어휘 밖·없는 그래프', () => {
  expect(projectTypeFor(projects, 'old')).toBeNull()
  expect(projectTypeFor(projects, 'odd')).toBeNull()
  expect(projectTypeFor(projects, 'nope')).toBeNull()
  expect(projectTypeFor(null, 'erp')).toBeNull()
})

test('lite 데스크톱에서 읽는다', async () => {
  expect(await loadProjectTypeDefault('erp', lite as never)).toBe('brownfield')
})

test('웹 판(window.desktop 없음)은 null', async () => {
  expect(await loadProjectTypeDefault('erp', {} as never)).toBeNull()
})

test('enterprise(projects:list 거절)는 null', async () => {
  const ent = { desktop: { projects: { list: async () => ({ ok: false, error: { message: 'lite only' } }) } } }
  expect(await loadProjectTypeDefault('erp', ent as never)).toBeNull()
  const throws = { desktop: { projects: { list: async () => { throw new Error('x') } } } }
  expect(await loadProjectTypeDefault('erp', throws as never)).toBeNull()
})

test('그래프를 모르면 묻지도 않는다', async () => {
  expect(await loadProjectTypeDefault(null, lite as never)).toBeNull()
})
