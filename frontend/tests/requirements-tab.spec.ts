import { test, expect } from '@playwright/test'

/**
 * Spec 026 — requirements-tab smoke test.
 *
 * Covers quickstart S1 (4-level tree drill-down + user story detail) and
 * S2 (selecting a user story loads its design trace). The backend is mocked
 * at the network boundary so the test runs without Neo4j.
 */

const TREE = {
  epics: [
    {
      id: 'bc-1',
      name: 'Order',
      features: [
        {
          id: 'feat-1',
          name: '주문 취소',
          description: '',
          source: 'llm',
          userStories: [
            {
              id: 'us-1',
              role: 'customer',
              action: 'cancel my order',
              benefit: 'I can get a refund',
              priority: 'high',
              status: 'approved',
              commandId: 'cmd-1',
              commandName: 'CancelOrder',
              acceptanceCriteria: [
                { kind: 'given', name: 'Command: CancelOrder', description: null },
              ],
            },
          ],
        },
      ],
      unassignedFeature: null,
    },
  ],
  unassigned: [],
}

const TRACE = {
  rootCommandId: 'cmd-1',
  nodes: [
    { id: 'cmd-1', name: 'CancelOrder', type: 'Command' },
    { id: 'evt-1', name: 'OrderCancelled', type: 'Event' },
  ],
  relationships: [{ source: 'cmd-1', target: 'evt-1', type: 'EMITS' }],
  empty: false,
}

test('Requirements tab: drill down the tree and open a user story', async ({ page }) => {
  await page.route('**/api/requirements/tree', (route) =>
    route.fulfill({ json: TREE }),
  )
  await page.route('**/api/requirements/user-story/us-1/design-trace', (route) =>
    route.fulfill({ json: TRACE }),
  )

  await page.goto('/')

  // Open the Requirements tab (first tab).
  await page.getByRole('button', { name: 'Requirements' }).first().click()

  // Drill down: Epic → Feature → User Story.
  await page.getByText('Order', { exact: true }).click()
  await page.getByText('주문 취소', { exact: true }).click()
  const usRow = page.getByText('customer: cancel my order')
  await expect(usRow).toBeVisible()

  // Selecting the user story shows the "As a … I want … so that …" detail.
  await usRow.click()
  await expect(page.getByText('I want cancel my order')).toBeVisible()
  await expect(page.getByText('Command: CancelOrder').first()).toBeVisible()
})
