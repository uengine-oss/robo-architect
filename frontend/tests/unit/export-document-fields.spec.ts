/**
 * 노드의 **필드를 어느 칸에서 꺼내나** (2026-10-08).
 *
 * ## 왜 이 검사가 있나
 *
 * 내보낸 문서의 Event 표에서 **Payload 가 26행 전부 `-`** 였다. 필드를 안 만든 것이
 * 아니라 **이름표가 어긋나 있었다** —
 *
 * ```
 * payload      0/26 · 전부 null      ← 내보내기가 읽던 칸
 * properties  26/26 · 필드 2~32개씩   ← 실제 필드가 있던 칸
 * ```
 *
 * 오류가 안 났다. `null` 을 풀면 빈 배열이고, 빈 배열은 `-` 로 찍히고, `-` 는 "없다"
 * 로 읽힌다. Command 는 같은 자리에 `inputSchema` 가 채워져 있어 **17/17 멀쩡했다** —
 * 그 차이 때문에 한참 안 보였다.
 *
 * 아래 값은 기준 프로젝트(`prj_16972790c0`)의 **실제 Event 노드**에서 떠온 것이다.
 */
import { test, expect } from '@playwright/test'
// @ts-expect-error 플레인 JS 모듈
import { fieldsOf, parseJsonFields } from '../../src/features/exportDocument/fields.js'

/** 실제 Event — `payload` 는 `null` 이고 필드는 `properties` 에 있다. */
const REAL_EVENT = {
  id: '9a0eecd4-fca6-48c3-9e98-9f0b3ed9b600',
  name: 'ApprovalStepApproved',
  displayName: '결재 단계 승인됨',
  version: '1.0.0',
  payload: null,
  properties: [
    {
      name: 'approvalLineId', type: 'String', displayName: '결재선 ID',
      description: '승인된 결재선의 식별자', isKey: false, isForeignKey: true, isRequired: true,
    },
    { name: 'stepNo', type: 'Integer', isKey: false, isRequired: true },
  ],
}

/** 실제 Command — 필드가 `inputSchema` JSON 문자열에 있다. */
const REAL_COMMAND = {
  name: 'ApproveApprovalStep',
  inputSchema: '{"approvalStepId": "string", "approverEmpNo": "string", "comment": "string (optional)"}',
}

test('Event 필드는 **`properties` 에서** 꺼낸다 — `payload` 가 null 이어도 비지 않는다', () => {
  // 고치기 전 코드가 하던 것 — 이것이 26행을 전부 `-` 로 만들었다.
  expect(parseJsonFields(REAL_EVENT.payload)).toEqual([])

  const fields = fieldsOf(REAL_EVENT, 'payload')
  expect(fields).toHaveLength(2)
  expect(fields[0].name).toBe('approvalLineId')
  expect(fields[0].type).toBe('String')
  expect(fields[0].isRequired).toBe(true)
  expect(fields.map((f: { name: string }) => f.name)).toEqual(['approvalLineId', 'stepNo'])
})

test('Command 필드는 **JSON 칸에서** 꺼낸다 — 이쪽은 원래 멀쩡했다', () => {
  const fields = fieldsOf(REAL_COMMAND, 'inputSchema')
  expect(fields.map((f: { name: string }) => f.name)).toEqual(['approvalStepId', 'approverEmpNo', 'comment'])
  expect(fields[2].type).toBe('string (optional)')
})

test('`properties` 가 **있으면 그것이 원본**이다 — JSON 칸을 보지 않는다', () => {
  const both = { properties: [{ name: 'fromProps', type: 'String' }], payload: '{"fromPayload":"String"}' }
  expect(fieldsOf(both, 'payload').map((f: { name: string }) => f.name)).toEqual(['fromProps'])
})

test('둘 다 비면 **빈 배열**이다 — `-` 를 쓸지는 부르는 쪽이 정한다', () => {
  expect(fieldsOf({ payload: null, properties: [] }, 'payload')).toEqual([])
  expect(fieldsOf(null, 'payload')).toEqual([])
  expect(fieldsOf({}, 'payload')).toEqual([])
})

test('이름 없는 필드는 버린다 — 이름 없는 칸은 표에서 빈 줄이 된다', () => {
  const noisy = { properties: [{ type: 'String' }, { name: 'ok', type: 'String' }, null] }
  expect(fieldsOf(noisy).map((f: { name: string }) => f.name)).toEqual(['ok'])
})

test('배열로 온 JSON 칸도 **같은 모양**으로 맞춘다', () => {
  const arr = { payload: '[{"name":"a","dataType":"Long"}]' }
  const f = fieldsOf(arr, 'payload')
  expect(f).toEqual([{ name: 'a', type: 'Long', isKey: false, isRequired: false, description: '' }])
})

test('깨진 JSON 은 **빈 배열**이다 — 화면이 터지지 않는다', () => {
  expect(parseJsonFields('{not json')).toEqual([])
  expect(parseJsonFields('')).toEqual([])
  expect(parseJsonFields(undefined)).toEqual([])
})

test('**같은 필드를 두 번 적지 않는다** — API 가 2~4배로 돌려주던 그 모양', () => {
  // 실측 — full-tree 가 한 Event 의 필드를 4번씩 돌려줬다(같은 id 가 네 번).
  // 그래서 문서 Payload 에 `approvalLineId(String)` 이 네 번 찍혔다.
  const fourTimes = {
    properties: [
      { id: 'p1', name: 'approvalLineId', type: 'String', isRequired: true },
      { id: 'p1', name: 'approvalLineId', type: 'String', isRequired: true },
      { id: 'p1', name: 'approvalLineId', type: 'String', isRequired: true },
      { id: 'p1', name: 'approvalLineId', type: 'String', isRequired: true },
      { id: 'p2', name: 'stepNo', type: 'Integer' },
      { id: 'p2', name: 'stepNo', type: 'Integer' },
    ],
  }
  const fields = fieldsOf(fourTimes, 'payload')
  expect(fields.map((f: { name: string }) => f.name)).toEqual(['approvalLineId', 'stepNo'])
})

test('id 가 없으면 **이름**으로 가른다 — JSON 칸에서 온 필드가 그렇다', () => {
  const noIds = { properties: [{ name: 'a', type: 'String' }, { name: 'a', type: 'String' }, { name: 'b', type: 'Long' }] }
  expect(fieldsOf(noIds).map((f: { name: string }) => f.name)).toEqual(['a', 'b'])
})

test('이름이 같아도 **id 가 다르면 둘 다** 남긴다 — 값을 지우지 않는다', () => {
  const two = { properties: [{ id: 'x', name: 'amount', type: 'Long' }, { id: 'y', name: 'amount', type: 'String' }] }
  expect(fieldsOf(two)).toHaveLength(2)
})
