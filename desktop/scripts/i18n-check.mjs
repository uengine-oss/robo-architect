// English mode check for Robo Architect Lite: starts the app in English (ROBO_LANG=en), opens the
// home, every card's tab and the main sub-screens, and reports the Korean still on screen — what the
// translator could not translate (osI18n.missing(), new on that screen) and any Hangul left in the
// page text (user data — names in the graph — stays Korean on purpose). Read-only: it opens
// existing projects and proposals, clicks only tabs / tree rows / view toggles, never Accept /
// Destroy / Revoke, never starts a plan, implementation, validation or analysis.
//
//   node desktop/scripts/i18n-check.mjs                 # all screens
//   node desktop/scripts/i18n-check.mjs home proposals  # some of them
//   I18N_LANG=ko node desktop/scripts/i18n-check.mjs home   # Korean-mode sanity run
//
// Screens: home proposals stories process design data code constitution settings legacy
// Output: desktop/i18n/check/<NN-screen>.png (shell + tab composited) and report.json.
// Env: RA_RUNTIME (Docker runtime folder), RA_USER_DATA (user data folder — one app instance at a
// time per folder), I18N_GRAPH / I18N_FOLDER (project with design data), I18N_LEGACY_GRAPH /
// I18N_LEGACY_FOLDER (project with an analysed code graph), I18N_PROPOSAL (proposal id to open).
import { _electron as electron } from 'playwright'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const DESKTOP = path.resolve(HERE, '..')
const OUT = path.join(DESKTOP, 'i18n', 'check')
const LANG = process.env.I18N_LANG || 'en'
const RUNTIME = process.env.RA_RUNTIME || '/Users/uengine/robo-lite-src/runtime'
const USER_DATA = process.env.RA_USER_DATA || '/Users/uengine/robo-lite-src/userdata-tut'
const PROJ = process.env.RA_PROJECTS || '/Users/uengine/robo-lite-src/projects'
const GRAPH = process.env.I18N_GRAPH || 'hanbit_delivery'
const FOLDER = process.env.I18N_FOLDER || path.join(PROJ, 'hanbit-delivery')
const LEGACY_GRAPH = process.env.I18N_LEGACY_GRAPH || 'hanbit_legacy'
const LEGACY_FOLDER = process.env.I18N_LEGACY_FOLDER || path.join(PROJ, 'hanbit-legacy')
const W = 1280, H = 720, BAR = 38
const ALL = ['home', 'proposals', 'stories', 'process', 'design', 'data', 'code', 'constitution', 'settings', 'legacy']
const want = process.argv.slice(2).filter((a) => !a.startsWith('-'))
const screens = want.length ? ALL.filter((s) => want.includes(s)) : ALL
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const visible = (loc) => loc.isVisible().catch(() => false)
const report = {}
let n = 0

async function launch() {
  const env = { ...process.env }
  delete env.ELECTRON_RUN_AS_NODE
  for (const k of Object.keys(env)) if (/^CLAUDE/.test(k)) delete env[k]   // not a nested Claude session
  Object.assign(env, { ROBO_RUNTIME_MODE: 'docker', ROBO_DOCKER_RUNTIME_DIR: RUNTIME, ROBO_LANG: LANG })
  const app = await electron.launch({ args: [DESKTOP, `--user-data-dir=${USER_DATA}`], env, timeout: 120_000 })
  const win = await app.firstWindow()
  await app.evaluate(({ BrowserWindow }, [w, h]) => { const b = BrowserWindow.getAllWindows()[0]; b.setContentSize(w, h); b.center() }, [W, H])
  return { app, win }
}

async function waitReady(win) {
  for (let t0 = Date.now(); Date.now() - t0 < 600_000; await sleep(2000)) {
    const st = await win.evaluate(() => window.desktop?.app?.getRuntimeState?.()).catch(() => null)
    if (st?.data?.status === 'ready') return
    if (st?.data?.status === 'fatal') throw new Error('runtime fatal — see <userData>/logs/desktop.log')
  }
  throw new Error('runtime not ready in time')
}

async function openProject(win, graph, folder) {
  const r = await win.evaluate(([g, f]) => window.raShell.openProject(g, f), [graph, folder])
  if (!r?.ok) throw new Error(`project ${graph}: ${r?.error}`)
  await win.locator('.card:not([disabled])').first().waitFor({ timeout: 120_000 })
  await sleep(1500)
}

/** A tab (WebContentsView) for a shell target → its Playwright page. */
async function openTab(app, target) {
  const before = new Set(app.context().pages())
  await app.evaluate((_e, t) => { const w = globalThis.__raShell.firstWindow(); w.activate(w.open(t)) }, target)
  for (let i = 0; i < 150; i++) {
    const p = app.context().pages().find((x) => !before.has(x))
    if (p) {
      await p.waitForLoadState('domcontentloaded')
      await p.waitForSelector('.app-shell, .tab-panel-container, #app > *', { timeout: 60_000 }).catch(() => {})
      await sleep(3500)
      return p
    }
    await sleep(200)
  }
  throw new Error(`tab not opened: ${JSON.stringify(target)}`)
}

async function home(app) {
  await app.evaluate(() => globalThis.__raShell.firstWindow().activate('home'))
  await sleep(600)
}

/** The window as the user sees it: the shell (tab strip) with the active tab laid over it. */
async function snap(app, name) {
  const file = path.join(OUT, `${name}.png`)
  const parts = await app.evaluate(async () => {
    const w = globalThis.__raShell.firstWindow()
    const [cw, ch] = w.win.getContentSize()
    const s = await w.win.webContents.capturePage({ x: 0, y: 0, width: cw, height: ch })
    const t = w.tab(w.active)
    const ti = t ? await t.view.webContents.capturePage() : null
    return { s: s.toPNG().toString('base64'), t: ti ? ti.toPNG().toString('base64') : null, cw }
  })
  const tmp = path.join(OUT, `.${name}`)
  fs.writeFileSync(`${tmp}-s.png`, Buffer.from(parts.s, 'base64'))
  if (parts.t) fs.writeFileSync(`${tmp}-t.png`, Buffer.from(parts.t, 'base64'))
  execFileSync('python3', ['-c', `
import sys
from PIL import Image
s = Image.open(sys.argv[1]).convert('RGB')
if sys.argv[2] != '-':
    t = Image.open(sys.argv[2]).convert('RGB')
    k = s.width / ${parts.cw}
    s.paste(t.resize((s.width, s.height - round(${BAR} * k))), (0, round(${BAR} * k)))
s.save(sys.argv[3])`, `${tmp}-s.png`, parts.t ? `${tmp}-t.png` : '-', file])
  for (const f of [`${tmp}-s.png`, `${tmp}-t.png`]) fs.rmSync(f, { force: true })
}

const seen = new WeakMap()   // page → missing strings already reported
/** Record a screen: screenshot + the Korean the translator missed (new here) + Hangul on screen. */
async function check(app, page, name) {
  const key = `${String(++n).padStart(2, '0')}-${name}`
  await settle(page)
  await sleep(800)
  await snap(app, key).catch((e) => console.log('snap failed', e.message))
  const r = await page.evaluate(() => {
    const re = /[가-힣]/
    const missing = (window.osI18n && window.osI18n.missing()) || []
    const left = [...new Set(document.body.innerText.split('\n').map((l) => l.trim()).filter((l) => re.test(l)))]
    const attrs = [...new Set([...document.querySelectorAll('[title],[placeholder],[aria-label]')]
      .flatMap((el) => ['title', 'placeholder', 'aria-label'].map((a) => el.getAttribute(a) || ''))
      .filter((v) => re.test(v)))]
    // English that does not fit: text cut by its box (one line, overflow hidden or ellipsis)
    const overflow = [...document.querySelectorAll('button, .tab-btn, .rail__item span, th, label, .card-title, h1, h2, h3')]
      .filter((el) => el.offsetParent && el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== 'visible' && (el.innerText || '').trim())
      .map((el) => (el.innerText || '').trim().slice(0, 60))
    return { lang: window.osI18n ? window.osI18n.lang : '(no translator)', htmlLang: document.documentElement.lang, missing, left, attrs, overflow: [...new Set(overflow)] }
  }).catch((e) => ({ error: e.message }))
  const old = seen.get(page) || new Set()
  r.missing = (r.missing || []).filter((m) => !old.has(m))
  r.missing.forEach((m) => old.add(m))
  seen.set(page, old)
  report[key] = r
  console.log(`${key}: lang=${r.lang} missing=${r.missing.length} left=${(r.left || []).length} attrs=${(r.attrs || []).length} overflow=${(r.overflow || []).length}${r.error ? ' ' + r.error : ''}`)
  return r
}

/** Wait until nothing on the page says it is still loading (the graph DB can be slow). */
async function settle(page, ms = 45_000) {
  const t0 = Date.now()
  while (Date.now() - t0 < ms) {
    const busy = await page.evaluate(() => /(^|\n)\s*(Loading|로딩|불러오는)[^\n]{0,30}(\n|$)/i.test(document.body.innerText)).catch(() => false)
    if (!busy) return
    await sleep(1000)
  }
}

async function clickIf(loc, wait = 1800) {
  if (!(await visible(loc))) return false
  await loc.click({ timeout: 5000 }).catch(() => {})
  await sleep(wait)
  return true
}

// ── screens ──
const S = {
  async home({ app, win }) {
    await home(app)
    await check(app, win, 'home')
    // the project picker (Switch project), then back without changing anything
    if (await clickIf(win.locator('[data-act="switch"]').first(), 800)) {
      await check(app, win, 'home-project-picker')
      await clickIf(win.locator('[data-act="cancel"]').first(), 600)
    }
  },

  async proposals({ app }) {
    const pg = await openTab(app, { view: 'Proposals' })
    await check(app, pg, 'proposals')
    const list = await pg.evaluate(async () => (await (await fetch('/api/proposals/?limit=100')).json())).catch(() => [])
    const items = Array.isArray(list) ? list : list.proposals || list.items || []
    const pick = process.env.I18N_PROPOSAL
      ? items.filter((p) => p.id === process.env.I18N_PROPOSAL)
      : [items.find((p) => p.status === 'ACCEPTED'), items.find((p) => p.status === 'SUBMITTED')].filter(Boolean)
    console.log('proposals:', items.map((p) => `${p.id}:${p.status}:${p.mode || ''}`).join(' '))
    for (const p of pick) {
      await clickIf(pg.locator('.proposal-item', { hasText: p.id }).first(), 2500)
      const tabs = pg.locator('.detail-tabs .tab-btn')
      const count = await tabs.count()
      for (let i = 0; i < count; i++) {
        const label = ((await tabs.nth(i).innerText().catch(() => '')) || '').trim()
        // the validation view starts a run by itself on a TESTING proposal without results
        if (/Validation|검증/.test(label) && p.status === 'TESTING') continue
        await tabs.nth(i).click().catch(() => {})
        await sleep(2500)
        await check(app, pg, `proposal-${p.id}-${label.replace(/[^\w]+/g, '_').slice(0, 24)}`)
      }
    }
    // the New Proposal dialog (opened, not submitted)
    if (await clickIf(pg.locator('.proposals-panel button, .panel-header button').filter({ hasText: /New Proposal|새 Proposal/ }).first(), 1500)) {
      await check(app, pg, 'proposal-create')
      await pg.keyboard.press('Escape').catch(() => {})
      await clickIf(pg.getByRole('button', { name: /^(Cancel|취소)$/ }).first(), 600)
    }
  },

  async stories({ app }) {
    const st = await openTab(app, { view: 'Stories' })
    await check(app, st, 'requirements')
    for (const level of ['epic', 'feature']) {
      const carets = st.locator(`.tree-node--${level} > .tree-row .caret`)
      const c = await carets.count()
      for (let i = 0; i < c; i++) {
        const el = carets.nth(i)
        if ((await el.innerText().catch(() => '')).includes('▸')) { await el.click().catch(() => {}); await sleep(250) }
      }
    }
    await check(app, st, 'requirements-tree')
    if (await clickIf(st.locator('.us-row').first(), 2500)) {
      await check(app, st, 'story-detail')
      for (const tab of [/Design trace|설계 궤적/, /History|이력/]) {
        if (await clickIf(st.getByRole('button', { name: tab }).first(), 1800)) {
          await check(app, st, `story-${String(tab).replace(/[^\w]+/g, '').slice(0, 14)}`)
          await st.keyboard.press('Escape').catch(() => {})
        }
      }
    }
  },

  async process({ app }) {
    const pr = await openTab(app, { view: 'Process' })
    await check(app, pr, 'process-bpm')
    if (await clickIf(pr.getByRole('button', { name: /Event Modeling|이벤트 모델링/ }).first(), 2500)) {
      await check(app, pr, 'process-event-modeling')
    }
  },

  async design({ app }) {
    const ds = await openTab(app, { view: 'Design' })
    await check(app, ds, 'design')
    const bc = ds.locator('.left-panel .tree-node__header').first()
    if (await visible(bc)) {
      await bc.dblclick().catch(() => {})
      await sleep(3000)
      await ds.locator('.vue-flow__controls-fitview').first().click().catch(() => {})
      await sleep(1200)
      await check(app, ds, 'design-canvas')
      const node = ds.locator('.vue-flow__node').nth(1)
      if (await clickIf(node, 1500)) await check(app, ds, 'design-node-selected')
      // double-click: the node's properties in the right panel (looked at, not edited)
      if (await visible(node)) {
        await node.dblclick().catch(() => {})
        await sleep(2000)
        await check(app, ds, 'design-node-properties')
        await ds.keyboard.press('Escape').catch(() => {})
      }
    }
  },

  async data({ app }) {
    const dt = await openTab(app, { view: 'Data' })
    await check(app, dt, 'data')
    const bc = dt.locator('.left-panel .tree-node__header').first()
    if (await visible(bc)) {
      await bc.dblclick().catch(() => {})
      await sleep(3000)
      await check(app, dt, 'data-model')
    }
  },

  async code({ app }) {
    const cd = await openTab(app, { view: 'Code' })
    await sleep(2000)
    await check(app, cd, 'code')
  },

  async constitution({ app }) {
    const cs = await openTab(app, { view: 'Design', constitution: true })
    await sleep(1500)
    await check(app, cs, 'constitution')
    for (const t of [/^(Preview|미리보기)$/, /^(Edit|편집)$/]) {
      if (await clickIf(cs.getByRole('button', { name: t }).first(), 1200)) await check(app, cs, `constitution-${String(t).replace(/[^\w]+/g, '').slice(0, 10)}`)
    }
  },

  async settings({ app }) {
    const pg = await openTab(app, { view: 'Proposals' })
    if (await clickIf(pg.locator('.rail__btn[title="Settings"], .rail__btn[title="설정"]').first(), 1200)) {
      await check(app, pg, 'settings')
      await pg.keyboard.press('Escape').catch(() => {})
    }
  },

  async legacy({ app, win }) {
    await home(app)
    await openProject(win, LEGACY_GRAPH, LEGACY_FOLDER)
    const lg = await openTab(app, { view: 'Legacy' })
    await sleep(3000)
    const items = lg.locator('.rail__item')
    const count = await items.count()
    for (let i = 0; i < count; i++) {
      const label = ((await items.nth(i).innerText().catch(() => '')) || '').trim()
      await items.nth(i).click().catch(() => {})
      await sleep(4500)
      await check(app, lg, `legacy-${label.replace(/[^\w]+/g, '_').slice(0, 20)}`)
    }
  },
}

fs.mkdirSync(OUT, { recursive: true })
const { app, win } = await launch()
// the theme the user had (shared by the shell and the tabs: localStorage app_theme) — the check
// runs in I18N_THEME (default dark, like the tutorial captures) and puts it back afterwards
const theme0 = process.env.I18N_THEME_RESTORE || (await win.evaluate(() => localStorage.getItem('app_theme')).catch(() => null))
const setTheme = (t) => win.evaluate((v) => { try { if (v) localStorage.setItem('app_theme', v); else localStorage.removeItem('app_theme') } catch {} if (v) document.documentElement.dataset.theme = v }, t).catch(() => {})
await setTheme(process.env.I18N_THEME || 'dark')
try {
  await waitReady(win)
  await win.locator('.project, .project.pick').first().waitFor({ timeout: 600_000 })
  const needsDesign = screens.some((s) => s !== 'legacy')
  if (needsDesign) await openProject(win, GRAPH, FOLDER)
  for (const s of screens) {
    try { await S[s]({ app, win }) } catch (e) { report[s] = { error: e.message }; console.log(`${s}: ERROR ${e.message}`) }
  }
} finally {
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 1))
  // leave the last project as it was found: the legacy run ends on the legacy project; otherwise
  // the check opened the design project — put the legacy one back
  if (!screens.includes('legacy')) await openProject(win, LEGACY_GRAPH, LEGACY_FOLDER).catch(() => {})
  await setTheme(theme0)
  await app.close().catch(() => {})
}
const all = new Set()
for (const v of Object.values(report)) for (const m of v.missing || []) all.add(m)
console.log(`\n${all.size} distinct missing:`)
for (const m of all) console.log('  ·', JSON.stringify(m).slice(0, 140))
