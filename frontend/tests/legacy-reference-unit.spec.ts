// evlink — legacy-reference selector 순수 로직 단위 검증 (브라우저 불필요).
// 실행: npx playwright test -c playwright.unit.config.ts
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import {
  elementLegacyBasis,
  provenanceIndex,
  legacyReferenceItems,
  legacyReferenceCount,
} from '../src/features/proposals/legacy-reference.js'

const V2_REFS = [{
  version: 2, stage: 'INTENT',
  retrieves: [{
    query: 'q',
    searchedNodes: [{ id: 'code:a.c:f1', name: 'f1', label: 'FUNCTION', summary: 's' }],
    inspections: [
      { nodeId: 'code:a.c:f1', ok: true, name: 'f1', source: { available: true, file_path: 'a.c', start_line: 3, end_line: 9 } },
      { nodeId: 'code:a.c:broken', ok: false, error: { code: 'NODE_NOT_FOUND' } },
    ],
  }],
}]

test.describe('elementLegacyBasis — 3상태 판정', () => {
  test('linked: 유효 refs 보유', () => {
    const basis = elementLegacyBasis({ legacyRefs: [{ nodeId: 'code:a.c:f1', evidence: 'e' }] })
    expect(basis.state).toBe('linked')
    expect(basis.refs).toEqual([{ nodeId: 'code:a.c:f1', evidence: 'e' }])
  })

  test('new: 빈 배열은 정직한 근거 없음', () => {
    expect(elementLegacyBasis({ legacyRefs: [] }).state).toBe('new')
  })

  test('unknown: 키 부재는 구버전 판정불가 — 신규로 오표기 금지(T6)', () => {
    expect(elementLegacyBasis({ tempId: 'EP-1' }).state).toBe('unknown')
    expect(elementLegacyBasis(null).state).toBe('unknown')
    expect(elementLegacyBasis(undefined).state).toBe('unknown')
    expect(elementLegacyBasis({ legacyRefs: 'not-a-list' }).state).toBe('unknown')
  })

  test('bare string nodeId 수용·객체로 정규화', () => {
    const basis = elementLegacyBasis({ legacyRefs: ['db:t1'] })
    expect(basis.state).toBe('linked')
    expect(basis.refs).toEqual([{ nodeId: 'db:t1' }])
  })

  test('깨진 항목은 걸러지고 전량 불량이면 new', () => {
    expect(elementLegacyBasis({ legacyRefs: [null, 42, {}, { nodeId: '  ' }] }).state).toBe('new')
    const mixed = elementLegacyBasis({ legacyRefs: [null, { nodeId: 'code:ok' }] })
    expect(mixed.state).toBe('linked')
    expect(mixed.refs).toHaveLength(1)
  })

  test('임의 id 스킴(유니코드·특수문자·초장문)에서 해석 없이 안전', () => {
    const weird = ['java:com.acme.Order#place', 'file:src/한글 경로/주문.xml#섹션-1', 'x'.repeat(500)]
    const basis = elementLegacyBasis({ legacyRefs: weird })
    expect(basis.state).toBe('linked')
    expect(basis.refs.map((r: { nodeId: string }) => r.nodeId)).toEqual(weird)
  })

  test('중복 nodeId 는 첫 항목만(T3 중복 금지)', () => {
    const basis = elementLegacyBasis({ legacyRefs: [
      { nodeId: 'code:a', evidence: '첫' }, { nodeId: 'code:a', evidence: '둘' },
    ] })
    expect(basis.refs).toEqual([{ nodeId: 'code:a', evidence: '첫' }])
  })
})

test.describe('provenanceIndex — 표시 강화 인덱스', () => {
  test('검색+검토 병합, source line 노출', () => {
    const index = provenanceIndex(V2_REFS)
    const item = index.get('code:a.c:f1')
    expect(item.inspected).toBe(true)
    expect(item.source.start_line).toBe(3)
  })

  test('실패 inspection 도 항목으로 남되 inspected=false', () => {
    const item = provenanceIndex(V2_REFS).get('code:a.c:broken')
    expect(item.inspected).toBe(false)
    expect(item.inspectionError.code).toBe('NODE_NOT_FOUND')
  })

  test('v1(nodes 키)·빈 입력·깨진 입력 방어', () => {
    const v1 = [{ stage: 'INTENT', retrieves: [{ query: 'q', nodes: [{ id: 'code:v1' }] }] }]
    expect(provenanceIndex(v1).has('code:v1')).toBe(true)
    expect(provenanceIndex([]).size).toBe(0)
    expect(provenanceIndex(null).size).toBe(0)
    expect(legacyReferenceCount(undefined)).toBe(0)
    expect(legacyReferenceItems([{ retrieves: [{}] }])).toEqual([])
  })
})
