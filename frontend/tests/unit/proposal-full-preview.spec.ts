/**
 * B-4 ⑧ 전체 미리보기 — 제안이 건드리는 BC 를 어떻게 모으나(collectPreviewBcIds).
 *
 * 전체 미리보기는 새 백엔드 없이 BC 마다 기존 투영(design graph · data full-tree)을 다시
 * 부른다. 그래서 "어느 BC 를 투영하나" 가 진입점의 전부다.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { collectPreviewBcIds } from '../../src/features/proposals/proposalPreview.js'

test('tacticalDiff 의 boundedContextId · BC 항목 · impactMap 을 순서대로, 중복 없이 모은다', () => {
  const ids = collectPreviewBcIds({
    tacticalDiff: [
      { nodeLabel: 'Aggregate', changeType: 'CREATE', boundedContextId: 'BC-order' },
      { nodeLabel: 'Command', changeType: 'CREATE', aggregateId: 'AGG-1' },
      { nodeLabel: 'UI', changeType: 'CREATE', boundedContextId: 'BC-order' },
      { nodeLabel: 'BoundedContext', changeType: 'MODIFY', nodeId: 'BC-pay' },
    ],
    impactMap: [
      { nodeLabel: 'BoundedContext', nodeId: 'BC-ship' },
      { nodeLabel: 'Aggregate', nodeId: 'AGG-x' },
    ],
  })
  expect(ids).toEqual(['BC-order', 'BC-pay', 'BC-ship'])
})

test('tacticalDiff 가 비면 planDraft.tacticalDiff 를 본다(Plan 단계 산출물)', () => {
  const ids = collectPreviewBcIds({
    tacticalDiff: [],
    planDraft: { tacticalDiff: [{ nodeLabel: 'Aggregate', boundedContextId: 'BC-a' }] },
  })
  expect(ids).toEqual(['BC-a'])
})

test('신규 BC(CREATE) 와 임시 id 는 투영 대상이 아니다', () => {
  const ids = collectPreviewBcIds({
    tacticalDiff: [
      { nodeLabel: 'BoundedContext', changeType: 'CREATE', nodeId: 'BC-new' },
      { nodeLabel: 'Aggregate', boundedContextId: 'PREVIEW:PRO-1:0' },
    ],
  })
  expect(ids).toEqual([])
})

test('제안이 없으면 빈 목록', () => {
  expect(collectPreviewBcIds(null)).toEqual([])
  expect(collectPreviewBcIds({})).toEqual([])
})
