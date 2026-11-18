/**
 * openEventSource — `new EventSource` 자리에 끼우는 판(2026-11-18).
 * 인증을 켠 서버 판에서 EventSource 스트림이 401 이라 요구사항 명확화가 "스캔 중" 에서 끝나지 않았다.
 */
import { expect, test } from '@playwright/test'

// @ts-expect-error 플레인 JS 모듈
import { openEventSource, openSse } from '../../src/app/sse.js'

function sseResponse(text: string, status = 200) {
  const body = new ReadableStream({
    start(c) { c.enqueue(new TextEncoder().encode(text)); c.close() },
  })
  return new Response(body, { status, headers: { 'Content-Type': 'text/event-stream' } })
}

async function withFetch(impl: (...a: any[]) => Promise<Response>, fn: () => Promise<void>) {
  const orig = globalThis.fetch
  ;(globalThis as any).fetch = impl
  try { await fn() } finally { (globalThis as any).fetch = orig }
}

const tick = () => new Promise((r) => setTimeout(r, 20))

test('onmessage 로 기본 이벤트를 받고 readyState 가 바뀐다', async () => {
  await withFetch(async () => sseResponse('data: {"phase":"questions_ready"}\n\n'), async () => {
    const es = openEventSource('/x')
    const got: string[] = []
    let opened = false
    es.onopen = () => { opened = true }
    es.onmessage = (ev: any) => got.push(ev.data)
    expect(es.readyState).toBe(0)
    await tick()
    expect(opened).toBe(true)
    expect(got).toEqual(['{"phase":"questions_ready"}'])
    expect(es.readyState).toBe(es.CLOSED)
  })
})

test('401 이면 onerror — 화면이 "스캔 중" 에 머물지 않게', async () => {
  await withFetch(async () => new Response('no', { status: 401 }), async () => {
    const es = openEventSource('/x')
    let err: any = null
    es.onerror = (e: any) => { err = e }
    await tick()
    expect(String(err)).toContain('401')
    expect(es.readyState).toBe(2)
  })
})

test('끝 신호 없이 서버가 닫으면 onerror(EventSource 와 같다) · 호출부가 먼저 닫으면 안 부른다', async () => {
  await withFetch(async () => sseResponse('event: progress\ndata: 1\n\n'), async () => {
    const es = openEventSource('/x')
    let errors = 0
    es.onerror = () => { errors += 1 }
    await tick()
    expect(errors).toBe(1)
  })
  await withFetch(async () => sseResponse('event: done\ndata: 1\n\n'), async () => {
    const es = openEventSource('/x')
    let errors = 0
    es.addEventListener('done', () => es.close())
    es.onerror = () => { errors += 1 }
    await tick()
    expect(errors).toBe(0)
  })
})

test('기존 openSse 는 서버가 닫아도 onerror 를 안 부른다(동작 유지)', async () => {
  await withFetch(async () => sseResponse('data: 1\n\n'), async () => {
    const es = openSse('/x')
    let errors = 0
    es.onerror = () => { errors += 1 }
    await tick()
    expect(errors).toBe(0)
  })
})
