/**
 * RoboArchitect Sync — Figma Plugin (sandbox code)
 */

figma.showUI(__html__, { width: 320, height: 400, themeColors: true })

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
    }
  } catch (e: any) {
    figma.ui.postMessage({ type: 'ERROR', message: (e && e.message) || String(e) })
  }
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

function serializeNode(node: SceneNode): any {
  const result: any = {
    id: node.id,
    type: node.type,
    name: node.name,
    visible: node.visible,
    width: 'width' in node ? node.width : 0,
    height: 'height' in node ? node.height : 0,
  }

  // Text content
  if (node.type === 'TEXT') {
    result.characters = (node as TextNode).characters
    result.fontSize = (node as TextNode).fontSize
  }

  // Children
  if ('children' in node) {
    result.children = (node as ChildrenMixin).children.map(function(child) {
      return serializeNode(child as SceneNode)
    })
  }

  return result
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

figma.on('documentchange', (event) => {
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

figma.ui.postMessage({ type: 'PLUGIN_READY', fileKey: figma.fileKey })
