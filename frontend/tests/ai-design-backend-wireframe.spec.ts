import { test, expect } from '@playwright/test'

/**
 * Phase 1 verification: backend-driven wireframe generation pipeline.
 *
 * Verifies the backend pipeline end-to-end without depending on UI
 * interactions (canvas/inspector clicks become brittle once the project
 * accumulates many nodes). The flow under test:
 *
 *   POST /api/ai-design/wireframe/{ui_node_id}
 *     1. backend reads UI node + BC from Neo4j
 *     2. langchain LLM agent (render+calc tools) → JSX
 *     3. wireframe service (Bun, port 7610) → SceneGraph
 *     4. Neo4j SET sceneGraph + designSource='backend'
 *     5. SSE stream emits context_loaded → tool_call → render_progress
 *        → persist_done → done events
 *
 * Robustness:
 *   - Targets the FIRST UI node returned from any context tree.
 *   - Resets that node's sceneGraph before generation so the test is
 *     idempotent across re-runs.
 *   - Asserts on SSE event names AND on the persisted Neo4j state.
 */

const PROVIDER_HOSTS = [
  'api.anthropic.com',
  'api.openai.com',
  'generativelanguage.googleapis.com',
  'openrouter.ai/api',
]

test.describe('AI Design — backend wireframe pipeline (Phase 1)', () => {
  test('POST /api/ai-design/wireframe/{id} runs the full backend agent and persists', async ({
    page,
    request,
  }) => {
    test.setTimeout(180_000)

    // ── Find a UI node to target ──────────────────────────────────────
    const ctxResp = await request.get('/api/contexts')
    expect(ctxResp.ok(), 'GET /api/contexts').toBeTruthy()
    const ctxs: any[] = await ctxResp.json()

    let targetUI: { id: string; displayName: string; bcId?: string } | null = null
    for (const ctx of ctxs) {
      const treeResp = await request.get(`/api/contexts/${ctx.id}/full-tree`)
      if (!treeResp.ok()) continue
      const tree = await treeResp.json()
      const found = walkForUI(tree)
      if (found) {
        targetUI = found
        break
      }
    }
    expect(targetUI, 'project must have at least one UI node').toBeTruthy()
    const uiId = targetUI!.id
    const uiName = targetUI!.displayName
    console.log(`[test] target UI: "${uiName}" (id=${uiId})`)

    // ── Reset sceneGraph so the run is idempotent ─────────────────────
    // /api/graph/update-node accepts a `sceneGraph` field; clearing it
    // to '' emulates "no design yet" without needing direct DB access.
    const resetResp = await request.put(`/api/graph/update-node/${uiId}`, {
      data: { sceneGraph: '' },
    })
    expect(resetResp.ok(), 'reset sceneGraph').toBeTruthy()
    console.log('[test] sceneGraph reset for', uiName)

    // ── Capture network — proxy/wireframe calls + ensure no direct provider ──
    await page.goto('/', { waitUntil: 'networkidle' })

    const directProviderCalls: string[] = []
    page.on('request', (req) => {
      const url = req.url()
      if (PROVIDER_HOSTS.some((h) => url.includes(h))) {
        directProviderCalls.push(url)
      }
    })

    // ── Drive the backend pipeline via the page-context fetch ─────────
    // Streaming the SSE response is easier from the page than from
    // request.post (the latter buffers the full body anyway, but page
    // gives us a real reader for free). Either works.
    const result = await page.evaluate(async (id) => {
      const resp = await fetch(`/api/ai-design/wireframe/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      })
      const events: { event: string; data: any }[] = []
      if (!resp.body) {
        return { status: resp.status, events, raw: '' }
      }
      const reader = resp.body.getReader()
      const dec = new TextDecoder()
      let buf = ''
      let raw = ''
      const start = Date.now()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = dec.decode(value, { stream: true })
        buf += chunk
        raw += chunk
        let idx
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          const evtLine = block.match(/^event:\s*(.+)$/m)
          const dataLine = block.match(/^data:\s*([\s\S]+)$/m)
          if (!evtLine || !dataLine) continue
          let data: any
          try { data = JSON.parse(dataLine[1]) } catch { continue }
          events.push({ event: evtLine[1].trim(), data })
        }
        if (Date.now() - start > 150_000) break // safety
      }
      return { status: resp.status, events, raw: raw.slice(0, 6000) }
    }, uiId)

    console.log(`[test] HTTP status: ${result.status}`)
    console.log(`[test] received ${result.events.length} SSE events`)
    for (const e of result.events.slice(0, 30)) {
      const summary = JSON.stringify(e.data).slice(0, 200)
      console.log(`  ${e.event}  ${summary}`)
    }

    // ── Assertions on the SSE stream ──────────────────────────────────
    expect(result.status).toBe(200)
    const eventNames = new Set(result.events.map((e) => e.event))
    expect(eventNames.has('context_loaded'), 'context_loaded emitted').toBeTruthy()
    expect(eventNames.has('llm_step'), 'llm_step emitted').toBeTruthy()
    expect(eventNames.has('tool_call'), 'tool_call emitted').toBeTruthy()
    expect(eventNames.has('render_progress'), 'render_progress emitted').toBeTruthy()
    expect(eventNames.has('persist_done'), 'persist_done emitted').toBeTruthy()
    expect(eventNames.has('done'), 'done emitted').toBeTruthy()
    expect(eventNames.has('error'), 'no error event').toBeFalsy()

    const renderToolCalls = result.events.filter((e) => e.event === 'tool_call' && e.data?.name === 'render')
    expect(renderToolCalls.length, 'at least one render tool call').toBeGreaterThan(0)

    const doneEvent = result.events.find((e) => e.event === 'done')
    expect(doneEvent?.data?.uiNodeId).toBe(uiId)
    expect(doneEvent?.data?.nodeCount).toBeGreaterThan(2)

    // ── Verify Neo4j persistence ──────────────────────────────────────
    const apiResp = await request.get(`/api/graph/expand-with-bc/${uiId}`)
    expect(apiResp.ok()).toBeTruthy()
    const apiData = await apiResp.json()
    const ui = apiData.nodes?.find((n: any) => n.id === uiId)
    expect(ui).toBeTruthy()

    const sg = ui?.sceneGraph
    expect(typeof sg, 'sceneGraph stored as JSON string').toBe('string')
    expect(sg.length, 'sceneGraph non-trivial').toBeGreaterThan(500)
    expect(ui.designSource, 'designSource marker').toBe('backend')

    const parsed = JSON.parse(sg)
    const nodeCount = Object.keys(parsed.nodes || {}).length
    console.log(`[test] persisted sceneGraph: ${nodeCount} nodes, designSource=${ui.designSource}`)
    expect(nodeCount).toBeGreaterThan(2)

    // ── Verify NO direct LLM-provider traffic from the page ────────────
    expect(directProviderCalls, 'browser made no direct LLM-provider calls').toHaveLength(0)
  })
})

// ── helpers ────────────────────────────────────────────────────────────

function walkForUI(node: any): { id: string; displayName: string; bcId?: string } | null {
  if (!node) return null
  const label = node.label || node.type
  const labels = node.labels || []
  if (label === 'UI' || labels.includes?.('UI')) {
    return {
      id: node.id,
      displayName: node.displayName || node.name || node.id,
    }
  }
  for (const k of ['children', 'aggregates', 'commands', 'events', 'readModels', 'uis', 'queries', 'policies']) {
    const arr = node[k]
    if (!Array.isArray(arr)) continue
    for (const child of arr) {
      const found = walkForUI(child)
      if (found) return found
    }
  }
  return null
}
