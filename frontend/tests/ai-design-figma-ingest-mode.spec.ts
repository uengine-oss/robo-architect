import { test, expect } from '@playwright/test'

/**
 * Verifies that the requirements ingestion modal carries the
 * `ui_generation_mode` ("html" | "figma") field through to the backend,
 * and that the backend stores it on the session.
 *
 * This is a contract regression test only — it does NOT run a full ingestion
 * (that would burn many LLM calls and is verified by manual smoke + the
 * existing wireframe Playwright tests).
 */

test.describe('Ingestion — UI generation mode field', () => {
  test('POST /api/ingest/upload stores ui_generation_mode=figma on the session', async ({ request }) => {
    const form = new FormData()
    form.append(
      'text',
      '# 미니 요구사항\n- 사용자는 로그인할 수 있어야 한다\n- 사용자는 비밀번호를 재설정할 수 있어야 한다'
    )
    form.append('display_language', 'ko')
    form.append('ui_generation_mode', 'figma')
    form.append('source_type', 'rfp')

    const resp = await request.post('/api/ingest/upload', { multipart: form as any })
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    expect(data.session_id).toBeTruthy()
    expect(data.ui_generation_mode).toBe('figma')
  })

  test('POST /api/ingest/upload defaults ui_generation_mode=html when omitted', async ({ request }) => {
    const form = new FormData()
    form.append('text', '# 테스트\n- 한 줄')
    form.append('display_language', 'ko')
    // ui_generation_mode intentionally omitted

    const resp = await request.post('/api/ingest/upload', { multipart: form as any })
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    expect(data.ui_generation_mode).toBe('html')
  })

  test('POST /api/ingest/upload coerces unknown ui_generation_mode to html', async ({ request }) => {
    const form = new FormData()
    form.append('text', '# 테스트\n- 한 줄')
    form.append('ui_generation_mode', 'invalid-mode')

    const resp = await request.post('/api/ingest/upload', { multipart: form as any })
    expect(resp.ok()).toBeTruthy()
    const data = await resp.json()
    expect(data.ui_generation_mode).toBe('html')
  })
})
