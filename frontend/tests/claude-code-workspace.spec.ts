import { test, expect, Page } from '@playwright/test'

const FIXTURE_ROOT = '/tmp/ccw-e2e-fixture'

// Programmatically drive the workspace into our fixture directory by
// tapping the existing `provide('openClaudeCode', fn)` injection that
// App.vue exposes. This avoids fighting the in-pane folder-picker UI in
// the headed run.
async function openClaudeCodeWorkspace(page: Page, root: string) {
  // 1. Click the Claude Code button to switch tabs.
  await page.getByRole('button', { name: 'Claude Code', exact: true }).click()

  // 2. Wait for the workspace shell to render.
  await expect(page.locator('.ccw-root')).toBeVisible({ timeout: 10_000 })

  // 3. Drive the in-pane folder picker via the API rather than the UI.
  //    The terminal owns the picker; opening it, navigating to FIXTURE_ROOT,
  //    and clicking "이 폴더에서 열기" is brittle headed. So we cheat:
  //    set activeRoot directly by emitting the same event the picker emits.
  await page.evaluate((path) => {
    // Find the workspace's Vue component via its root DOM node and set
    // activeRoot through the exposed scoped state. We synthesize the
    // emit('workdir-picked') by dispatching a custom DOM event the
    // workspace listens for via its `@workdir-picked` handler.
    // The cleanest hook is to write to localStorage to drive width
    // restoration; for activeRoot we directly set window.__ccwTestSetRoot
    // which the App.vue test hook will respect.
    ;(window as any).__ccwTestRoot = path
  }, root)

  // Reload-free path: simulate the event by evaluating in page context
  // using the existing emit chain. Easiest = trigger the terminal's
  // internal `confirmFolderSelection` via DOM events. Instead we just
  // reload with a query param honored by a small App.vue test shim.
}

test.describe('Claude Code IDE Workspace (021)', () => {
  test.beforeEach(async ({ page }) => {
    // Surface console errors in the test output for easier debug.
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        console.log('[browser console error]', msg.text())
      }
    })
    page.on('pageerror', (err) => {
      console.log('[page error]', err.message)
    })
  })

  test('S1 — clicks Claude Code button and 3-pane shell renders', async ({ page }) => {
    await page.goto('/')

    // Click the Claude Code top-bar button.
    await page.getByRole('button', { name: 'Claude Code', exact: true }).click()

    // The workspace shell mounts.
    const shell = page.locator('.ccw-root')
    await expect(shell).toBeVisible({ timeout: 10_000 })

    // Three panes (collapse toggles always present, so we count the panes).
    await expect(page.locator('.ccw-tree')).toBeVisible()
    await expect(page.locator('.ccw-editor')).toBeVisible()
    await expect(page.locator('.ccw-terminal')).toBeVisible()

    // Editor placeholder text appears (no file selected yet).
    await expect(page.locator('.ccw-editor')).toContainText('트리에서 파일을 선택하세요')
  })

  test('S2 — picks fixture dir via API, tree lists files, editor opens README.md', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Claude Code', exact: true }).click()
    await expect(page.locator('.ccw-root')).toBeVisible({ timeout: 10_000 })

    // Inject the picked root by directly dispatching the same event the
    // terminal's folder picker emits. We grab the workspace's Vue instance
    // by walking the DOM, find its `__vueParentComponent`, and call the
    // exposed `onTerminalWorkdirPicked` via the emit chain. Easiest path:
    // monkey-patch via a window hook the workspace registers.
    //
    // Since we did not wire a window hook, we use a simpler trick: the
    // ClaudeCodeTerminal component emits `workdir-picked` with the chosen
    // path. We grab its root DOM node and dispatch a synthetic Vue event
    // by looking up the component instance.
    await page.evaluate((root) => {
      function findVueComponent(el: any, name: string): any {
        if (!el) return null
        let cur = el.__vueParentComponent
        while (cur) {
          if (cur.type?.__name === name || cur.type?.name === name) return cur
          cur = cur.parent
        }
        return null
      }
      const terminalEl = document.querySelector('.claude-code-terminal') as any
      const inst = findVueComponent(terminalEl, 'ClaudeCodeTerminal')
      if (!inst) throw new Error('ClaudeCodeTerminal instance not found')
      inst.emit('workdir-picked', root)
    }, FIXTURE_ROOT)

    // Tree should now list the fixture's children. Whitelisted .claude
    // is shown; .git is filtered.
    const treeBody = page.locator('.ccw-tree .tree-body')
    await expect(treeBody).toContainText('README.md', { timeout: 10_000 })
    await expect(treeBody).toContainText('.claude')
    await expect(treeBody).toContainText('specs')
    await expect(treeBody).not.toContainText('.git')

    // Click README.md → editor loads.
    await page.locator('.ccw-tree .tree-row-file').filter({ hasText: 'README.md' }).click()

    // Tab strip shows the file name.
    await expect(page.locator('.editor-tab-label')).toContainText('README.md')
    // Editor body has the Markdown content.
    await expect(page.locator('.cm-editor')).toContainText('Sample Project', { timeout: 5_000 })
  })

  test('S3 — typing into the editor flips the dirty indicator', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Claude Code', exact: true }).click()
    await expect(page.locator('.ccw-root')).toBeVisible({ timeout: 10_000 })

    await page.evaluate((root) => {
      function findVueComponent(el: any, name: string): any {
        if (!el) return null
        let cur = el.__vueParentComponent
        while (cur) {
          if (cur.type?.__name === name || cur.type?.name === name) return cur
          cur = cur.parent
        }
        return null
      }
      const terminalEl = document.querySelector('.claude-code-terminal') as any
      const inst = findVueComponent(terminalEl, 'ClaudeCodeTerminal')
      inst.emit('workdir-picked', root)
    }, FIXTURE_ROOT)

    // Open README.md.
    await expect(page.locator('.ccw-tree .tree-body')).toContainText('README.md', { timeout: 10_000 })
    await page.locator('.ccw-tree .tree-row-file').filter({ hasText: 'README.md' }).click()
    await expect(page.locator('.cm-editor')).toContainText('Sample Project', { timeout: 5_000 })

    // No dirty dot initially.
    await expect(page.locator('.editor-tab .dirty-dot')).toHaveCount(0)

    // Focus the editor and type.
    await page.locator('.cm-content').click()
    await page.keyboard.type('// edited from playwright\n')

    // Dirty dot appears.
    await expect(page.locator('.editor-tab .dirty-dot')).toBeVisible({ timeout: 5_000 })

    // Save button is now enabled.
    const saveBtn = page.locator('.editor-save')
    await expect(saveBtn).toBeEnabled()

    // Click Save → indicator clears.
    await saveBtn.click()
    await expect(page.locator('.editor-tab .dirty-dot')).toHaveCount(0, { timeout: 5_000 })

    // Status briefly shows "Saved".
    await expect(page.locator('.editor-status')).toContainText(/Saved|Saving/, { timeout: 3_000 })
  })

  test('S4 — sandbox: API rejects ../etc path', async ({ request }) => {
    const r = await request.get(
      `http://localhost:8000/api/claude-code/tree?root=${encodeURIComponent(FIXTURE_ROOT)}&path=${encodeURIComponent('../../etc')}`,
    )
    expect(r.status()).toBe(400)
    const body = await r.json()
    expect(body.detail).toContain('escapes project root')
  })
})
