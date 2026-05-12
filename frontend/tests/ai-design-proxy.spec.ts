import { test, expect } from '@playwright/test'

/**
 * E2E test: open-pencil AI is now proxied through the backend
 * (api/features/ai_design + frontend/src/features/aiDesign/bootstrap.js).
 *
 * What we verify:
 *  1. Bootstrap is purely static client-side: it sets non-secret SDK
 *     plumbing keys (provider routing, base URL, placeholder api-key,
 *     placeholder model) so open-pencil's existing @ai-sdk/openai client
 *     posts to our backend. NO backend call is required for bootstrap —
 *     the real provider/model/credentials live exclusively on the backend.
 *  2. A real Chat Completions request goes to /api/ai-design/v1/chat/completions
 *     and the browser never calls api.anthropic.com / api.openai.com / google /
 *     openrouter directly.
 *
 * Test 2 makes the call via `page.evaluate()` so it does NOT depend on the
 * full UI flow (Inspector → Design tab → button click), which is already
 * exercised by `wireframe-convert.spec.ts`.
 */

const OPEN_PENCIL_LS_KEYS = [
  'open-pencil:ai-provider',
  'open-pencil:ai-model',
  'open-pencil:ai-base-url',
  'open-pencil:ai-custom-model',
  'open-pencil:ai-api-type',
  'open-pencil:ai-key:openai',
  'open-pencil:ai-key:anthropic',
  'open-pencil:ai-key:google',
  'open-pencil:ai-key:openrouter',
  'open-pencil:ai-key:openai-compatible',
]

const EXTERNAL_PROVIDER_HOSTS = [
  'api.anthropic.com',
  'api.openai.com',
  'generativelanguage.googleapis.com',
  'openrouter.ai/api',
]

test.describe('AI Design backend proxy', () => {
  test('bootstrap is static — wires SDK plumbing without any backend call', async ({ page }) => {
    test.setTimeout(30_000)

    // Watch for any backend call during bootstrap. There should be none
    // related to ai-design — the fix moved bootstrap to pure client-side.
    const aiDesignCalls: string[] = []
    page.on('request', (req) => {
      const url = req.url()
      if (url.includes('/api/ai-design/')) {
        aiDesignCalls.push(`${req.method()} ${url}`)
      }
    })

    // First load — runs bootstrap, populates localStorage. Clear it so the
    // second load truly re-runs bootstrap (which short-circuits when set).
    await page.goto('/')
    await page.evaluate((keys) => {
      for (const k of keys) localStorage.removeItem(k)
    }, OPEN_PENCIL_LS_KEYS)

    // Reset call list so we only count what happens on this reload.
    aiDesignCalls.length = 0

    await page.reload({ waitUntil: 'networkidle' })

    // Bootstrap is synchronous now — but give Vite/HMR a hair to settle.
    await page.waitForFunction(
      () => localStorage.getItem('open-pencil:ai-provider') === 'openai-compatible',
      undefined,
      { timeout: 5_000 }
    )

    const ls = await page.evaluate(() => ({
      provider: localStorage.getItem('open-pencil:ai-provider'),
      baseUrl: localStorage.getItem('open-pencil:ai-base-url'),
      apiType: localStorage.getItem('open-pencil:ai-api-type'),
      customModel: localStorage.getItem('open-pencil:ai-custom-model'),
      apiKey: localStorage.getItem('open-pencil:ai-key:openai-compatible'),
    }))

    // Plumbing — these are SDK config, not credentials, and not echoes
    // of any backend secret/state.
    expect(ls.provider).toBe('openai-compatible')
    // baseUrl must include /v1 — OpenAI-compatible SDKs append /chat/completions.
    expect(ls.baseUrl).toMatch(/\/api\/ai-design\/v1$/)
    expect(ls.apiType).toBe('completions')
    // Placeholders — NOT the real api key, NOT the real model name.
    expect(ls.apiKey).toBe('proxy')
    expect(ls.customModel).toBe('backend-managed')

    // The bootstrap fix removed the /info round-trip. We assert no
    // ai-design endpoint is touched during bootstrap so any future regression
    // (someone re-introducing a fetch) is caught.
    expect(
      aiDesignCalls,
      'bootstrap must not call backend; got: ' + aiDesignCalls.join(', ')
    ).toHaveLength(0)
  })

  test('Chat completion routes through backend; no direct provider calls', async ({ page }) => {
    test.setTimeout(120_000)

    // Track every relevant request and final response status.
    const calls: { url: string; status?: number; method: string }[] = []
    page.on('request', (req) => {
      const url = req.url()
      if (
        url.includes('/api/ai-design/v1/chat/completions') ||
        EXTERNAL_PROVIDER_HOSTS.some((h) => url.includes(h))
      ) {
        calls.push({ url, method: req.method() })
      }
    })
    page.on('response', (resp) => {
      const idx = calls.findIndex(
        (c) => c.url === resp.url() && c.status === undefined
      )
      if (idx >= 0) calls[idx].status = resp.status()
    })

    await page.goto('/', { waitUntil: 'networkidle' })
    await expect(page.locator('#app')).toBeVisible()

    // Wait for bootstrap to finish writing the LS keys.
    await page.waitForFunction(
      () => localStorage.getItem('open-pencil:ai-provider') === 'openai-compatible',
      undefined,
      { timeout: 10_000 }
    )

    // Make a Chat Completions call exactly the way open-pencil's
    // `createOpenAI({ apiKey, baseURL })` would — driven from the page
    // context so any direct external calls would also be observable here.
    // Note: the `model` field in the request body is whatever placeholder
    // open-pencil sends; the backend ignores it and uses LLM_MODEL from env.
    const result = await page.evaluate(async () => {
      const baseUrl = localStorage.getItem('open-pencil:ai-base-url')!
      const model = localStorage.getItem('open-pencil:ai-custom-model')!
      // baseUrl already includes /v1; just append /chat/completions like the SDK does.
      const resp = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model,
          messages: [
            { role: 'user', content: 'Reply with the four characters: TEST' },
          ],
          stream: true,
          max_tokens: 32,
        }),
      })
      const reader = resp.body!.getReader()
      const dec = new TextDecoder()
      let body = ''
      let chunks = 0
      const start = Date.now()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        body += dec.decode(value)
        chunks++
        if (body.length > 8000 || chunks > 200 || Date.now() - start > 60_000) break
      }
      return {
        status: resp.status,
        chunks,
        hasDone: body.includes('[DONE]'),
        hasError: body.includes('"error"'),
        bodyHead: body.slice(0, 800),
      }
    })

    console.log('[test] proxy stream result:', JSON.stringify(result, null, 2))

    expect(result.status).toBe(200)
    expect(result.chunks).toBeGreaterThan(0)
    // Either we got a clean DONE, or the proxy emitted an in-stream error
    // chunk — both prove the routing works.
    expect(result.hasDone || result.hasError).toBeTruthy()

    const proxyHits = calls.filter((c) =>
      c.url.includes('/api/ai-design/v1/chat/completions')
    )
    const directHits = calls.filter((c) =>
      EXTERNAL_PROVIDER_HOSTS.some((h) => c.url.includes(h))
    )

    expect(proxyHits.length, 'browser should hit the proxy').toBeGreaterThan(0)
    expect(proxyHits[0].status).toBe(200)
    expect(
      directHits,
      'browser must not call any external LLM provider directly'
    ).toHaveLength(0)
  })
})
