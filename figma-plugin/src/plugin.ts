/**
 * RoboArchitect Sync — Figma Plugin (sandbox code)
 */

figma.showUI(__html__, { width: 320, height: 400, themeColors: true })

// ── Persistent config (Figma clientStorage; survives plugin/Figma restarts) ──
//
// Two keys:
//   roboArchitectBackendUrl     last successfully-connected Backend URL
//   roboArchitectFileKeyOverride manual file-key override (used when the
//                                sandbox's auto-detect figma.fileKey doesn't
//                                fit, e.g., running against a different file
//                                than the one open in Figma's tab)
//
// On plugin launch we read both and post them to the UI so the input fields
// pre-fill BEFORE auto-detection kicks in.

const CFG_KEY_URL = 'roboArchitectBackendUrl'
const CFG_KEY_FILE_KEY = 'roboArchitectFileKeyOverride'

async function loadAndSendStoredConfig(): Promise<void> {
  try {
    const [savedUrl, savedFileKey] = await Promise.all([
      figma.clientStorage.getAsync(CFG_KEY_URL),
      figma.clientStorage.getAsync(CFG_KEY_FILE_KEY),
    ])
    figma.ui.postMessage({
      type: 'RESTORED_CONFIG',
      backendUrl: typeof savedUrl === 'string' ? savedUrl : null,
      fileKeyOverride: typeof savedFileKey === 'string' ? savedFileKey : null,
      autoDetectedFileKey: figma.fileKey || null,
    })
  } catch (_e) { /* best-effort */ }
}

// Fire as soon as the UI iframe is alive. PLUGIN_READY (existing message)
// already gives a hook but it carries figma.fileKey only; we add a richer
// RESTORED_CONFIG so the UI can decide which value to pre-fill.
setTimeout(() => { void loadAndSendStoredConfig() }, 50)

// ── Message router ──

figma.ui.onmessage = async (msg: any) => {
  try {
    switch (msg.type) {
      case 'UPDATE_NODES':
        await handleNodeUpdates(msg.nodeUpdates || [])
        break
      case 'UPDATE_TEXT':
        await handleTextUpdate(msg.nodeId, msg.text)
        break
      case 'SYNC_FRAME':
        await handleSyncFrame(msg)
        break
      case 'GET_SELECTION':
        sendSelection()
        break
      case 'GET_FILE_KEY':
        figma.ui.postMessage({ type: 'FILE_KEY', fileKey: figma.fileKey })
        break
      case 'LIST_FRAMES':
        listAllFrames()
        break
      case 'FIND_AND_REPLACE_TEXT':
        await handleFindAndReplaceText(msg)
        break
      case 'EXPORT_FRAME':
        handleExportFrame(msg)
        break
      case 'CREATE_PAGE':
        await handleCreatePage(msg)
        break
      case 'CREATE_FRAME_IN_PAGE':
        await handleCreateFrameInPage(msg)
        break
      case 'UPDATE_FRAME_FROM_SCENE_GRAPH':
        await handleUpdateFrameFromSceneGraph(msg)
        break
      case 'EXPORT_FRAME_BY_ID':
        await handleExportFrameById(msg)
        break
      case 'SAVE_CONFIG': {
        // Persist Backend URL and optional file-key override across sessions.
        // Empty / null values clear the slot.
        const setOrClear = async (key: string, val: unknown): Promise<void> => {
          if (typeof val === 'string' && val.trim()) {
            await figma.clientStorage.setAsync(key, val.trim())
          } else if (val === null || val === '') {
            await figma.clientStorage.deleteAsync(key)
          }
        }
        await Promise.all([
          setOrClear(CFG_KEY_URL, msg.backendUrl),
          setOrClear(CFG_KEY_FILE_KEY, msg.fileKeyOverride),
        ])
        figma.ui.postMessage({ type: 'CONFIG_SAVED' })
        break
      }
      case 'RESET_CONFIG': {
        await Promise.all([
          figma.clientStorage.deleteAsync(CFG_KEY_URL),
          figma.clientStorage.deleteAsync(CFG_KEY_FILE_KEY),
        ])
        figma.ui.postMessage({ type: 'CONFIG_RESET' })
        break
      }
      case 'SCAN_COMPONENTS':
        await handleScanComponents()
        break
    }
  } catch (e: any) {
    figma.ui.postMessage({ type: 'ERROR', message: (e && e.message) || String(e) })
  }
}

// ── CREATE_PAGE: feature 016 / US2 / FR-006 ──
//
// Backend asks plugin to create a Figma page named after a storyboard's
// entry-command displayName. The reply (CREATE_PAGE_RESULT) carries the
// new page's id/name plus the same requestId so the backend can correlate
// it with the original CREATE_PAGE request via plugin_messages._resolve.
async function handleCreatePage(msg: { requestId?: string; name?: string }) {
  const requestId = msg.requestId
  const name = (msg.name || '').trim()
  try {
    if (!name) {
      figma.ui.postMessage({
        type: 'CREATE_PAGE_RESULT',
        requestId,
        ok: false,
        error: '페이지 이름이 비어 있습니다.',
      })
      return
    }
    const page = figma.createPage()
    page.name = name
    figma.ui.postMessage({
      type: 'CREATE_PAGE_RESULT',
      requestId,
      ok: true,
      figmaPageId: page.id,
      figmaPageName: page.name,
    })
  } catch (e: any) {
    figma.ui.postMessage({
      type: 'CREATE_PAGE_RESULT',
      requestId,
      ok: false,
      error: (e && e.message) || String(e) || 'Figma 페이지 생성 실패',
    })
  }
}

// ── CREATE_FRAME_IN_PAGE: feature 016 / US3 + FR-019b ──
//
// Backend asks plugin to create a new top-level frame inside a specific
// page (resolved from a storyboard mapping) and populate it from a
// SerializedSceneGraph. Routes through `renderJsxSceneGraphIntoFrame`
// (recursive renderer for JSX-primitive sceneGraphs from open-pencil's
// wireframe service). Old `buildFrameFromSceneGraph` (component-based)
// is retained for the legacy SYNC_FRAME flow (009).
const SPEC024_PLUGIN_BUILD = 'v7'

async function handleCreateFrameInPage(msg: {
  requestId?: string
  figmaPageId?: string
  frameName?: string
  sceneGraph?: any
}) {
  const requestId = msg.requestId
  // Diagnostic: surface the build id so the backend can tell whether the
  // currently-running plugin window is the freshly-built bundle.
  try { figma.notify(`spec024 plugin build ${SPEC024_PLUGIN_BUILD}`) } catch (_e) {}
  const fail = (error: string) => figma.ui.postMessage({
    type: 'CREATE_FRAME_IN_PAGE_RESULT',
    requestId,
    ok: false,
    error,
    buildId: SPEC024_PLUGIN_BUILD,
  })
  try {
    if (!msg.figmaPageId) return fail('figmaPageId가 비어 있습니다.')
    const pageNode = figma.getNodeById(msg.figmaPageId)
    if (!pageNode || pageNode.type !== 'PAGE') {
      return fail(`Figma 페이지를 찾을 수 없습니다 (id=${msg.figmaPageId}).`)
    }
    const page = pageNode as PageNode

    // Switch current page so subsequent createFrame() lands here.
    figma.currentPage = page

    const frame = figma.createFrame()
    frame.name = (msg.frameName || 'Wireframe').trim() || 'Wireframe'
    frame.resize(375, 812)
    // Lay out new frames horizontally to keep the page browsable.
    const existingCount = page.children.length - 1
    frame.x = Math.max(0, existingCount) * 420
    frame.y = 0
    frame.fills = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 1 }]

    let nodesCreated = 0
    let nodesFailed = 0
    let renderErrors: string[] = []
    if (msg.sceneGraph && msg.sceneGraph.nodes && msg.sceneGraph.rootId) {
      const result = await renderJsxSceneGraphIntoFrame(
        frame,
        msg.sceneGraph.nodes,
        msg.sceneGraph.rootId,
      )
      nodesCreated = result.created
      nodesFailed = result.failed
      renderErrors = result.errors
    }

    // Scroll the viewport so the new frame is visible when the user
    // switches to the new page (Figma does not auto-center on programmatic
    // frame creation — spec 024 smoke test bug, user saw an empty viewport).
    try {
      figma.viewport.scrollAndZoomIntoView([frame])
    } catch (_e) { /* best-effort */ }

    const ackBody: any = {
      type: 'CREATE_FRAME_IN_PAGE_RESULT',
      requestId,
      ok: true,
      figmaPageId: page.id,
      figmaNodeId: frame.id,
      figmaFrameName: frame.name,
      nodesCreated,
      nodesFailed,
      buildId: SPEC024_PLUGIN_BUILD,
    }
    if (renderErrors.length > 0) {
      // Up the slice limit so the v4/v5 trace lines all make it through.
      ackBody.renderErrors = renderErrors.slice(0, 40)
    }
    figma.ui.postMessage(ackBody)
  } catch (e: any) {
    fail((e && e.message) || String(e) || 'Figma 프레임 생성 실패')
  }
}

// ── UPDATE_FRAME_FROM_SCENE_GRAPH: feature 016 bidirectional sync ──
//
// In-place update of an existing Figma frame: clear all children and
// re-render from a (possibly modified) sceneGraph using the same recursive
// renderer used by CREATE_FRAME_IN_PAGE. Used when Robo Architect's local
// sceneGraph has changed and needs to flow back to the linked Figma frame.
async function handleUpdateFrameFromSceneGraph(msg: {
  requestId?: string
  figmaNodeId?: string
  sceneGraph?: any
}) {
  const requestId = msg.requestId
  const fail = (error: string) => figma.ui.postMessage({
    type: 'UPDATE_FRAME_RESULT',
    requestId,
    ok: false,
    error,
  })
  try {
    if (!msg.figmaNodeId) return fail('figmaNodeId가 비어 있습니다.')
    const node = figma.getNodeById(msg.figmaNodeId)
    if (!node || node.type !== 'FRAME') {
      return fail(`Figma 프레임을 찾을 수 없습니다 (id=${msg.figmaNodeId}).`)
    }
    const frame = node as FrameNode

    // Clear existing children before re-rendering.
    for (const child of [...frame.children]) {
      try { child.remove() } catch (_e) { /* noop */ }
    }
    // Reset auto-layout so re-render's settings take effect cleanly.
    try { frame.layoutMode = 'NONE' } catch (_e) {}

    let nodesCreated = 0
    let nodesFailed = 0
    let renderErrors: string[] = []
    if (msg.sceneGraph && msg.sceneGraph.nodes && msg.sceneGraph.rootId) {
      const result = await renderJsxSceneGraphIntoFrame(
        frame,
        msg.sceneGraph.nodes,
        msg.sceneGraph.rootId,
      )
      nodesCreated = result.created
      nodesFailed = result.failed
      renderErrors = result.errors
    }

    const ackBody: any = {
      type: 'UPDATE_FRAME_RESULT',
      requestId,
      ok: true,
      figmaNodeId: frame.id,
      figmaFrameName: frame.name,
      nodesCreated,
      nodesFailed,
    }
    if (renderErrors.length > 0) ackBody.renderErrors = renderErrors.slice(0, 5)
    figma.ui.postMessage(ackBody)
  } catch (e: any) {
    fail((e && e.message) || String(e) || 'Figma 프레임 업데이트 실패')
  }
}

// ── EXPORT_FRAME_BY_ID: feature 016 Figma → RA pull via plugin ──
//
// Read a Figma frame's current state (via the plugin, no Figma API token
// required) and ship its full node tree back so the backend can convert it
// to a sceneGraph and update the linked UI node.
async function handleExportFrameById(msg: {
  requestId?: string
  figmaNodeId?: string
}) {
  const requestId = msg.requestId
  const fail = (error: string) => figma.ui.postMessage({
    type: 'EXPORT_FRAME_BY_ID_RESULT',
    requestId,
    ok: false,
    error,
  })
  try {
    if (!msg.figmaNodeId) return fail('figmaNodeId가 비어 있습니다.')
    const node = figma.getNodeById(msg.figmaNodeId)
    if (!node || node.type !== 'FRAME') {
      return fail(`Figma 프레임을 찾을 수 없습니다 (id=${msg.figmaNodeId}).`)
    }
    const frame = node as FrameNode
    const tree = serializeFigmaNode(frame)
    figma.ui.postMessage({
      type: 'EXPORT_FRAME_BY_ID_RESULT',
      requestId,
      ok: true,
      figmaNodeId: frame.id,
      figmaFrameName: frame.name,
      frameData: tree,
    })
  } catch (e: any) {
    fail((e && e.message) || String(e) || 'Figma 프레임 export 실패')
  }
}

// Lightweight Figma node serializer for EXPORT_FRAME_BY_ID. Produces a
// structure the backend converter understands (mirrors the handleExportFrame
// payload but reachable by node id rather than by selection).
//
// Captures enough fields that the round-tripped sceneGraph can be re-rendered
// in open-pencil's CanvasKit FrameEditor (otherwise everything stacks at
// (0,0) with no fills and looks blank).
function serializeFigmaNode(n: any): any {
  const out: any = {
    id: n.id,
    name: n.name,
    type: n.type,
    visible: n.visible !== false,
  }
  // Geometry
  if (typeof n.x === 'number') out.x = n.x
  if (typeof n.y === 'number') out.y = n.y
  if (typeof n.width === 'number') out.width = n.width
  if (typeof n.height === 'number') out.height = n.height
  if (typeof n.rotation === 'number') out.rotation = n.rotation
  if (typeof n.opacity === 'number') out.opacity = n.opacity

  // Paint
  if (n.fills && n.fills !== figma.mixed) out.fills = n.fills
  if (n.strokes) out.strokes = n.strokes
  if (n.effects) out.effects = n.effects
  if (typeof n.cornerRadius === 'number') out.cornerRadius = n.cornerRadius
  if (typeof n.topLeftRadius === 'number') out.topLeftRadius = n.topLeftRadius
  if (typeof n.topRightRadius === 'number') out.topRightRadius = n.topRightRadius
  if (typeof n.bottomLeftRadius === 'number') out.bottomLeftRadius = n.bottomLeftRadius
  if (typeof n.bottomRightRadius === 'number') out.bottomRightRadius = n.bottomRightRadius
  if (n.clipsContent === true || n.clipsContent === false) out.clipsContent = n.clipsContent

  // Auto-layout (FRAME / SECTION)
  if (n.layoutMode) out.layoutMode = n.layoutMode
  if (typeof n.itemSpacing === 'number') out.itemSpacing = n.itemSpacing
  if (typeof n.paddingTop === 'number') out.paddingTop = n.paddingTop
  if (typeof n.paddingRight === 'number') out.paddingRight = n.paddingRight
  if (typeof n.paddingBottom === 'number') out.paddingBottom = n.paddingBottom
  if (typeof n.paddingLeft === 'number') out.paddingLeft = n.paddingLeft
  if (n.primaryAxisSizingMode) out.primaryAxisSizing = n.primaryAxisSizingMode === 'AUTO' ? 'HUG' : 'FIXED'
  if (n.counterAxisSizingMode) out.counterAxisSizing = n.counterAxisSizingMode === 'AUTO' ? 'HUG' : 'FIXED'
  if (n.primaryAxisAlignItems) out.primaryAxisAlign = n.primaryAxisAlignItems
  if (n.counterAxisAlignItems) out.counterAxisAlign = n.counterAxisAlignItems
  if (n.layoutWrap) out.layoutWrap = n.layoutWrap
  if (typeof n.layoutGrow === 'number') out.layoutGrow = n.layoutGrow
  if (n.layoutAlign) out.layoutAlignSelf = n.layoutAlign

  // Text
  if (n.type === 'TEXT') {
    out.characters = n.characters
    if (n.fontSize !== figma.mixed) out.fontSize = n.fontSize
    if (n.fontName !== figma.mixed) out.fontName = n.fontName
    if (n.textAlignHorizontal) out.textAlignHorizontal = n.textAlignHorizontal
    if (n.textAlignVertical) out.textAlignVertical = n.textAlignVertical
    if (n.letterSpacing && typeof n.letterSpacing === 'object' && typeof n.letterSpacing.value === 'number') {
      out.letterSpacing = n.letterSpacing.value
    }
    if (n.lineHeight && typeof n.lineHeight === 'object' && typeof n.lineHeight.value === 'number') {
      out.lineHeight = n.lineHeight.value
    }
    if (n.textAutoResize) out.textAutoResize = n.textAutoResize
    if (n.textCase) out.textCase = n.textCase
    if (n.textDecoration) out.textDecoration = n.textDecoration
  }
  if ('children' in n) {
    out.children = []
    for (const c of n.children) out.children.push(serializeFigmaNode(c))
  }
  return out
}

// ── Recursive renderer for JSX-primitive sceneGraphs (016 / FR-019b) ──
//
// open-pencil's wireframe-service emits sceneGraphs whose leaves are TEXT,
// RECTANGLE, ELLIPSE etc., and whose containers are FRAME / GROUP. The
// older `buildFrameFromSceneGraph` only handled COMPONENT INSTANCE leaves,
// so JSX-primitive sceneGraphs rendered as empty boxes (frames created but
// no children populated). This function recurses the full tree and creates
// matching Figma nodes with auto-layout, fills, text styling, and corner
// radius preserved.
async function renderJsxSceneGraphIntoFrame(
  outerFrame: FrameNode,
  nodes: Record<string, any>,
  rootId: string,
): Promise<{ created: number; failed: number; errors: string[] }> {
  const ctx = { created: 0, failed: 0, errors: [] as string[] }

  // Find the wireframe FRAME node: rootId → CANVAS → first FRAME with childIds.
  let wireframeId: string | null = null
  const root = nodes[rootId]
  if (root) {
    for (const cid of root.childIds || []) {
      const c = nodes[cid]
      if (!c) continue
      if (c.type === 'CANVAS') {
        for (const fid of c.childIds || []) {
          const f = nodes[fid]
          if (f && f.type === 'FRAME') { wireframeId = fid; break }
        }
      } else if (c.type === 'FRAME') {
        wireframeId = cid
      }
      if (wireframeId) break
    }
  }
  if (!wireframeId) {
    // Fallback: any FRAME with children.
    for (const [nid, n] of Object.entries(nodes)) {
      if (n.type === 'FRAME' && (n.childIds || []).length > 0 && nid !== rootId) {
        wireframeId = nid; break
      }
    }
  }
  if (!wireframeId) {
    ctx.errors.push('No wireframe FRAME node found in sceneGraph')
    ctx.failed = 1
    return ctx
  }

  // Pre-load all fonts referenced by TEXT nodes (Figma plugin requirement).
  const fontsToLoad = new Set<string>()
  for (const n of Object.values(nodes)) {
    if (n.type === 'TEXT') {
      const family = n.fontFamily || 'Inter'
      const style = sgWeightToStyle(n.fontWeight, n.italic)
      fontsToLoad.add(family + '|' + style)
    }
  }
  // Always have Inter Regular as a fallback.
  fontsToLoad.add('Inter|Regular')
  for (const key of fontsToLoad) {
    const [family, style] = key.split('|')
    try { await figma.loadFontAsync({ family, style }) }
    catch (_e) {
      // If the requested style isn't available, fall back to Regular.
      try { await figma.loadFontAsync({ family, style: 'Regular' }) } catch (_e2) { /* ignore */ }
    }
  }

  // Apply the wireframe FRAME's own properties to the outerFrame, then
  // recurse its children INTO outerFrame. This way the outerFrame gets
  // the wireframe's auto-layout, fills, padding, gap — not a hard-coded
  // 375×812 white box.
  const wireframe = nodes[wireframeId]
  applyContainerProps(outerFrame, wireframe)
  applyFillsAndStrokes(outerFrame, wireframe)
  applyAutoLayout(outerFrame, wireframe)
  // outerFrame already named by handleCreateFrameInPage; preserve.

  for (const cid of wireframe.childIds || []) {
    await renderSceneNode(outerFrame, cid, nodes, ctx)
  }
  return ctx
}

async function renderSceneNode(
  parent: FrameNode | GroupNode,
  nodeId: string,
  nodes: Record<string, any>,
  ctx: { created: number; failed: number; errors: string[] },
): Promise<void> {
  const sn = nodes[nodeId]
  if (!sn) { ctx.failed++; return }
  try {
    if (sn.type === 'FRAME' || sn.type === 'SECTION' || sn.type === 'GROUP') {
      const f = figma.createFrame()
      f.name = sn.name || 'Frame'
      // Add to parent BEFORE applying size/layout — auto-layout sizing rules
      // depend on parent's layoutMode being known.
      parent.appendChild(f)
      applyContainerProps(f, sn)
      applyFillsAndStrokes(f, sn)
      applyAutoLayout(f, sn)
      ctx.created++
      for (const cid of sn.childIds || []) {
        await renderSceneNode(f, cid, nodes, ctx)
      }
    } else if (sn.type === 'TEXT') {
      const t = figma.createText()
      t.name = sn.name || 'Text'
      const family = sn.fontFamily || 'Inter'
      const style = sgWeightToStyle(sn.fontWeight, sn.italic)
      try { t.fontName = { family, style } }
      catch (_e) { t.fontName = { family: 'Inter', style: 'Regular' } }
      t.characters = sn.text || ''
      if (typeof sn.fontSize === 'number') t.fontSize = sn.fontSize
      if (sn.textAlignHorizontal) {
        try { t.textAlignHorizontal = sn.textAlignHorizontal as any } catch (_e) {}
      }
      if (typeof sn.letterSpacing === 'number' && sn.letterSpacing !== 0) {
        try { t.letterSpacing = { value: sn.letterSpacing, unit: 'PIXELS' } } catch (_e) {}
      }
      applyFillsToText(t, sn)
      // Add after styling for Figma to pick up text properties cleanly.
      parent.appendChild(t)
      // Free positioning only when parent has no auto-layout.
      const parentLayout = (parent as any).layoutMode
      if (parentLayout === 'NONE' || parentLayout === undefined) {
        if (typeof sn.x === 'number') t.x = sn.x
        if (typeof sn.y === 'number') t.y = sn.y
      }
      ctx.created++
    } else if (sn.type === 'RECTANGLE') {
      const r = figma.createRectangle()
      r.name = sn.name || 'Rectangle'
      parent.appendChild(r)
      applyContainerProps(r, sn)
      applyFillsAndStrokes(r, sn)
      ctx.created++
    } else if (sn.type === 'ELLIPSE') {
      const e = figma.createEllipse()
      e.name = sn.name || 'Ellipse'
      parent.appendChild(e)
      applyContainerProps(e, sn)
      applyFillsAndStrokes(e, sn)
      ctx.created++
    } else if (sn.type === 'LINE') {
      const l = figma.createLine()
      l.name = sn.name || 'Line'
      parent.appendChild(l)
      applyContainerProps(l, sn)
      applyFillsAndStrokes(l, sn)
      ctx.created++
    } else if (sn.type === 'INSTANCE') {
      // Spec 024 — sceneGraph references a Figma COMPONENT / COMPONENT_SET by
      // name. Look up the local component, instantiate, append, then apply
      // text overrides (sn.overrides: {childName: text}).
      const compName = (sn.name || '').trim().toLowerCase()
      let comp: ComponentNode | null = null
      if (compName) {
        // Exact match first, then substring fallback (mirrors the old
        // buildFrameFromSceneGraph cache lookup).
        const visit = (node: BaseNode, exact: boolean): void => {
          if (comp) return
          const lower = (node as any).name ? (node as any).name.toLowerCase() : ''
          if (node.type === 'COMPONENT') {
            if (exact ? lower === compName : (lower.includes(compName) || compName.includes(lower))) {
              comp = node as ComponentNode; return
            }
          } else if (node.type === 'COMPONENT_SET') {
            if (exact ? lower === compName : (lower.includes(compName) || compName.includes(lower))) {
              const set = node as ComponentSetNode
              const variant = (set as any).defaultVariant || (set.children && set.children[0])
              if (variant && variant.type === 'COMPONENT') { comp = variant as ComponentNode; return }
            }
          }
          if ('children' in node) {
            for (const c of (node as ChildrenMixin).children) {
              visit(c, exact)
              if (comp) return
            }
          }
        }
        for (const page of figma.root.children) { visit(page, true); if (comp) break }
        if (!comp) {
          for (const page of figma.root.children) { visit(page, false); if (comp) break }
        }
      }
      if (!comp) {
        // Fallback (v7): the bound Figma file doesn't actually contain a
        // matching COMPONENT — most commonly because the architect started
        // from an empty file with no design system. Instead of failing
        // silently and leaving an invisible gap in the wireframe, render a
        // grey placeholder FRAME labelled with the missing component name.
        // The user still sees the spatial structure the LLM intended.
        try {
          const ph = figma.createFrame()
          ph.name = `«${sn.name || 'INSTANCE'}»`
          parent.appendChild(ph)
          applyContainerProps(ph, sn)
          // Grey fill so it reads as "not the real component".
          try {
            ph.fills = [{ type: 'SOLID', color: { r: 0.92, g: 0.92, b: 0.94 }, opacity: 1 }]
          } catch (_e) {}
          try {
            ph.strokes = [{ type: 'SOLID', color: { r: 0.70, g: 0.72, b: 0.78 }, opacity: 1 }]
            ph.strokeWeight = 1
            ph.dashPattern = [4, 4]
          } catch (_e) {}
          // Tiny label so the architect can identify what should go there.
          try {
            await figma.loadFontAsync({ family: 'Inter', style: 'Regular' })
            const label = figma.createText()
            label.fontName = { family: 'Inter', style: 'Regular' }
            label.fontSize = 11
            label.characters = sn.name || 'INSTANCE'
            try { label.fills = [{ type: 'SOLID', color: { r: 0.35, g: 0.36, b: 0.42 }, opacity: 1 }] } catch (_e) {}
            ph.appendChild(label)
            // Center the label inside the placeholder when parent layout permits.
            const w = (ph as any).width || 0
            const h = (ph as any).height || 0
            try {
              label.x = Math.max(0, (w - label.width) / 2)
              label.y = Math.max(0, (h - label.height) / 2)
            } catch (_e) {}
          } catch (_e) { /* font load failed — placeholder still useful */ }
          ctx.created++
          ctx.errors.push(`INSTANCE "${sn.name}": component not found — rendered placeholder`)
        } catch (e: any) {
          ctx.failed++
          ctx.errors.push(`INSTANCE "${sn.name}" placeholder failed: ${(e && e.message) || e}`)
        }
        return
      }
      try {
        const inst = (comp as ComponentNode).createInstance()
        inst.name = sn.name || (comp as ComponentNode).name
        parent.appendChild(inst)
        // Spec 024: do NOT call applyContainerProps for INSTANCE — that would
        // overwrite the variant's natural size with the catalog bbox (which
        // for COMPONENT_SET is the size of ALL variants stacked, ~10× too tall).
        // The natural variant size from createInstance() is the right thing.
        // Apply non-size container props only (opacity, rotation, corners).
        if (typeof sn.opacity === 'number' && sn.opacity !== 1) {
          try { inst.opacity = sn.opacity } catch (_e) {}
        }
        if (typeof sn.rotation === 'number' && sn.rotation !== 0) {
          try { inst.rotation = sn.rotation } catch (_e) {}
        }
        // Spec 024 text overrides — apply 3 strategies in order:
        //   (1) Figma component-property overrides via setProperties()
        //   (2) Named text-child match (override[name] → tn.characters)
        //   (3) Generic fallback (override.text|label|title|placeholder → first text)
        // We walk the instance's TEXT descendants and replace by name match.
        const overrides = (sn.overrides && typeof sn.overrides === 'object') ? sn.overrides : null
        if (overrides) {
          // (1) Try Figma component-property overrides first. Variant TEXT
          //     properties have suffixed names like "label#1:0" — we match by
          //     stripping the suffix and lowercasing on both sides.
          try {
            const compProps = (inst as any).componentProperties as
              | Record<string, { type: string; value: any }>
              | undefined
            if (compProps) {
              const updates: Record<string, string | boolean> = {}
              for (const [overrideKey, overrideVal] of Object.entries(overrides)) {
                if (typeof overrideVal !== 'string') continue
                const okLow = overrideKey.toLowerCase()
                for (const propKey of Object.keys(compProps)) {
                  const prop = compProps[propKey]
                  if (prop.type !== 'TEXT') continue
                  // "label#1:0" → "label"
                  const bareName = propKey.split('#')[0].toLowerCase()
                  if (bareName === okLow || okLow === 'text' || okLow === 'label') {
                    updates[propKey] = overrideVal
                    break
                  }
                }
              }
              if (Object.keys(updates).length > 0) {
                ;(inst as any).setProperties(updates)
              }
            }
          } catch (_e) { /* setProperties may throw on variant mismatch */ }

          // (2 + 3) Direct text-node override fallback — works for non-property
          //     text leaves OR when setProperties didn't catch the override.
          const textNodes: TextNode[] = []
          const collect = (n: BaseNode): void => {
            if (n.type === 'TEXT') textNodes.push(n as TextNode)
            if ('children' in n) for (const c of (n as ChildrenMixin).children) collect(c)
          }
          collect(inst)
          // Build-identifier trace so renderErrors can confirm the plugin is
          // running the spec-024-v4 bundle (a stale plugin window would not
          // emit this string).
          ctx.errors.push(`[trace v4] INSTANCE "${sn.name}" overrides=${JSON.stringify(overrides)}`)

          // Robust font-loader + text setter — Figma INSTANCE text often
          // references private fonts (e.g. Pretendard) that load asynchronously
          // and that Figma sometimes reports as "unloaded" even after a
          // successful await. We use a two-tier strategy:
          //   1. Natural-font path: try to load the text's current font, then
          //      write. Preserves the component's typography.
          //   2. Inter-Regular fallback: if (1) throws OR the write throws,
          //      replace the node's fontName with Inter Regular (always
          //      loadable in Figma) and write. The text is still updated;
          //      typography may degrade.
          const safeSetText = async (tn: TextNode, val: string): Promise<boolean> => {
            // (1) Natural-font path.
            try {
              const fn = (tn as any).fontName
              if (fn === (figma as any).mixed) {
                const len = tn.characters.length
                const fonts: { family: string; style: string }[] = []
                for (let i = 0; i < len; i++) {
                  const f = tn.getRangeFontName(i, i + 1) as any
                  if (f !== (figma as any).mixed && f && f.family) fonts.push({ family: f.family, style: f.style })
                }
                for (const f of fonts) await figma.loadFontAsync(f)
              } else if (fn && fn.family) {
                await figma.loadFontAsync(fn as FontName)
              }
              tn.characters = val
              return true
            } catch (_e1: any) {
              /* fall through to Inter-Regular fallback */
            }
            // (2) Inter-Regular fallback — force the font, then write.
            try {
              await figma.loadFontAsync({ family: 'Inter', style: 'Regular' })
              ;(tn as any).fontName = { family: 'Inter', style: 'Regular' }
              tn.characters = val
              return true
            } catch (e2: any) {
              ctx.errors.push(`INSTANCE "${sn.name}" override of TEXT "${tn.name}": ${(e2 && e2.message) || e2}`)
              return false
            }
          }
          ctx.errors.push(`[trace v4] INSTANCE "${sn.name}" found ${textNodes.length} TEXT nodes: ${textNodes.map(t => `${t.name}=${JSON.stringify(t.characters).slice(0, 30)}`).join(', ')}`)
          const used = new Set<TextNode>()
          for (const [key, val] of Object.entries(overrides)) {
            if (typeof val !== 'string') continue
            for (const tn of textNodes) {
              if (used.has(tn)) continue
              if ((tn.name || '').toLowerCase() === key.toLowerCase()) {
                if (await safeSetText(tn, val)) used.add(tn)
                break
              }
            }
          }
          const generic = (overrides as any).text || (overrides as any).label || (overrides as any).title || (overrides as any).placeholder
          if (typeof generic === 'string' && textNodes.length > 0 && used.size === 0) {
            // No keyed match worked — apply the generic override to every TEXT
            // child whose current content looks like a placeholder/variant
            // label (`{xxx}`, "default", current chars equal to a known variant
            // hint). Otherwise stamp the first TEXT.
            const looksLikePlaceholder = (s: string): boolean =>
              !!s && (/^\{.+\}$/.test(s.trim()) || /^(default|placeholder|label|텍스트|text)$/i.test(s.trim()))
            let appliedAny = false
            for (const tn of textNodes) {
              if (looksLikePlaceholder(tn.characters)) {
                const beforeChars = tn.characters
                const ok = await safeSetText(tn, generic)
                ctx.errors.push(`[trace v4] INSTANCE "${sn.name}" placeholder-match ${tn.name}: ${JSON.stringify(beforeChars).slice(0, 20)} → ${ok ? 'ok' : 'failed'} actual=${JSON.stringify(tn.characters).slice(0, 30)}`)
                if (ok) appliedAny = true
              }
            }
            if (!appliedAny) {
              const tn = textNodes[0]
              const beforeChars = tn.characters
              const ok = await safeSetText(tn, generic)
              ctx.errors.push(`[trace v4] INSTANCE "${sn.name}" first-text-fallback ${tn.name}: ${JSON.stringify(beforeChars).slice(0, 20)} → ${ok ? 'ok' : 'failed'} actual=${JSON.stringify(tn.characters).slice(0, 30)}`)
            }
          }
        }
        ctx.created++
      } catch (e: any) {
        ctx.failed++
        ctx.errors.push(`INSTANCE "${sn.name}": ${(e && e.message) || e}`)
      }
    } else {
      ctx.failed++
      ctx.errors.push('Unsupported node type: ' + sn.type)
    }
  } catch (e: any) {
    ctx.failed++
    ctx.errors.push(`${sn.type} "${sn.name}": ${(e && e.message) || e}`)
  }
}

// ── Property appliers (best-effort: missing props no-op) ──

function applyContainerProps(node: any, sn: any) {
  // Size: only resize if both width/height are positive numbers.
  if (typeof sn.width === 'number' && typeof sn.height === 'number'
      && sn.width > 0 && sn.height > 0) {
    try { node.resize(sn.width, sn.height) } catch (_e) {}
  }
  if (typeof sn.opacity === 'number' && sn.opacity !== 1) {
    try { node.opacity = sn.opacity } catch (_e) {}
  }
  if (typeof sn.rotation === 'number' && sn.rotation !== 0) {
    try { node.rotation = sn.rotation } catch (_e) {}
  }
  // Independent corner radii take precedence over uniform cornerRadius.
  if (sn.independentCorners && (sn.topLeftRadius || sn.topRightRadius || sn.bottomLeftRadius || sn.bottomRightRadius)) {
    try {
      node.topLeftRadius = sn.topLeftRadius || 0
      node.topRightRadius = sn.topRightRadius || 0
      node.bottomLeftRadius = sn.bottomLeftRadius || 0
      node.bottomRightRadius = sn.bottomRightRadius || 0
    } catch (_e) {}
  } else if (typeof sn.cornerRadius === 'number' && sn.cornerRadius > 0) {
    try { node.cornerRadius = sn.cornerRadius } catch (_e) {}
  }
}

function applyFillsAndStrokes(node: any, sn: any) {
  if (Array.isArray(sn.fills) && sn.fills.length > 0) {
    try { node.fills = sn.fills.map(toFigmaPaint).filter(Boolean) } catch (_e) {}
  }
  if (Array.isArray(sn.strokes) && sn.strokes.length > 0) {
    try { node.strokes = sn.strokes.map(toFigmaPaint).filter(Boolean) } catch (_e) {}
  }
  // Border weights: per-side or uniform (best-effort).
  if (sn.independentStrokeWeights) {
    try {
      node.strokeTopWeight = sn.borderTopWeight || 0
      node.strokeRightWeight = sn.borderRightWeight || 0
      node.strokeBottomWeight = sn.borderBottomWeight || 0
      node.strokeLeftWeight = sn.borderLeftWeight || 0
    } catch (_e) {}
  } else if (typeof sn.borderTopWeight === 'number' && sn.borderTopWeight > 0) {
    try { node.strokeWeight = sn.borderTopWeight } catch (_e) {}
  }
}

function applyFillsToText(t: TextNode, sn: any) {
  // For TEXT nodes, the SOLID fill IS the text color.
  if (Array.isArray(sn.fills) && sn.fills.length > 0) {
    try { t.fills = sn.fills.map(toFigmaPaint).filter(Boolean) } catch (_e) {}
  }
}

function applyAutoLayout(frame: FrameNode, sn: any) {
  if (sn.layoutMode === 'VERTICAL' || sn.layoutMode === 'HORIZONTAL') {
    try { frame.layoutMode = sn.layoutMode } catch (_e) {}
    if (typeof sn.itemSpacing === 'number') {
      try { frame.itemSpacing = sn.itemSpacing } catch (_e) {}
    }
    if (typeof sn.paddingTop === 'number') frame.paddingTop = sn.paddingTop
    if (typeof sn.paddingRight === 'number') frame.paddingRight = sn.paddingRight
    if (typeof sn.paddingBottom === 'number') frame.paddingBottom = sn.paddingBottom
    if (typeof sn.paddingLeft === 'number') frame.paddingLeft = sn.paddingLeft
    // primary/counter sizing: HUG/FILL/FIXED → AUTO/FIXED in Figma API.
    if (sn.primaryAxisSizing === 'HUG') frame.primaryAxisSizingMode = 'AUTO'
    else if (sn.primaryAxisSizing === 'FIXED') frame.primaryAxisSizingMode = 'FIXED'
    if (sn.counterAxisSizing === 'HUG') frame.counterAxisSizingMode = 'AUTO'
    else if (sn.counterAxisSizing === 'FIXED') frame.counterAxisSizingMode = 'FIXED'
    if (sn.primaryAxisAlign) {
      try { frame.primaryAxisAlignItems = sn.primaryAxisAlign as any } catch (_e) {}
    }
    if (sn.counterAxisAlign) {
      try { frame.counterAxisAlignItems = sn.counterAxisAlign as any } catch (_e) {}
    }
    if (sn.layoutWrap) {
      try { frame.layoutWrap = sn.layoutWrap as any } catch (_e) {}
    }
  }
}

function toFigmaPaint(p: any): Paint | null {
  if (!p || p.visible === false) return null
  if (p.type === 'SOLID' && p.color) {
    const r = typeof p.color.r === 'number' ? p.color.r : 0
    const g = typeof p.color.g === 'number' ? p.color.g : 0
    const b = typeof p.color.b === 'number' ? p.color.b : 0
    let opacity: number = 1
    if (typeof p.opacity === 'number') opacity = p.opacity
    else if (typeof p.color.a === 'number') opacity = p.color.a
    const out: SolidPaint = {
      type: 'SOLID',
      color: { r, g, b },
      opacity,
    }
    return out
  }
  // GRADIENT / IMAGE not implemented — paint omitted.
  return null
}

function sgWeightToStyle(weight: number | undefined, italic: boolean | undefined): string {
  const w = weight || 400
  let base = 'Regular'
  if (w <= 100) base = 'Thin'
  else if (w <= 200) base = 'ExtraLight'
  else if (w <= 300) base = 'Light'
  else if (w <= 400) base = 'Regular'
  else if (w <= 500) base = 'Medium'
  else if (w <= 600) base = 'SemiBold'
  else if (w <= 700) base = 'Bold'
  else if (w <= 800) base = 'ExtraBold'
  else base = 'Black'
  return italic ? `${base} Italic` : base
}

// ── SYNC_FRAME: The main sync command from robo-architect ──

async function handleSyncFrame(msg: {
  figmaNodeId?: string
  frameName: string
  textUpdates?: Array<{ nodeId: string; text: string }>
  sceneGraph?: any
}) {
  const { figmaNodeId, frameName, textUpdates } = msg
  let targetFrame: FrameNode | null = null

  // 1. Try to find existing frame by ID
  if (figmaNodeId) {
    const node = figma.getNodeById(figmaNodeId)
    if (node && (node.type === 'FRAME' || node.type === 'COMPONENT')) {
      targetFrame = node as FrameNode
    }
  }

  // 2. Try to find by name across all pages
  if (!targetFrame && frameName) {
    for (const page of figma.root.children) {
      for (const child of page.children) {
        if (child.name === frameName && (child.type === 'FRAME' || child.type === 'COMPONENT')) {
          targetFrame = child as FrameNode
          break
        }
      }
      if (targetFrame) break
    }
  }

  // 3. Frame not found → create in "RoboArchitect Sync" page
  let isNewFrame = false
  if (!targetFrame) {
    const syncPageName = 'RoboArchitect Sync'
    let syncPage = figma.root.children.find(function(p) { return p.name === syncPageName }) as PageNode | undefined

    if (!syncPage) {
      syncPage = figma.createPage()
      syncPage.name = syncPageName
    }

    figma.currentPage = syncPage

    // Count existing frames for positioning
    const existingCount = syncPage.children.length

    targetFrame = figma.createFrame()
    targetFrame.name = frameName || 'Synced Wireframe'
    targetFrame.resize(375, 812)
    targetFrame.x = existingCount * 420
    targetFrame.y = 0
    targetFrame.fills = [{ type: 'SOLID', color: { r: 1, g: 1, b: 1 }, opacity: 1 }]
    isNewFrame = true

    figma.ui.postMessage({
      type: 'SYNC_CREATED',
      message: `새 프레임 생성: "${targetFrame.name}" (${syncPage.name}) — ID: ${targetFrame.id}`,
      nodeId: targetFrame.id,
      pageId: syncPage.id,
      frameName: targetFrame.name,
      isNew: true,
    })
  }

  // 4. Build frame content from sceneGraph components or update text
  let updated = 0
  let failed = 0
  const errors: string[] = []

  // Load Inter font once (for text nodes)
  let fontLoaded = false
  async function ensureFont() {
    if (fontLoaded) return
    await figma.loadFontAsync({ family: "Inter", style: "Regular" })
    await figma.loadFontAsync({ family: "Inter", style: "Bold" }).catch(function() {})
    fontLoaded = true
  }

  // If sceneGraph with component info is provided, build from components
  const sceneNodes = msg.sceneGraph && msg.sceneGraph.nodes
  if (isNewFrame && sceneNodes) {
    // Build frame from SceneGraph — find components by name and create instances
    const built = await buildFrameFromSceneGraph(targetFrame, sceneNodes, msg.sceneGraph.rootId)
    updated = built.created
    failed = built.failed
    errors.push.apply(errors, built.errors)
  } else if (textUpdates && textUpdates.length > 0) {
    // Text-only updates for existing frames
    for (const tu of textUpdates) {
      try {
        let textNode = figma.getNodeById(tu.nodeId)
        if (!textNode) textNode = findTextNodeByName(targetFrame, tu.nodeId)
        if (!textNode && (tu as any).name) textNode = findTextNodeByName(targetFrame, (tu as any).name)

        if (textNode && textNode.type === 'TEXT') {
          const tn = textNode as TextNode
          // Try loading the original font; if unavailable, switch to Inter
          try {
            await Promise.all(
              tn.getRangeAllFontNames(0, tn.characters.length).map(figma.loadFontAsync)
            )
          } catch (_fontErr) {
            // Font not available — replace with Inter so we can edit
            await ensureFont()
            tn.fontName = { family: "Inter", style: "Regular" }
          }
          tn.characters = tu.text
          updated++
        } else if (tu.text) {
          await ensureFont()
          const newText = figma.createText()
          newText.fontName = { family: "Inter", style: "Regular" }
          newText.characters = tu.text
          newText.fontSize = (tu as any).fontSize || 14
          if ((tu as any).name) newText.name = (tu as any).name
          newText.x = 20
          newText.y = 20 + updated * 30
          newText.textAutoResize = "WIDTH_AND_HEIGHT"
          targetFrame.appendChild(newText)
          updated++
        } else {
          failed++
          errors.push('"' + tu.nodeId + '" not found')
        }
      } catch (e: any) {
        failed++
        errors.push('"' + tu.nodeId + '": ' + ((e && e.message) || e))
      }
    }
  }

  // 5. Zoom to the frame
  figma.viewport.scrollAndZoomIntoView([targetFrame])

  // 6. Report result (includes frameId for backend to save)
  figma.ui.postMessage({
    type: 'SYNC_RESULT',
    success: failed === 0 || updated > 0,
    frameId: targetFrame.id,
    frameName: targetFrame.name,
    isNewFrame: isNewFrame,
    updated,
    failed,
    total: (textUpdates && textUpdates.length) || 0,
    errors: errors.slice(0, 10),
    message: isNewFrame
      ? `새 프레임 생성 + ${updated}개 업데이트 (ID: ${targetFrame.id})`
      : failed === 0
        ? `${updated}개 노드 업데이트 완료`
        : `${updated}개 성공, ${failed}개 실패`,
  })
}

/**
 * Find any text node on a given page, replace its text.
 * msg: { pageName?: string, searchText?: string, replaceText: string }
 */
async function handleFindAndReplaceText(msg: any) {
  const { pageName, searchText, replaceText } = msg
  let targetPage: PageNode | null = null

  // Find the page by name (try exact, then substring, then index)
  if (pageName) {
    // Exact match
    targetPage = figma.root.children.find(p => p.name === pageName) as PageNode || null
    // Substring match
    if (!targetPage) {
      targetPage = figma.root.children.find(p => p.name.toLowerCase().includes(pageName.toLowerCase())) as PageNode || null
    }
    // Try as page index (e.g. "3" → third page)
    if (!targetPage) {
      const idx = parseInt(pageName) - 1
      if (idx >= 0 && idx < figma.root.children.length) {
        targetPage = figma.root.children[idx] as PageNode
      }
    }
  }
  if (!targetPage) {
    targetPage = figma.currentPage
  }

  // Switch to the target page so we can access its nodes
  figma.currentPage = targetPage

  // Find text nodes
  const textNodes: TextNode[] = []
  function collectText(node: BaseNode) {
    if (node.type === 'TEXT') textNodes.push(node as TextNode)
    if ('children' in node) {
      for (const child of (node as ChildrenMixin).children) collectText(child)
    }
  }
  for (const child of targetPage.children) collectText(child)

  let updated = 0
  const errors: string[] = []

  for (const tn of textNodes) {
    // If searchText specified, only match nodes containing it
    if (searchText && !tn.characters.includes(searchText)) continue

    try {
      await Promise.all(
        tn.getRangeAllFontNames(0, tn.characters.length).map(figma.loadFontAsync)
      )
      const oldText = tn.characters
      tn.characters = searchText
        ? tn.characters.replace(searchText, replaceText)
        : replaceText
      updated++
      // Only update first match if no searchText filter
      if (!searchText) break
    } catch (e: any) {
      errors.push(tn.id + ': ' + ((e && e.message) || String(e)))
    }
  }

  figma.ui.postMessage({
    type: 'SYNC_RESULT',
    success: updated > 0,
    updated,
    failed: errors.length,
    total: searchText ? textNodes.filter(t => t.characters.includes(searchText || '')).length : textNodes.length,
    errors,
    message: updated > 0
      ? `${updated}개 텍스트 변경 완료 (${targetPage.name})`
      : `텍스트를 찾을 수 없습니다 (${targetPage.name}, ${textNodes.length} text nodes)`
  })
}

/**
 * Build a frame's content from SceneGraph data using existing Figma components.
 * Finds COMPONENT nodes in the file by name and creates instances.
 */
async function buildFrameFromSceneGraph(
  frame: FrameNode,
  nodes: Record<string, any>,
  rootId: string
): Promise<{ created: number; failed: number; errors: string[] }> {
  let created = 0
  let failed = 0
  const errors: string[] = []

  // Set frame to auto-layout vertical
  frame.layoutMode = 'VERTICAL'
  frame.primaryAxisSizingMode = 'AUTO'
  frame.counterAxisSizingMode = 'FIXED'
  frame.itemSpacing = 0
  frame.paddingTop = 0
  frame.paddingBottom = 0
  frame.paddingLeft = 0
  frame.paddingRight = 0

  // Build component cache: name → ComponentNode (search all pages)
  const componentCache = new Map<string, ComponentNode>()
  for (const page of figma.root.children) {
    function collectComponents(node: BaseNode) {
      if (node.type === 'COMPONENT') {
        componentCache.set(node.name.toLowerCase(), node as ComponentNode)
      }
      if ('children' in node) {
        for (const child of (node as ChildrenMixin).children) {
          collectComponents(child)
        }
      }
    }
    collectComponents(page)
  }

  // Find the wireframe frame node in the SceneGraph
  // Walk: rootId → page → frame → children (instances)
  let wireframeNodeId: string | null = null
  const rootNode = nodes[rootId]
  if (rootNode) {
    // root → page (CANVAS) → frame (FRAME)
    for (const pageId of rootNode.childIds || []) {
      const page = nodes[pageId]
      if (!page) continue
      for (const frameId of page.childIds || []) {
        const f = nodes[frameId]
        if (f && f.type === 'FRAME') {
          wireframeNodeId = frameId
          break
        }
      }
      if (wireframeNodeId) break
    }
  }

  if (!wireframeNodeId) {
    // Fallback: find any FRAME in the nodes
    for (const [nid, n] of Object.entries(nodes)) {
      if (n.type === 'FRAME' && nid !== rootId && n.childIds && n.childIds.length > 0) {
        wireframeNodeId = nid
        break
      }
    }
  }

  if (!wireframeNodeId) {
    errors.push('No wireframe frame found in sceneGraph')
    return { created, failed: 1, errors }
  }

  const wireframeNode = nodes[wireframeNodeId]

  // Process each child of the wireframe frame
  for (const childId of wireframeNode.childIds || []) {
    const child = nodes[childId]
    if (!child) continue

    // For INSTANCE nodes, find the component by name and create instance
    if (child.type === 'INSTANCE' && child.name) {
      const compName = child.name.toLowerCase()
      const component = componentCache.get(compName)

      if (component) {
        try {
          const instance = component.createInstance()
          frame.appendChild(instance)

          // Apply text overrides from SceneGraph children
          await applyTextOverridesFromSceneGraph(instance, childId, nodes)
          created++
        } catch (e: any) {
          failed++
          errors.push('Instance "' + child.name + '": ' + ((e && e.message) || e))
        }
      } else {
        // Component not found — try partial name match
        let matched: ComponentNode | null = null
        for (const [cname, cnode] of componentCache) {
          if (cname.includes(compName) || compName.includes(cname)) {
            matched = cnode
            break
          }
        }
        if (matched) {
          try {
            const instance = matched.createInstance()
            frame.appendChild(instance)
            await applyTextOverridesFromSceneGraph(instance, childId, nodes)
            created++
          } catch (e: any) {
            failed++
            errors.push('Instance "' + child.name + '": ' + ((e && e.message) || e))
          }
        } else {
          failed++
          errors.push('Component "' + child.name + '" not found')
        }
      }
    } else if (child.type === 'FRAME') {
      // Non-instance frame — create a plain frame
      const newFrame = figma.createFrame()
      newFrame.name = child.name || 'Frame'
      newFrame.resize(child.width || 375, child.height || 100)
      frame.appendChild(newFrame)
      created++
    }
  }

  return { created, failed, errors }
}

/**
 * Apply text overrides: walk SceneGraph children to find TEXT nodes,
 * then find matching text nodes in the Figma instance by name and update.
 */
async function applyTextOverridesFromSceneGraph(
  instance: InstanceNode,
  sceneNodeId: string,
  nodes: Record<string, any>
): Promise<void> {
  // Collect all TEXT nodes from the SceneGraph subtree
  const textNodes: Array<{ name: string; text: string }> = []
  function collectTexts(nodeId: string) {
    const n = nodes[nodeId]
    if (!n) return
    if (n.type === 'TEXT' && n.text) {
      textNodes.push({ name: n.name || '', text: n.text })
    }
    for (const cid of n.childIds || []) {
      collectTexts(cid)
    }
  }
  collectTexts(sceneNodeId)

  if (textNodes.length === 0) return

  // Find and update matching text nodes in the Figma instance
  const figmaTexts: TextNode[] = []
  function collectFigmaTexts(node: BaseNode) {
    if (node.type === 'TEXT') figmaTexts.push(node as TextNode)
    if ('children' in node) {
      for (const child of (node as ChildrenMixin).children) {
        collectFigmaTexts(child)
      }
    }
  }
  collectFigmaTexts(instance)

  for (const st of textNodes) {
    // Match by name first
    let target = figmaTexts.find(function(ft) { return ft.name === st.name })
    // Fallback: match by current text content
    if (!target) {
      target = figmaTexts.find(function(ft) { return ft.characters === st.text })
    }
    if (target) {
      try {
        await Promise.all(
          target.getRangeAllFontNames(0, target.characters.length).map(figma.loadFontAsync)
        )
      } catch (_fontErr) {
        // Font not available — switch to Inter
        await figma.loadFontAsync({ family: "Inter", style: "Regular" })
        target.fontName = { family: "Inter", style: "Regular" }
      }
      try {
        target.characters = st.text
      } catch (_e) {}
    }
  }
}

/**
 * EXPORT_FRAME: Read a Figma frame's full node tree and send it back
 * to robo-architect via ui.html → backend. No Figma API token needed.
 */
function handleExportFrame(msg: any) {
  const { figmaNodeId, frameName, uiNodeId } = msg
  let targetFrame: SceneNode | null = null

  // Find by ID
  if (figmaNodeId) {
    const node = figma.getNodeById(figmaNodeId)
    if (node && (node.type === 'FRAME' || node.type === 'COMPONENT' || node.type === 'INSTANCE')) {
      targetFrame = node as SceneNode
    }
  }

  // Find by name
  if (!targetFrame && frameName) {
    for (const page of figma.root.children) {
      for (const child of page.children) {
        if (child.name === frameName && (child.type === 'FRAME' || child.type === 'COMPONENT')) {
          targetFrame = child as SceneNode
          break
        }
      }
      if (targetFrame) break
    }
  }

  if (!targetFrame) {
    figma.ui.postMessage({
      type: 'EXPORT_RESULT',
      success: false,
      error: 'Frame "' + (frameName || figmaNodeId) + '" not found',
      uiNodeId: uiNodeId,
    })
    return
  }

  // Serialize the frame tree
  const frameData = serializeNode(targetFrame)

  figma.ui.postMessage({
    type: 'EXPORT_RESULT',
    success: true,
    frameId: targetFrame.id,
    frameName: targetFrame.name,
    frameData: frameData,
    uiNodeId: uiNodeId,
  })
}

// Delegate to the richer serializeFigmaNode (declared earlier in the file)
// so the legacy EXPORT_FRAME path captures the same fields as the new
// EXPORT_FRAME_BY_ID path: x/y/fills/strokes/layoutMode/padding/fontName,
// not just id+type+name+width+height. Without this, Figma→RA pulls strip
// every visual property and the round-tripped frame renders blank in
// open-pencil's FrameEditor.
function serializeNode(node: SceneNode): any {
  return serializeFigmaNode(node as any)
}

function findTextNodeByName(parent: BaseNode, name: string): BaseNode | null {
  if (!('children' in parent)) return null
  for (const child of (parent as ChildrenMixin).children) {
    if (child.type === 'TEXT' && child.name === name) return child
    if ('children' in child) {
      const found = findTextNodeByName(child, name)
      if (found) return found
    }
  }
  return null
}

// ── Node update handlers ──

async function handleNodeUpdates(
  updates: Array<{ nodeId: string; props: Record<string, unknown> }>
) {
  let updated = 0
  let failed = 0

  for (const update of updates) {
    const node = figma.getNodeById(update.nodeId)
    if (!node) { failed++; continue }
    try {
      applyProps(node as SceneNode, update.props)
      updated++
    } catch (e) {
      failed++
    }
  }

  figma.ui.postMessage({ type: 'UPDATE_RESULT', updated, failed, total: updates.length })
}

async function handleTextUpdate(nodeId: string, text: string) {
  const node = figma.getNodeById(nodeId)
  if (!node || node.type !== 'TEXT') {
    figma.ui.postMessage({ type: 'ERROR', message: `Text node ${nodeId} not found` })
    return
  }
  const textNode = node as TextNode
  try {
    await Promise.all(
      textNode.getRangeAllFontNames(0, textNode.characters.length).map(figma.loadFontAsync)
    )
  } catch (_fontErr) {
    await figma.loadFontAsync({ family: "Inter", style: "Regular" })
    textNode.fontName = { family: "Inter", style: "Regular" }
  }
  textNode.characters = text
  figma.ui.postMessage({ type: 'UPDATE_RESULT', updated: 1, failed: 0, total: 1 })
}

function applyProps(node: SceneNode, props: Record<string, unknown>) {
  for (const [key, value] of Object.entries(props)) {
    if (key === 'fills' && 'fills' in node) (node as GeometryMixin).fills = value as Paint[]
    else if (key === 'strokes' && 'strokes' in node) (node as GeometryMixin).strokes = value as Paint[]
    else if (key === 'x' && 'x' in node) node.x = value as number
    else if (key === 'y' && 'y' in node) node.y = value as number
    else if (key === 'width' && 'resize' in node) (node as FrameNode).resize(value as number, node.height)
    else if (key === 'height' && 'resize' in node) (node as FrameNode).resize(node.width, value as number)
    else if (key === 'name') node.name = value as string
    else if (key === 'visible') node.visible = value as boolean
    else if (key === 'opacity' && 'opacity' in node) (node as BlendMixin).opacity = value as number
    else if (key === 'cornerRadius' && 'cornerRadius' in node) (node as CornerMixin).cornerRadius = value as number
  }
}

// ── Utilities ──

function sendSelection() {
  figma.ui.postMessage({
    type: 'SELECTION',
    nodes: figma.currentPage.selection.map(n => ({
      id: n.id, name: n.name, type: n.type,
      width: 'width' in n ? n.width : 0,
      height: 'height' in n ? n.height : 0,
    }))
  })
}

function listAllFrames() {
  const frames: any[] = []
  for (const page of figma.root.children) {
    for (const child of page.children) {
      if (child.type === 'FRAME' || child.type === 'COMPONENT' || child.type === 'COMPONENT_SET') {
        frames.push({
          id: child.id, name: child.name,
          width: child.width, height: child.height,
          pageId: page.id, pageName: page.name,
        })
      }
    }
  }
  figma.ui.postMessage({ type: 'FRAMES_LIST', frames })
}

figma.on('selectionchange', () => sendSelection())

// ── Watch for document changes and auto-export modified frames ──
let changeTimer: number | null = null
const CHANGE_DEBOUNCE_MS = 3000

// DISABLED (#10): auto-exporting on every documentchange creates a destructive
// feedback loop. RA's "Save & Sync" edits the Figma frame → documentchange fires
// → AUTO_EXPORT → POST /export-result re-imports a lossy, component-extracted
// version (plain TEXT dropped) → clobbers the rich sceneGraph RA just saved, so
// the UI shows empty after reload. Per the architecture decision (#7), Figma→RA
// must go through the explicit "가져오기"(pull) button, never an auto-sync. Flip
// to true only if echo-suppression + non-lossy export is implemented first.
const AUTO_EXPORT_TO_RA = false

figma.on('documentchange', (event) => {
  if (!AUTO_EXPORT_TO_RA) return
  // Collect unique frame IDs that were modified
  const modifiedFrameIds = new Set<string>()
  for (const change of event.documentChanges) {
    if (change.type === 'PROPERTY_CHANGE' || change.type === 'STYLE_CREATE' || change.type === 'STYLE_DELETE') {
      // Walk up to find the top-level frame
      let node: BaseNode | null = 'node' in change ? (change as any).node : null
      if (!node && 'id' in change) {
        node = figma.getNodeById((change as any).id)
      }
      while (node && node.parent && node.parent.type !== 'PAGE') {
        node = node.parent
      }
      if (node && (node.type === 'FRAME' || node.type === 'COMPONENT')) {
        modifiedFrameIds.add(node.id)
      }
    }
  }

  if (modifiedFrameIds.size === 0) return

  // Debounce: wait for changes to settle
  if (changeTimer) clearTimeout(changeTimer)
  changeTimer = setTimeout(() => {
    changeTimer = null
    for (const frameId of modifiedFrameIds) {
      const node = figma.getNodeById(frameId)
      if (node && (node.type === 'FRAME' || node.type === 'COMPONENT')) {
        const data = serializeNode(node as SceneNode)
        figma.ui.postMessage({
          type: 'AUTO_EXPORT',
          frameId: node.id,
          frameName: node.name,
          frameData: data,
        })
      }
    }
  }, CHANGE_DEBOUNCE_MS) as unknown as number
})

// ── Component scan (replaces the legacy REST `/v1/files/{key}` walk) ──
//
// Walks every COMPONENT / COMPONENT_SET in the document, exports each as a
// PNG, and ships them to the UI iframe which POSTs to
// `/api/figma-binding/components/scan`. Replaces the REST-API-token path —
// the plugin's mere presence inside Figma proves the user can read these
// nodes, so no `X-Figma-Token` is needed.
async function handleScanComponents(): Promise<void> {
  let nodes: SceneNode[]
  try {
    nodes = figma.root.findAll(
      (n: SceneNode) => n.type === 'COMPONENT' || n.type === 'COMPONENT_SET'
    )
  } catch (e: any) {
    figma.ui.postMessage({
      type: 'SCAN_COMPONENTS_RESULT',
      ok: false,
      error: `Document walk failed: ${(e && e.message) || String(e)}`,
    })
    return
  }

  figma.ui.postMessage({ type: 'SCAN_COMPONENTS_PROGRESS', total: nodes.length, exported: 0 })

  const components: any[] = []
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i] as any
    try {
      const bytes: Uint8Array = await n.exportAsync({ format: 'PNG' })
      components.push({
        figmaNodeId: n.id,
        name: n.name || n.id,
        pageName: pageNameOf(n),
        widthPx: Math.round(n.width || 0),
        heightPx: Math.round(n.height || 0),
        pngBase64: bytesToBase64(bytes),
      })
    } catch (e: any) {
      // Non-fatal — surface so the operator notices misconfigured nodes.
      figma.ui.postMessage({
        type: 'SCAN_COMPONENTS_SKIP',
        nodeId: n.id,
        name: n.name,
        reason: (e && e.message) || String(e),
      })
    }
    figma.ui.postMessage({
      type: 'SCAN_COMPONENTS_PROGRESS',
      total: nodes.length,
      exported: components.length,
      lastName: n.name,
    })
  }

  figma.ui.postMessage({
    type: 'SCAN_COMPONENTS_RESULT',
    ok: true,
    components,
  })
}

function pageNameOf(node: any): string {
  let cur: any = node
  while (cur && cur.type !== 'PAGE') cur = cur.parent
  return cur ? cur.name : ''
}

// Uint8Array → base64. Use figma.base64Encode where available (newer
// plugin API, single call); otherwise chunked String.fromCharCode + btoa
// to avoid stack overflow on multi-MB PNGs.
function bytesToBase64(bytes: Uint8Array): string {
  const f: any = figma as any
  if (typeof f.base64Encode === 'function') return f.base64Encode(bytes)
  const CHUNK = 0x8000
  let bin = ''
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, Array.from(bytes.subarray(i, i + CHUNK)))
  }
  return btoa(bin)
}

figma.ui.postMessage({
  type: 'PLUGIN_READY',
  fileKey: figma.fileKey,
  // figma.root.name is the file name — the UI uses it for the binding
  // payload so the architect modal can show "Connected to <fileName>".
  fileName: (figma.root && figma.root.name) || '',
})
