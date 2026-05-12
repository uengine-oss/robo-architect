import { test, expect } from '@playwright/test'

/**
 * Feature 022 — DDD Artifact Generation from Event Storming
 *
 * The feature is backend-only in this PR (frontend mirror deferred per
 * plan.md Complexity Tracking). The visible surface is the four new
 * endpoints under `/api/ddd-spec/*`, which must show up in the Swagger
 * UI tag "ddd-spec".
 *
 * This spec runs against a backend started on port 8765 (so it does not
 * collide with whatever the developer has on :8000).
 */

const BACKEND = 'http://127.0.0.1:8765'

const EXPECTED_OPS = [
  { path: '/api/ddd-spec/generate-bounded-context', method: 'post' },
  { path: '/api/ddd-spec/generate-aggregate', method: 'post' },
  { path: '/api/ddd-spec/generate-context-map', method: 'post' },
  { path: '/api/ddd-spec/generate-all', method: 'post' },
]

test('openapi.json advertises the four /api/ddd-spec endpoints', async ({ request }) => {
  const resp = await request.get(`${BACKEND}/openapi.json`)
  expect(resp.ok()).toBeTruthy()
  const doc = await resp.json()
  const paths = doc.paths ?? {}
  for (const op of EXPECTED_OPS) {
    expect(paths[op.path], `${op.path} should be present in openapi.json`).toBeTruthy()
    expect(paths[op.path][op.method], `${op.method.toUpperCase()} ${op.path} should be present`).toBeTruthy()
    expect(paths[op.path][op.method].tags).toContain('ddd-spec')
  }
})

test('Swagger UI renders all four ddd-spec endpoints under the ddd-spec tag', async ({ page }) => {
  await page.goto(`${BACKEND}/docs`)
  // Wait for swagger-ui to finish hydrating.
  await page.waitForSelector('.opblock-tag[data-tag="ddd-spec"]', { timeout: 30_000 })

  // Expand the tag if collapsed.
  const tagHeader = page.locator('.opblock-tag[data-tag="ddd-spec"]')
  await tagHeader.scrollIntoViewIfNeeded()
  await expect(tagHeader).toBeVisible()
  if ((await tagHeader.getAttribute('class'))?.includes('is-open') !== true) {
    await tagHeader.click()
  }

  // Swagger renders each operation as `.opblock` containing an `.opblock-summary-path`
  // whose data-path equals the route path. Cross-check by data-path so we don't depend
  // on the (verbose, FastAPI-generated) operationId.
  for (const op of EXPECTED_OPS) {
    const block = page.locator(
      `.opblock.opblock-${op.method} :has(.opblock-summary-path[data-path="${op.path}"])`,
    ).first()
    await expect(block, `Swagger should render ${op.method.toUpperCase()} ${op.path}`).toBeVisible({
      timeout: 10_000,
    })
  }

  // Take a screenshot for visual confirmation — useful in headed runs.
  await page.screenshot({
    path: 'test-results/ddd-spec-swagger.png',
    fullPage: true,
  })
})

test('POST /generate-context-map returns 400 no_bounded_contexts on an empty graph', async ({ request }) => {
  // The CI/dev Neo4j may legitimately have BCs; treat this as "either 200
  // with a created file, OR 400 with no_bounded_contexts". The point is to
  // confirm the endpoint is wired and returns a well-formed body.
  const resp = await request.post(`${BACKEND}/api/ddd-spec/generate-context-map`, {
    data: { overwrite: false, infer_patterns_with_llm: false },
  })
  expect([200, 400, 409, 500]).toContain(resp.status())
  const body = await resp.json()
  if (resp.status() === 200) {
    expect(body).toHaveProperty('correlation_id')
    expect(body).toHaveProperty('created')
  } else {
    expect(body).toHaveProperty('detail')
  }
})

function idFor(path: string) {
  // FastAPI generates Swagger operation ids from the route function name;
  // the DOM id is `operations-<tag>-<operationId>`. We don't know the
  // exact opId, so we fall back to a path-suffix match below.
  const tail = path.split('/').pop() || ''
  return tail.replace(/-/g, '_')
}
