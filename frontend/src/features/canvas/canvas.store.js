import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { MarkerType } from '@vue-flow/core'

export const useCanvasStore = defineStore('canvas', () => {
  // Nodes on the canvas
  const nodes = ref([])
  const edges = ref([])
  
  // Design level mode: show/hide detailed fields in nodes
  // ALWAYS default to true (show fields) - completely ignore localStorage
  // Force reset localStorage to 'true' to ensure fields are always shown by default
  const showDesignLevel = ref(true)
  
  // Force reset localStorage to ensure default is always true
  try {
    localStorage.setItem('canvas_show_design_level', 'true')
  } catch (e) {
    // Ignore localStorage errors
  }
  
  // Toggle design level and save to localStorage
  function toggleDesignLevel() {
    const newValue = !showDesignLevel.value
    showDesignLevel.value = newValue
    try {
      localStorage.setItem('canvas_show_design_level', String(newValue))
    } catch (e) {
      console.warn('Failed to save showDesignLevel to localStorage:', e)
    }
  }
  
  // Force set design level (for initialization)
  function setShowDesignLevel(value) {
    showDesignLevel.value = Boolean(value)
    try {
      localStorage.setItem('canvas_show_design_level', String(showDesignLevel.value))
    } catch (e) {
      console.warn('Failed to save showDesignLevel to localStorage:', e)
    }
  }
  
  // Right panel mode: 'none' | 'chat' | 'inspector'
  const rightPanelMode = ref('chat')
  
  // Close right panel (Model Modifier / Inspector)
  function closeRightPanel() {
    rightPanelMode.value = 'none'
  }
  
  // Set right panel mode
  function setRightPanelMode(mode) {
    rightPanelMode.value = mode
  }
  
  // Toggle chat panel
  function toggleChatPanel() {
    rightPanelMode.value = rightPanelMode.value === 'chat' ? 'none' : 'chat'
  }
  
  // Toggle inspector panel
  function toggleInspectorPanel() {
    rightPanelMode.value = rightPanelMode.value === 'inspector' ? 'none' : 'inspector'
  }

  // Selected nodes (for chat-based modification)
  const selectedNodeIds = ref(new Set())
  
  // Track BC containers and their children
  const bcContainers = ref({}) // { bcId: { nodeIds: [], bounds: {} } }
  
  // Track collapsed BCs
  const collapsedBCs = ref(new Set())
  
  // Node type configurations
  const nodeTypeConfig = {
    Command: { 
      color: '#5c7cfa', 
      width: 140,
      height: 80
    },
    Event: { 
      color: '#fd7e14', 
      width: 140,
      height: 70
    },
    Policy: { 
      color: '#fcc419', 
      width: 130,
      height: 60
    },
    Aggregate: { 
      color: '#b197fc', 
      width: 160,
      height: 80
    },
    ReadModel: {
      color: '#40c057',
      width: 170,
      height: 110
    },
    UI: {
      color: '#ffffff',
      width: 130,
      height: 110
    },
    BoundedContext: { 
      color: '#373a40', 
      width: 400,
      height: 300
    }
  }

  // Property rendering (Option C): node height expands with field count.
  // Actual measurements from CSS:
  // - es-node__props margin-top: 10px
  // - es-node__props padding: 6px (top/bottom = 12px total)
  // - es-node__prop padding: 3px 4px (top/bottom = 6px total per row)
  // - es-node__prop line-height: ~16px
  // Total per row: ~22px (6px padding + 16px content)
  const PROP_ROW_HEIGHT = 22  // Increased from 16 to match actual CSS
  const PROP_SECTION_MARGIN_TOP = 10  // es-node__props margin-top
  const PROP_SECTION_PADDING = 12  // es-node__props padding top + bottom (6px * 2)

  function getPropertiesCount(data) {
    const props = data?.properties
    const enums = data?.enumerations
    const vos = data?.valueObjects
    const propsCount = Array.isArray(props) ? props.length : 0
    const enumsCount = Array.isArray(enums) ? enums.length : 0
    const vosCount = Array.isArray(vos) ? vos.length : 0
    return propsCount + enumsCount + vosCount
  }

  function computeDynamicHeight(nodeType, data) {
    const base = nodeTypeConfig?.[nodeType]?.height || 80
    const count = getPropertiesCount(data)
    if (!count) return base
    // Calculate: base + margin-top + padding + (rows * row-height)
    return base + PROP_SECTION_MARGIN_TOP + PROP_SECTION_PADDING + (count * PROP_ROW_HEIGHT)
  }

  function getNodeHeight(node) {
    if (!node) return 80
    if (node.type === 'boundedcontext') {
      return parseInt(node.style?.height || '300')
    }
    const t = node.data?.type
    const h = Number(node.data?.dynamicHeight)
    if (Number.isFinite(h) && h > 0) return h
    return computeDynamicHeight(t, node.data)
  }

  function sortProperties(props) {
    const list = Array.isArray(props) ? [...props] : []
    list.sort((a, b) => {
      const aKey = Number(!!a?.isKey)
      const bKey = Number(!!b?.isKey)
      if (aKey !== bKey) return bKey - aKey

      const aFk = Number(!!a?.isForeignKey)
      const bFk = Number(!!b?.isForeignKey)
      if (aFk !== bFk) return bFk - aFk

      const an = String(a?.name || '')
      const bn = String(b?.name || '')
      return an.localeCompare(bn)
    })
    return list
  }

  function updateEmbeddedProperties(parentId, updater) {
    if (!parentId || !isOnCanvas(parentId)) return
    const idx = nodes.value.findIndex(n => n.id === parentId)
    if (idx === -1) return

    const existing = nodes.value[idx]
    const existingProps = Array.isArray(existing.data?.properties) ? [...existing.data.properties] : []
    const nextProps = sortProperties(updater(existingProps))

    const nextData = {
      ...existing.data,
      properties: nextProps
    }
    nextData.dynamicHeight = computeDynamicHeight(existing.data?.type, nextData)

    nodes.value[idx] = { ...existing, data: nextData }
    nodes.value = [...nodes.value]

    if (existing.parentNode) updateBCSize(existing.parentNode, true)
  }
  
  // Get all node IDs currently on canvas
  const nodeIds = computed(() => nodes.value.map(n => n.id))

  // Selected nodes list (derived)
  const selectedNodes = computed(() => nodes.value.filter(n => selectedNodeIds.value.has(n.id)))

  // Selection helpers
  function isSelected(nodeId) {
    return selectedNodeIds.value.has(nodeId)
  }

  function toggleNodeSelection(nodeId) {
    if (selectedNodeIds.value.has(nodeId)) {
      selectedNodeIds.value.delete(nodeId)
    } else {
      selectedNodeIds.value.add(nodeId)
    }
    selectedNodeIds.value = new Set(selectedNodeIds.value)
  }

  function selectNode(nodeId) {
    selectedNodeIds.value = new Set([nodeId])
  }

  function addToSelection(nodeId) {
    selectedNodeIds.value.add(nodeId)
    selectedNodeIds.value = new Set(selectedNodeIds.value)
  }

  function removeFromSelection(nodeId) {
    selectedNodeIds.value.delete(nodeId)
    selectedNodeIds.value = new Set(selectedNodeIds.value)
  }

  function clearSelection() {
    selectedNodeIds.value = new Set()
  }

  function selectNodes(nodeIdArray) {
    selectedNodeIds.value = new Set(nodeIdArray || [])
  }
  
  // Check if a node is on canvas
  function isOnCanvas(nodeId) {
    return nodeIds.value.includes(nodeId)
  }
  
  // Get or create BC container for a given BC ID
  function getOrCreateBCContainer(bcId, bcName, bcDescription) {
    // Check if BC container already exists
    let bcNode = nodes.value.find(n => n.id === bcId && n.type === 'boundedcontext')
    
    if (!bcNode) {
      // Create new BC container
      const existingBCs = nodes.value.filter(n => n.type === 'boundedcontext')
      const offsetX = existingBCs.length * 600
      
      bcNode = {
        id: bcId,
        type: 'boundedcontext',
        position: { x: 50 + offsetX, y: 50 },
        data: {
          id: bcId,
          name: bcName || bcId,
          description: bcDescription,
          type: 'BoundedContext',
          label: bcName
        },
        style: {
          width: '550px',
          height: '350px'
        },
        // Make it a group node
        className: 'bc-group-node'
      }
      
      nodes.value.push(bcNode)
      bcContainers.value[bcId] = { nodeIds: [], bounds: {} }
    } else {
      // BC already exists - try to sync position from Vue Flow DOM
      // This ensures we use the actual rendered position, not stale data
      try {
        const nodeEl = document.querySelector(`[data-id="${bcId}"]`)
        if (nodeEl) {
          const transform = nodeEl.style.transform
          if (transform) {
            // Extract x, y from transform: translate(xpx, ypx)
            const match = transform.match(/translate\(([^,]+)px,\s*([^)]+)px\)/)
            if (match) {
              const x = parseFloat(match[1])
              const y = parseFloat(match[2])
              if (!isNaN(x) && !isNaN(y)) {
                bcNode.position = { x, y }
                console.log(`[getOrCreateBCContainer] Synced BC position from DOM: ${bcId} -> (${x}, ${y})`)
              }
            }
          }
        }
      } catch (e) {
        // Ignore DOM access errors - use existing position
      }
    }
    
    return bcNode
  }
  
  // Calculate position within BC container
  function calculatePositionInBC(bcId, nodeType, existingChildCount) {
    const bcNode = nodes.value.find(n => n.id === bcId)
    if (!bcNode) return { x: 100, y: 100 }
    
    // Consistent padding values (matching updateBCSize)
    const headerHeight = 50
    const topPadding = 30
    const leftPadding = 40
    const gapX = 5  // Tight spacing between stickers
    const nodeWidth = nodeTypeConfig[nodeType]?.width || 140
    const nodeHeight = nodeTypeConfig[nodeType]?.height || 80
    const baseY = headerHeight + topPadding  // Starting Y position for all stickers
    
    // Sticker widths for tight layout
    const commandWidth = nodeTypeConfig.Command?.width || 140
    const aggregateWidth = nodeTypeConfig.Aggregate?.width || 160
    
    // Calculate X positions: stickers almost adjacent
    const commandX = leftPadding
    const aggregateX = commandX + commandWidth + gapX
    const eventX = aggregateX + aggregateWidth + gapX
    
    // Layout: External Event → Policy → Command → Aggregate → Event
    // Policy is placed LEFT of Command (triggered by external domain events, invokes internal command)
    const policyWidth = nodeTypeConfig.Policy?.width || 130
    const policyX = commandX - policyWidth - gapX  // Policy left of Command
    
    const typeOffsets = {
      Command: { x: commandX, baseY: baseY },
      Aggregate: { x: aggregateX, baseY: baseY },
      Event: { x: eventX, baseY: baseY },
      Policy: { x: policyX, baseY: baseY },  // Policy left of Command (same row)
      // Place ReadModel roughly below the main flow
      ReadModel: { x: aggregateX, baseY: baseY + 100 },
      // UI stickers default to left side (more accurate placement happens in addNodesWithLayout)
      UI: { x: leftPadding, baseY: baseY }
    }
    
    const offset = typeOffsets[nodeType] || { x: leftPadding, baseY: baseY }
    
    // Stack below the last node of the same type (dynamic height-aware)
    const sameType = nodes.value.filter(n =>
      n.parentNode === bcId &&
      n.data?.type === nodeType
    )

    if (!sameType.length) {
      return { x: offset.x, y: offset.baseY }
    }

    const maxBottom = Math.max(...sameType.map(n => n.position.y + getNodeHeight(n)))
    return { x: offset.x, y: maxBottom + 5 }
  }
  
  // Update BC container size based on children
  // If shiftIfNeeded is true, shifts all children right when minX < padding
  function updateBCSize(bcId, shiftIfNeeded = false) {
    const bcNode = nodes.value.find(n => n.id === bcId)
    if (!bcNode) return
    
    const children = nodes.value.filter(n => n.parentNode === bcId)
    if (children.length === 0) {
      bcNode.style = { width: '550px', height: '350px' }
      return
    }
    
    // Generous padding values for clear visual separation from BC border
    const headerHeight = 50      // BC header height
    const topPadding = 30        // Padding below header
    const bottomPadding = 50     // Bottom margin from BC border
    const leftPadding = 40       // Left margin from BC border  
    const rightPadding = 50      // Right margin from BC border
    
    // Calculate bounds of all children
    let minX = Infinity
    let minY = Infinity
    let maxX = 0
    let maxY = 0
    
    children.forEach(child => {
      const config = nodeTypeConfig[child.data?.type] || { width: 140, height: 80 }
      const left = child.position.x
      const top = child.position.y
      const right = child.position.x + config.width
      const bottom = child.position.y + getNodeHeight(child)
      
      minX = Math.min(minX, left)
      minY = Math.min(minY, top)
      maxX = Math.max(maxX, right)
      maxY = Math.max(maxY, bottom)
    })
    
    // If children extend past left boundary, shift all children right
    if (shiftIfNeeded && minX < leftPadding) {
      const shiftAmount = leftPadding - minX
      children.forEach(child => {
        child.position = {
          ...child.position,
          x: child.position.x + shiftAmount
        }
      })
      // Recalculate maxX after shift
      maxX += shiftAmount
      minX = leftPadding
    }
    
    // If children extend past top boundary (below header), shift all children down
    const minAllowedY = headerHeight + topPadding
    if (shiftIfNeeded && minY < minAllowedY) {
      const shiftAmount = minAllowedY - minY
      children.forEach(child => {
        child.position = {
          ...child.position,
          y: child.position.y + shiftAmount
        }
      })
      // Recalculate maxY after shift
      maxY += shiftAmount
      minY = minAllowedY
    }
    
    // Calculate new BC dimensions with generous margins
    const newWidth = Math.max(550, maxX + rightPadding)
    const newHeight = Math.max(350, maxY + bottomPadding)
    
    bcNode.style = {
      width: `${newWidth}px`,
      height: `${newHeight}px`
    }
  }
  
  // Add a node to canvas (within its BC container)
  function addNode(nodeData, bcId = null, bcName = null) {
    if (isOnCanvas(nodeData.id)) {
      console.log('Node already on canvas:', nodeData.id)
      return null
    }
    
    const nodeType = nodeData.type
    
    // If it's a BC, create container
    if (nodeType === 'BoundedContext') {
      return getOrCreateBCContainer(nodeData.id, nodeData.name, nodeData.description)
    }
    
    // For other nodes, they should be inside a BC
    let parentBcId = bcId
    
    // If no BC specified, try to find from node data
    if (!parentBcId && nodeData.bcId) {
      parentBcId = nodeData.bcId
    }
    
    // If we have a parent BC, ensure container exists
    if (parentBcId) {
      getOrCreateBCContainer(parentBcId, bcName)
    }
    
    // Calculate position
    const position = parentBcId 
      ? calculatePositionInBC(parentBcId, nodeType, 0)
      : { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 }
    
    const node = {
      id: nodeData.id,
      type: nodeType.toLowerCase(),
      position,
      data: {
        ...nodeData,
        label: nodeData.name,
        dynamicHeight: computeDynamicHeight(nodeType, nodeData)
      },
      ...(parentBcId && { parentNode: parentBcId, extent: 'parent' })
    }
    
    nodes.value.push(node)
    
    // Update BC size
    if (parentBcId) {
      updateBCSize(parentBcId)
    }
    
    return node
  }
  
  // Add multiple nodes with layout (from expand API)
  function addNodesWithLayout(nodeDataArray, relationships = [], bcContext = null) {
    const newNodes = []
    const bcMap = {} // Track which nodes belong to which BC
    
    // First pass: identify BCs and their children
    nodeDataArray.forEach(nodeData => {
      if (nodeData.type === 'BoundedContext') {
        bcMap[nodeData.id] = {
          bc: nodeData,
          children: []
        }
      }
    })
    
    // If we have BC context from the API, use it
    if (bcContext && bcContext.id) {
      if (!bcMap[bcContext.id]) {
        bcMap[bcContext.id] = {
          bc: {
            id: bcContext.id,
            name: bcContext.name,
            description: bcContext.description,
            type: 'BoundedContext'
          },
          children: []
        }
      }
    }
    
    // Second pass: assign children to BCs
    nodeDataArray.forEach(nodeData => {
      if (nodeData.type !== 'BoundedContext') {
        // Try to find parent BC from node data first
        let parentBcId = nodeData.bcId
        
        // If not in data, check bcContext
        if (!parentBcId && bcContext && bcContext.id) {
          parentBcId = bcContext.id
        }
        
        // If still not found, look for HAS_AGGREGATE / HAS_POLICY / HAS_READMODEL / HAS_UI relationship
        if (!parentBcId) {
          const parentRel = relationships.find(r => 
            r.target === nodeData.id && 
            (r.type === 'HAS_AGGREGATE' || r.type === 'HAS_POLICY' || r.type === 'HAS_READMODEL' || r.type === 'HAS_UI')
          )
          if (parentRel) {
            parentBcId = parentRel.source
          }
        }
        
        if (parentBcId && bcMap[parentBcId]) {
          bcMap[parentBcId].children.push(nodeData)
          nodeData.bcId = parentBcId
        } else if (parentBcId) {
          // BC not in map yet, create it
          bcMap[parentBcId] = {
            bc: { id: parentBcId, name: parentBcId, type: 'BoundedContext' },
            children: [nodeData]
          }
          nodeData.bcId = parentBcId
        } else {
          // No BC found, add to first available
          const firstBcId = Object.keys(bcMap)[0]
          if (firstBcId) {
            bcMap[firstBcId].children.push(nodeData)
            nodeData.bcId = firstBcId
          }
        }
      }
    })
    
    // If no BCs found but we have nodes, get BC info from API
    if (Object.keys(bcMap).length === 0 && nodeDataArray.length > 0) {
      // Group all nodes without explicit BC
      nodeDataArray.forEach(nodeData => {
        if (nodeData.type !== 'BoundedContext' && !isOnCanvas(nodeData.id)) {
          const node = {
            id: nodeData.id,
            type: nodeData.type.toLowerCase(),
            position: calculateStandalonePosition(nodeData.type, newNodes.length),
            data: {
              ...nodeData,
              label: nodeData.name,
              dynamicHeight: computeDynamicHeight(nodeData.type, nodeData)
            }
          }
          nodes.value.push(node)
          newNodes.push(node)
        }
      })
    } else {
      // Process each BC and its children
      let bcIndex = 0
      for (const [bcId, { bc, children }] of Object.entries(bcMap)) {
        // Create or get BC container
        const bcNode = getOrCreateBCContainer(bcId, bc?.name, bc?.description)
        if (!newNodes.find(n => n.id === bcId)) {
          newNodes.push(bcNode)
        }
        
        // Add children with proper layout
        // Layout: UI(맨 왼쪽) → Policy(왼쪽) → Command(왼쪽) → Aggregate(중앙) → Event(오른쪽) → ReadModel(아래)
        const typeGroups = {
          Aggregate: [],
          Command: [],
          Event: [],
          Policy: [],
          ReadModel: [],
          UI: []
        }
        
        children.forEach(child => {
          if (typeGroups[child.type]) {
            typeGroups[child.type].push(child)
          }
        })
        
        // Consistent padding values (matching updateBCSize and calculatePositionInBC)
        const headerHeight = 50
        const topPadding = 30
        const leftPadding = 40
        const nodeWidth = 140
        const nodeHeight = 90
        const gapX = 5   // Tight spacing between stickers (almost adjacent)
        const gapY = 5   // Tight spacing between stickers (almost adjacent)
        
        // Sticker widths for tight layout calculation
        const commandWidth = nodeTypeConfig.Command?.width || 140
        const aggregateWidth = nodeTypeConfig.Aggregate?.width || 160
        const eventWidth = nodeTypeConfig.Event?.width || 140
        const uiWidth_layout = nodeTypeConfig.UI?.width || 130
        const policyWidth = nodeTypeConfig.Policy?.width || 130
        const readModelWidth = nodeTypeConfig.ReadModel?.width || 170
        
        // Calculate positions: stickers almost adjacent (width + gapX)
        const commandX = leftPadding                                    // Command starts at left padding
        const aggregateX = commandX + commandWidth + gapX               // Aggregate right after Command
        const eventX = aggregateX + aggregateWidth + gapX               // Event right after Aggregate
        const policyX = commandX - policyWidth - gapX                   // Policy left of Command
        const readModelX = aggregateX                                   // ReadModel below Aggregate
        const uiX = commandX - uiWidth_layout - gapX                    // UI left of Command
        
        let currentY = headerHeight + topPadding
        
        // Find which command each policy invokes
        const policyCommandMap = {}
        typeGroups.Policy.forEach(pol => {
          if (pol.invokeCommandId) {
            policyCommandMap[pol.id] = pol.invokeCommandId
          }
        })
        
        // Build parent maps from relationships (preferred) and keep a fallback for missing fields
        const commandToAggregate = {}
        const eventToCommand = {}
        relationships.forEach(rel => {
          if (rel.type === 'HAS_COMMAND' && rel.source && rel.target) commandToAggregate[rel.target] = rel.source
          if (rel.type === 'EMITS' && rel.source && rel.target) eventToCommand[rel.target] = rel.source
        })

        // Fallback: derive Command.parentId from HAS_COMMAND if backend didn't include it
        typeGroups.Command.forEach(cmd => {
          if (!cmd.parentId && commandToAggregate[cmd.id]) {
            cmd.parentId = commandToAggregate[cmd.id] // Aggregate ID
          }
        })
        // Group Commands by their parent Aggregate
        const commandsByAggregate = {}
        typeGroups.Command.forEach(cmd => {
          const aggId = commandToAggregate[cmd.id] || cmd.parentId
          if (aggId) {
            if (!commandsByAggregate[aggId]) commandsByAggregate[aggId] = []
            commandsByAggregate[aggId].push(cmd)
          }
        })

        // Layout Commands (left column) - dynamic height-aware stacking
        const commandPositions = {}
        const aggregatePositions = {} // Track Y range for each aggregate (for Aggregate sizing)
        let yCursor = currentY
        let maxBottom = currentY

        typeGroups.Aggregate.forEach(agg => {
          const aggCommands = commandsByAggregate[agg.id] || []
          const startY = yCursor

          aggCommands.forEach(cmd => {
            if (!isOnCanvas(cmd.id)) {
              const h = computeDynamicHeight('Command', cmd)
              commandPositions[cmd.id] = { x: commandX, y: yCursor, height: h }
              const node = {
                id: cmd.id,
                type: 'command',
                position: { x: commandX, y: yCursor },
                data: { ...cmd, label: cmd.name, dynamicHeight: h },
                parentNode: bcId,
                extent: 'parent'
              }
              nodes.value.push(node)
              newNodes.push(node)
              maxBottom = Math.max(maxBottom, yCursor + h)
              yCursor += h + gapY
            }
          })

          if (aggCommands.length > 0) {
            const endY = yCursor - gapY
            aggregatePositions[agg.id] = { startY, endY, commandCount: aggCommands.length }
          }
        })

        // Also layout any orphan commands (no parent aggregate mapping)
        const orphanCommands = typeGroups.Command.filter(cmd => !(commandToAggregate[cmd.id] || cmd.parentId))
        orphanCommands.forEach(cmd => {
          if (!isOnCanvas(cmd.id)) {
            const h = computeDynamicHeight('Command', cmd)
            commandPositions[cmd.id] = { x: commandX, y: yCursor, height: h }
            const node = {
              id: cmd.id,
              type: 'command',
              position: { x: commandX, y: yCursor },
              data: { ...cmd, label: cmd.name, dynamicHeight: h },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, yCursor + h)
            yCursor += h + gapY
          }
        })
        
        // Layout Aggregates (center column) - height spans all its Commands (and grows with fields)
        typeGroups.Aggregate.forEach((agg, idx) => {
          if (!isOnCanvas(agg.id)) {
            const aggPos = aggregatePositions[agg.id]
            let aggY = currentY
            const baseAggHeight = computeDynamicHeight('Aggregate', agg)
            let aggHeight = baseAggHeight
            
            if (aggPos && aggPos.commandCount > 0) {
              // Position aggregate at the same Y as its first command
              aggY = aggPos.startY
              // Calculate height to span all commands (from first to last command bottom)
              aggHeight = aggPos.endY - aggPos.startY
              // Ensure minimum height
              aggHeight = Math.max(aggHeight, baseAggHeight)
            } else {
              // No commands for this aggregate - use default positioning
              aggY = currentY + idx * (baseAggHeight + gapY)
            }
            
            const node = {
              id: agg.id,
              type: 'aggregate',
              position: { x: aggregateX, y: aggY },
              data: { ...agg, label: agg.name, dynamicHeight: aggHeight },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, aggY + aggHeight)
          }
        })
        
        // Layout Events (right column) - prefer aligning with their emitting Command
        let eventCursor = currentY
        typeGroups.Event.forEach((evt) => {
          if (!isOnCanvas(evt.id)) {
            const h = computeDynamicHeight('Event', evt)
            const emitCmdId = eventToCommand[evt.id]
            const yPos = (emitCmdId && commandPositions[emitCmdId])
              ? commandPositions[emitCmdId].y
              : eventCursor

            const node = {
              id: evt.id,
              type: 'event',
              position: { x: eventX, y: yPos },
              data: { ...evt, label: evt.name, dynamicHeight: h },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, yPos + h)

            if (!(emitCmdId && commandPositions[emitCmdId])) {
              eventCursor += h + gapY
            }
          }
        })
        
        // Layout Policies (left of their invoking command)
        // Group policies by the command they invoke to handle multiple policies per command
        const policiesByCommand = {}
        const orphanPolicies = []
        const policyToCommand = {}
        relationships.forEach(rel => {
          if (rel.type === 'INVOKES' && rel.source && rel.target) policyToCommand[rel.source] = rel.target
        })
        
        typeGroups.Policy.forEach(pol => {
          if (!isOnCanvas(pol.id)) {
            // Try to find invokeCommandId from pol.invokeCommandId first, then from relationships
            const invokedCmdId = pol.invokeCommandId || policyToCommand[pol.id]
            if (invokedCmdId) {
              // Group by command ID even if command is not yet on canvas
              if (!policiesByCommand[invokedCmdId]) {
                policiesByCommand[invokedCmdId] = []
              }
              policiesByCommand[invokedCmdId].push(pol)
            } else {
              orphanPolicies.push(pol)
            }
          }
        })
        
        // Layout policies grouped by command (stack vertically to the left of each command)
        // First, calculate total height of all policy groups to position them above commands
        const policyGroupHeights = {}
        Object.entries(policiesByCommand).forEach(([cmdId, policies]) => {
          let totalHeight = 0
          policies.forEach(pol => {
            totalHeight += computeDynamicHeight('Policy', pol) + gapY
          })
          totalHeight -= gapY // Remove last gap
          policyGroupHeights[cmdId] = totalHeight
        })
        
        Object.entries(policiesByCommand).forEach(([cmdId, policies]) => {
          const cmdPos = commandPositions[cmdId]
          
          // If command is on canvas, position policies above the command to avoid overlap
          // Otherwise stack policies below existing content
          let baseY, baseX
          if (cmdPos) {
            // Position policies above the command
            // Calculate total height of this policy group
            const groupHeight = policyGroupHeights[cmdId] || 0
            // Position so that the last policy ends at or above the command's top
            // This ensures policies don't extend below the command and overlap with Events
            baseY = Math.max(currentY, cmdPos.y - groupHeight - gapY)
            // Use policyX (left of command) to ensure policies are positioned to the left
            // policyX is already calculated as commandX - policyWidth - gapX
            baseX = policyX
            
            console.log(`[addNodesWithLayout] Policy group for command ${cmdId}:`, {
              cmdPos: { x: cmdPos.x, y: cmdPos.y },
              commandX,
              policyX,
              baseX,
              baseY,
              groupHeight,
              policyCount: policies.length
            })
          } else {
            // Command not on canvas, stack below existing content
            baseY = maxBottom + 20
            baseX = policyX
          }
          
          // Stack policies vertically
          // If policy group height exceeds command height, shift policies further left
          const cmdHeight = cmdPos ? cmdPos.height : 0
          const groupHeight = policyGroupHeights[cmdId] || 0
          const exceedsCommandHeight = groupHeight > cmdHeight
          
          // Calculate X position: if exceeds command height, shift further left
          const basePolicyX = policyX
          const shiftedPolicyX = basePolicyX - policyWidth - gapX
          const finalPolicyX = exceedsCommandHeight ? shiftedPolicyX : basePolicyX
          
          let policyY = baseY
          policies.forEach((pol, idx) => {
            const h = computeDynamicHeight('Policy', pol)
            
            // Calculate cumulative height up to this policy
            let cumulativeHeight = 0
            if (idx > 0) {
              for (let i = 0; i < idx; i++) {
                cumulativeHeight += computeDynamicHeight('Policy', policies[i]) + gapY
              }
            }
            policyY = baseY + cumulativeHeight
            
            // If policy extends beyond command height, use shifted X position
            const policyBottom = policyY + h
            const cmdBottom = cmdPos ? (cmdPos.y + cmdHeight) : Infinity
            const useShiftedX = policyBottom > cmdBottom
            
            const xPos = useShiftedX ? shiftedPolicyX : finalPolicyX
            
            if (idx === 0) {
              console.log(`[addNodesWithLayout] Policy ${pol.name}:`, {
                xPos,
                yPos: policyY,
                height: h,
                cmdPos: cmdPos ? { x: cmdPos.x, y: cmdPos.y, height: cmdPos.height } : null,
                exceedsCommandHeight,
                useShiftedX
              })
            }
            
            const node = {
              id: pol.id,
              type: 'policy',
              // Use xPos directly to ensure policies are left of command
              position: { x: xPos, y: policyY },
              data: { ...pol, label: pol.name, dynamicHeight: h },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, policyY + h)
          })
        })
        
        // Layout orphan policies (those without an invokeCommandId)
        // Stack them vertically to avoid overlap
        let policyOffsetY = 0
        orphanPolicies.forEach((pol) => {
          const h = computeDynamicHeight('Policy', pol)
          const yPos = (maxBottom + 20) + policyOffsetY
          const xPos = policyX
          
          const node = {
            id: pol.id,
            type: 'policy',
            position: { x: Math.max(leftPadding, xPos), y: yPos },
            data: { ...pol, label: pol.name, dynamicHeight: h },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
          maxBottom = Math.max(maxBottom, yPos + h)
          policyOffsetY += h + gapY
        })

        // Layout ReadModels (bottom section, stacked vertically for proper UI alignment)
        const readModelPositions = {}
        const readModelY = maxBottom + 40

        typeGroups.ReadModel.forEach((rm, idx) => {
          if (!isOnCanvas(rm.id)) {
            const xPos = readModelX
            const yPos = readModelY + idx * (nodeHeight + gapY)
            readModelPositions[rm.id] = { x: xPos, y: yPos }
            const h = computeDynamicHeight('ReadModel', rm)
            const node = {
              id: rm.id,
              type: 'readmodel',
              position: { x: xPos, y: yPos },
              data: { ...rm, label: rm.name, dynamicHeight: h },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, yPos + h)
          }
        })

        // Layout UI stickers (positioned to the left of their attached Command/ReadModel)
        // UI stickers need special handling - they go to the left of commands,
        // so we may need to shift all existing nodes right and expand BC width
        const uiNodes = []
        const uiWidth = nodeTypeConfig.UI?.width || 130
        const uiGap = 5  // Tight spacing between stickers (almost adjacent)
        let uiFallbackY = currentY
        let minUiX = Infinity
        
        typeGroups.UI.forEach((ui, idx) => {
          if (!isOnCanvas(ui.id)) {
            let xPos = uiX
            let yPos = uiFallbackY
            const uiH = computeDynamicHeight('UI', ui)

            if (ui.attachedToId) {
              if (commandPositions[ui.attachedToId]) {
                yPos = commandPositions[ui.attachedToId].y
                xPos = commandPositions[ui.attachedToId].x - uiWidth - 5  // Tight gap between UI and Command
              } else if (readModelPositions[ui.attachedToId]) {
                yPos = readModelPositions[ui.attachedToId].y
                xPos = readModelPositions[ui.attachedToId].x - uiWidth - 5  // Tight gap between UI and ReadModel
              }
            } else {
              uiFallbackY += uiH + gapY
            }
            
            minUiX = Math.min(minUiX, xPos)
            uiNodes.push({ ui, xPos, yPos })
          }
        })
        
        // If UI stickers would be placed past the left boundary,
        // shift all existing nodes in this BC to the right
        // Note: leftPadding is already defined above (40) for consistent margins
        if (uiNodes.length > 0 && minUiX < leftPadding) {
          const shiftAmount = leftPadding - minUiX
          
          // Shift all already-added nodes in this BC
          nodes.value.forEach(node => {
            if (node.parentNode === bcId && node.type !== 'boundedcontext') {
              node.position = {
                ...node.position,
                x: node.position.x + shiftAmount
              }
            }
          })
          
          // Update position maps for accurate UI placement
          Object.keys(commandPositions).forEach(cmdId => {
            commandPositions[cmdId].x += shiftAmount
          })
          Object.keys(readModelPositions).forEach(rmId => {
            readModelPositions[rmId].x += shiftAmount
          })
          
          // Update UI positions after shift
          uiNodes.forEach(uiData => {
            uiData.xPos += shiftAmount
          })
        }
        
        // Now add UI nodes with corrected positions
        uiNodes.forEach(({ ui, xPos, yPos }) => {
          const uiH = computeDynamicHeight('UI', ui)
          const node = {
            id: ui.id,
            type: 'ui',
            position: { x: Math.max(leftPadding, xPos), y: yPos },
            data: { ...ui, label: ui.name, dynamicHeight: uiH },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
          maxBottom = Math.max(maxBottom, yPos + uiH)
        })
        
        // Update BC size (with shift already applied, just recalculate bounds)
        updateBCSize(bcId, true)
        
        bcIndex++
      }
    }
    
    // Add relationships as edges
    relationships.forEach(rel => {
      addEdge(rel.source, rel.target, rel.type)
    })
    
    return newNodes
  }
  
  // Calculate standalone position (for nodes without BC)
  function calculateStandalonePosition(nodeType, index) {
    const baseX = 100 + (index % 4) * 180
    const baseY = 100 + Math.floor(index / 4) * 120
    return { x: baseX, y: baseY }
  }
  
  // Helper function to get node's absolute X position (considering parent container)
  function getNodeAbsoluteX(nodeId) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (!node) return null
    
    let x = node.position?.x || 0
    // If node has a parent, add parent's position
    if (node.parentNode) {
      const parent = nodes.value.find(n => n.id === node.parentNode)
      if (parent) {
        x += parent.position?.x || 0
      }
    }
    return x
  }

  // Normalize position string to Vue Flow format
  function normalizePos(v) {
    const s = String(v || '').toLowerCase()
    if (s.includes('left')) return 'left'
    if (s.includes('right')) return 'right'
    if (s.includes('top')) return 'top'
    if (s.includes('bottom')) return 'bottom'
    return 'right' // fallback
  }

  // Convert position to Vue Flow format
  function toVuePos(p) {
    if (p === 'left') return 'left'
    if (p === 'right') return 'right'
    if (p === 'top') return 'top'
    if (p === 'bottom') return 'bottom'
    return 'right' // fallback
  }

  // Get all available handles for a node (DOM-based, same as AggregatePanel)
  function getAllHandlesForNode(nodeId) {
    const nodeEl = document.querySelector(`[data-id="${nodeId}"]`)
    if (!nodeEl) return []
    
    const handleEls = Array.from(nodeEl.querySelectorAll('.vue-flow__handle[data-handleid]'))
    
    if (handleEls.length === 0) return []
    
    return handleEls
      .map((el) => {
        const handleId = el.getAttribute('data-handleid')
        if (!handleId) return null
        
        const r = el.getBoundingClientRect()
        return {
          id: handleId,
          // Screen coordinates for distance comparison
          x: r.left + r.width / 2,
          y: r.top + r.height / 2,
          pos: normalizePos(el.getAttribute('data-handlepos')),
          type: el.getAttribute('data-handle-type') || 'unknown',
        }
      })
      .filter(Boolean)
  }

  // Helper function to determine optimal handles based on actual handle positions (DOM-based)
  // Uses same logic as AggregatePanel for consistency
  function getOptimalHandles(sourceId, targetId) {
    const srcAll = getAllHandlesForNode(sourceId)
    const tgtAll = getAllHandlesForNode(targetId)
    
    // Source: only general source handles (left-source, right-source)
    const src = srcAll.filter(h => h.id === 'left-source' || h.id === 'right-source')
    
    // Target: only general target handles (left-target, right-target)
    const tgt = tgtAll.filter(h => h.id === 'left-target' || h.id === 'right-target')
    
    // Fallback if no handles found
    if (!src.length || !tgt.length) {
      return {
        sourceHandle: 'right-source',
        sourcePosition: 'right',
        targetHandle: 'left-target',
        targetPosition: 'left',
      }
    }
    
    // Find the closest handle pair using screen coordinates
    let best = { d: Infinity, s: src[0], t: tgt[0] }
    for (const s of src) {
      for (const t of tgt) {
        const dx = t.x - s.x
        const dy = t.y - s.y
        const d = dx * dx + dy * dy
        if (d < best.d) {
          best = { d, s, t }
        }
      }
    }
    
    return {
      sourceHandle: best.s.id,
      sourcePosition: toVuePos(best.s.pos),
      targetHandle: best.t.id,
      targetPosition: toVuePos(best.t.pos),
    }
  }

  // Add an edge between nodes
  function addEdge(sourceId, targetId, edgeType) {
    const edgeId = `${sourceId}-${targetId}`
    
    // Check if edge already exists
    if (edges.value.find(e => e.id === edgeId)) {
      return null
    }
    
    // Only add if both nodes are on canvas
    if (!isOnCanvas(sourceId) || !isOnCanvas(targetId)) {
      return null
    }
    
    // Don't show container membership edges (implied by container)
    if (edgeType === 'HAS_AGGREGATE' || edgeType === 'HAS_POLICY' || edgeType === 'HAS_READMODEL' || edgeType === 'HAS_UI') {
      return null
    }
    
    const edgeStyle = getEdgeStyle(edgeType)
    const edge = {
      id: edgeId,
      source: sourceId,
      target: targetId,
      type: 'smoothstep',
      animated: edgeType === 'TRIGGERS',
      style: edgeStyle,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: edgeStyle.stroke || '#909296',
      },
      label: getEdgeLabel(edgeType),
      labelStyle: { fill: '#c1c2c5', fontSize: 10, fontWeight: 500 },
      labelBgStyle: { fill: '#1e1e2e', fillOpacity: 0.9 },
      labelBgPadding: [4, 4],
      data: {
        edgeType: edgeType // Store edgeType for filtering
      }
    }
    
    // Determine optimal handles based on actual handle positions (DOM-based)
    const handles = getOptimalHandles(sourceId, targetId)
    edge.sourceHandle = handles.sourceHandle
    edge.sourcePosition = handles.sourcePosition
    edge.targetHandle = handles.targetHandle
    edge.targetPosition = handles.targetPosition
    
    edges.value.push(edge)
    // Ensure consumers relying on reference changes (e.g. Vue Flow) observe updates.
    edges.value = [...edges.value]
    return edge
  }

  // Update edges for moved nodes - recalculate handles for affected edges
  function rerouteEdgesForMovedNodes(movedNodeIds) {
    if (!movedNodeIds || movedNodeIds.length === 0) return
    
    // Wait for DOM to update with new positions
    setTimeout(() => {
      const updatedEdges = edges.value.map(edge => {
        // Only update edges connected to moved nodes
        const touchesMoved = movedNodeIds.includes(edge.source) || movedNodeIds.includes(edge.target)
        if (!touchesMoved) return edge
        
        // Recalculate optimal handles for this edge
        const handles = getOptimalHandles(edge.source, edge.target)
        
        // Only update if handles or positions changed
        if (edge.sourceHandle !== handles.sourceHandle || 
            edge.targetHandle !== handles.targetHandle ||
            edge.sourcePosition !== handles.sourcePosition ||
            edge.targetPosition !== handles.targetPosition) {
          return {
            ...edge,
            sourceHandle: handles.sourceHandle,
            sourcePosition: handles.sourcePosition,
            targetHandle: handles.targetHandle,
            targetPosition: handles.targetPosition
          }
        }
        
        return edge
      })
      
      // Update edges array
      edges.value = updatedEdges
    }, 50) // Small delay to ensure DOM is updated
  }
  
  // Get edge style based on type
  function getEdgeStyle(edgeType) {
    const styles = {
      EMITS: { stroke: '#fd7e14', strokeWidth: 2 },
      TRIGGERS: { stroke: '#b197fc', strokeWidth: 2 },
      INVOKES: { stroke: '#5c7cfa', strokeWidth: 2 },
      HAS_COMMAND: { stroke: '#fcc419', strokeWidth: 1.5, strokeDasharray: '4 2' }
    }
    return styles[edgeType] || { stroke: '#909296', strokeWidth: 1 }
  }
  
  // Get edge label
  function getEdgeLabel(edgeType) {
    const labels = {
      EMITS: '',
      TRIGGERS: 'triggers',
      INVOKES: 'invokes',
      HAS_COMMAND: ''
    }
    return labels[edgeType] || ''
  }
  
  // Remove a node from canvas
  function removeNode(nodeId) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (node?.parentNode) {
      // Update BC size after removal
      setTimeout(() => updateBCSize(node.parentNode), 0)
    }
    
    nodes.value = nodes.value.filter(n => n.id !== nodeId)
    edges.value = edges.value.filter(e => e.source !== nodeId && e.target !== nodeId)

    // Also remove from selection if present
    if (selectedNodeIds.value.has(nodeId)) {
      selectedNodeIds.value.delete(nodeId)
      selectedNodeIds.value = new Set(selectedNodeIds.value)
    }
  }
  
  // Clear canvas
  function clearCanvas() {
    nodes.value = []
    edges.value = []
    bcContainers.value = {}
    selectedNodeIds.value = new Set()
    collapsedBCs.value = new Set()
  }
  
  // Check if BC is collapsed
  function isBCCollapsed(bcId) {
    return collapsedBCs.value.has(bcId)
  }
  
  // Toggle BC collapse state
  function toggleBCCollapse(bcId) {
    if (collapsedBCs.value.has(bcId)) {
      collapsedBCs.value.delete(bcId)
    } else {
      collapsedBCs.value.add(bcId)
    }
    collapsedBCs.value = new Set(collapsedBCs.value)
    
    // Update visibility of child nodes
    updateChildNodesVisibility(bcId)
  }
  
  // Update visibility of child nodes when BC is collapsed/expanded
  function updateChildNodesVisibility(bcId) {
    const isCollapsed = collapsedBCs.value.has(bcId)
    const bcNode = nodes.value.find(n => n.id === bcId)
    
    if (!bcNode) return
    
    // Get child nodes
    const childNodes = nodes.value.filter(n => n.parentNode === bcId)
    
    // Update hidden property for child nodes
    childNodes.forEach(child => {
      child.hidden = isCollapsed
    })
    
    // Also hide/show edges connected to child nodes
    const childIds = new Set(childNodes.map(n => n.id))
    edges.value.forEach(edge => {
      if (childIds.has(edge.source) || childIds.has(edge.target)) {
        edge.hidden = isCollapsed
      }
    })
    
    // Update BC size when collapsed
    if (isCollapsed) {
      // Store original size
      if (!bcNode.data.originalStyle) {
        bcNode.data.originalStyle = { ...bcNode.style }
      }
      // Collapse to header only
      bcNode.style = {
        ...bcNode.style,
        height: '48px'
      }
    } else {
      // Restore original size
      if (bcNode.data.originalStyle) {
        bcNode.style = { ...bcNode.data.originalStyle }
      } else {
        updateBCSize(bcId)
      }
    }
    
    // Trigger reactivity
    nodes.value = [...nodes.value]
    edges.value = [...edges.value]
  }
  
  // Remove BC and all its children
  function removeBC(bcId) {
    // Get all child nodes
    const childNodeIds = nodes.value
      .filter(n => n.parentNode === bcId)
      .map(n => n.id)
    
    // Remove child nodes
    childNodeIds.forEach(id => {
      selectedNodeIds.value.delete(id)
    })
    
    // Remove from collapsed set
    collapsedBCs.value.delete(bcId)
    collapsedBCs.value = new Set(collapsedBCs.value)
    
    // Remove BC container tracking
    delete bcContainers.value[bcId]
    
    // Remove all related edges
    edges.value = edges.value.filter(e => 
      !childNodeIds.includes(e.source) && 
      !childNodeIds.includes(e.target) &&
      e.source !== bcId && 
      e.target !== bcId
    )
    
    // Remove all nodes (children + BC)
    nodes.value = nodes.value.filter(n => 
      n.id !== bcId && n.parentNode !== bcId
    )
    
    // Remove BC from selection
    selectedNodeIds.value.delete(bcId)
    selectedNodeIds.value = new Set(selectedNodeIds.value)
  }

  // Add a new node to an existing BC on canvas (used by chat create action)
  function addNodeToBC(nodeData, bcId) {
    if (isOnCanvas(nodeData.id)) return null

    const bcNode = nodes.value.find(n => n.id === bcId && n.type === 'boundedcontext')
    if (!bcNode) return null

    const nodeType = nodeData.type
    // Consistent padding value (matching updateBCSize and calculatePositionInBC)
    const leftPadding = 40
    const uiWidth = nodeTypeConfig.UI?.width || 130
    const uiGap = 5  // Tight spacing between stickers (almost adjacent)
    
    let position
    
    // Special handling for UI stickers - place to the left of attached command
    if (nodeType === 'UI') {
      // Find the command positions in this BC
      const commandsInBC = nodes.value.filter(n => 
        n.parentNode === bcId && n.data?.type === 'Command'
      )
      const readModelsInBC = nodes.value.filter(n => 
        n.parentNode === bcId && n.data?.type === 'ReadModel'
      )
      
      let xPos = leftPadding
      let yPos = 70 // Default Y (below header)
      
      // If UI is attached to a command, position to the left of that command
      if (nodeData.attachedToId) {
        const attachedCommand = commandsInBC.find(c => c.id === nodeData.attachedToId)
        const attachedReadModel = readModelsInBC.find(r => r.id === nodeData.attachedToId)
        
        if (attachedCommand) {
          xPos = attachedCommand.position.x - uiWidth - uiGap
          yPos = attachedCommand.position.y
        } else if (attachedReadModel) {
          xPos = attachedReadModel.position.x - uiWidth - uiGap
          yPos = attachedReadModel.position.y
        }
      } else if (commandsInBC.length > 0) {
        // Default: position to the left of the first command
        const firstCmd = commandsInBC.reduce((min, cmd) => 
          cmd.position.y < min.position.y ? cmd : min
        , commandsInBC[0])
        xPos = firstCmd.position.x - uiWidth - uiGap
        yPos = firstCmd.position.y
      }
      
      // If UI would be placed past left boundary, shift all existing nodes right
      if (xPos < leftPadding) {
        const shiftAmount = leftPadding - xPos
        
        // Shift all children in this BC to the right
        nodes.value.forEach(node => {
          if (node.parentNode === bcId) {
            node.position = {
              ...node.position,
              x: node.position.x + shiftAmount
            }
          }
        })
        
        // Update xPos after shift
        xPos = leftPadding
        // No need to update yPos - it stays the same
      }
      
      // Check for existing UI stickers at same Y to avoid overlap
      const existingUIsAtY = nodes.value.filter(n => 
        n.parentNode === bcId && 
        n.data?.type === 'UI' &&
        Math.abs(n.position.y - yPos) < 50
      )
      if (existingUIsAtY.length > 0) {
        // Stack UI stickers vertically with tight spacing
        const nodeHeight = nodeTypeConfig.UI?.height || 110
        yPos = existingUIsAtY[existingUIsAtY.length - 1].position.y + nodeHeight + 5
      }
      
      position = { x: xPos, y: yPos }
    } else {
      // For other node types, use default positioning
      position = calculatePositionInBC(bcId, nodeType, 0)
    }
    
    const node = {
      id: nodeData.id,
      type: nodeType.toLowerCase(),
      position,
      data: {
        ...nodeData,
        label: nodeData.name,
        bcId,
        dynamicHeight: computeDynamicHeight(nodeType, nodeData)
      },
      parentNode: bcId,
      extent: 'parent'
    }

    nodes.value.push(node)
    updateBCSize(bcId, true)
    return node
  }

  // Sync canvas with applied chat changes
  function syncAfterChanges(changes) {
    for (const change of changes || []) {
      const action = change.action
      const targetId = change.targetId

      if (!action || !targetId) continue

      // Property nodes are embedded into their parent and are not rendered as separate nodes/edges.
      if (change.targetType === 'Property') {
        const parentId = change.parentId

        if (action === 'create') {
          updateEmbeddedProperties(parentId, props => {
            const next = props.filter(p => p?.id !== targetId)
            next.push({
              id: targetId,
              name: change.name || change.targetName,
              type: change.type,
              description: change.description ?? '',
              isKey: !!change.isKey,
              isForeignKey: !!change.isForeignKey,
              isRequired: !!change.isRequired,
              parentType: change.parentType,
              parentId: parentId
            })
            return next
          })
        } else if (action === 'update' || action === 'rename') {
          updateEmbeddedProperties(parentId, props => {
            const next = [...props]
            const i = next.findIndex(p => p?.id === targetId)
            if (i === -1) return next
            next[i] = {
              ...next[i],
              name: change.name || change.targetName || next[i]?.name,
              type: change.type ?? next[i]?.type,
              description: change.description ?? next[i]?.description ?? '',
              isKey: change.isKey ?? next[i]?.isKey,
              isForeignKey: change.isForeignKey ?? next[i]?.isForeignKey,
              isRequired: change.isRequired ?? next[i]?.isRequired
            }
            return next
          })
        } else if (action === 'delete') {
          updateEmbeddedProperties(parentId, props => props.filter(p => p?.id !== targetId))
        }
        continue
      }

      if (action === 'rename' || action === 'update') {
        const idx = nodes.value.findIndex(n => n.id === targetId)
        if (idx !== -1) {
          const existing = nodes.value[idx]
          const nextName = change.targetName || existing.data?.name
          nodes.value[idx] = {
            ...existing,
            data: {
              ...existing.data,
              name: nextName,
              label: nextName || existing.data?.label,
              description: change.description || existing.data?.description,
              // Inspector MVP fields (safe no-op for non-matching node types)
              actor: change.actor ?? existing.data?.actor,
              version: change.version ?? existing.data?.version,
              rootEntity: change.rootEntity ?? existing.data?.rootEntity,
              provisioningType: change.provisioningType ?? existing.data?.provisioningType,
              // UI specific fields (safe no-op for non-UI nodes)
              template: change.template ?? existing.data?.template,
              attachedToId: change.attachedToId ?? existing.data?.attachedToId,
              attachedToType: change.attachedToType ?? existing.data?.attachedToType,
              attachedToName: change.attachedToName ?? existing.data?.attachedToName
            }
          }
          nodes.value = [...nodes.value]
        }
      } else if (action === 'create') {
        const bcId = change.targetBcId || change.bcId
        if (bcId && isOnCanvas(bcId)) {
          addNodeToBC(
            {
              id: targetId,
              name: change.targetName,
              type: change.targetType,
              description: change.description,
              bcId,
              // UI fields (optional)
              template: change.template,
              attachedToId: change.attachedToId,
              attachedToType: change.attachedToType,
              attachedToName: change.attachedToName
            },
            bcId
          )
        }
      } else if (action === 'delete') {
        removeNode(targetId)
      } else if (action === 'connect') {
        const sourceId = change.sourceId
        const connectionType = change.connectionType || 'TRIGGERS'
        if (connectionType === 'REFERENCES') {
          // FK reference is only represented in Property metadata (not as an edge on canvas)
          const sourceParentId = change.sourceParentId
          if (sourceId && sourceParentId) {
            updateEmbeddedProperties(sourceParentId, props => {
              const next = [...props]
              const i = next.findIndex(p => p?.id === sourceId)
              if (i === -1) return next
              next[i] = { ...next[i], isForeignKey: true }
              return next
            })
          }
        } else if (sourceId && isOnCanvas(sourceId) && isOnCanvas(targetId)) {
          addEdge(sourceId, targetId, connectionType)
        }
      }
    }
  }
  
  // Update node position
  function updateNodePosition(nodeId, position) {
    const node = nodes.value.find(n => n.id === nodeId)
    if (node) {
      node.position = position
      if (node.parentNode) {
        updateBCSize(node.parentNode)
      }
    }
  }
  
  // Helper to sync BC position from Vue Flow (called from CanvasWorkspace)
  function syncBCPositionFromVueFlow(bcId, vueFlowPosition) {
    const bcNode = nodes.value.find(n => n.id === bcId && n.type === 'boundedcontext')
    if (bcNode && vueFlowPosition) {
      bcNode.position = { x: vueFlowPosition.x, y: vueFlowPosition.y }
    }
  }
  
  // Find and add relations between existing nodes
  async function findAndAddRelations() {
    if (nodes.value.length < 2) return
    
    const ids = nodes.value.map(n => n.id)
    
    try {
      const params = new URLSearchParams()
      ids.forEach(id => params.append('node_ids', id))
      
      const response = await fetch(`/api/graph/find-relations?${params}`)
      const relations = await response.json()
      
      relations.forEach(rel => {
        addEdge(rel.source, rel.target, rel.type)
      })
    } catch (error) {
      console.error('Failed to find relations:', error)
    }
  }
  
  // Find cross-BC relations when adding new nodes
  async function findCrossBCRelations(newNodeIds) {
    if (newNodeIds.length === 0 || nodes.value.length < 2) return
    
    // Get existing node IDs (excluding the new ones)
    const existingIds = nodes.value
      .map(n => n.id)
      .filter(id => !newNodeIds.includes(id))
    
    if (existingIds.length === 0) return
    
    try {
      const params = new URLSearchParams()
      newNodeIds.forEach(id => params.append('new_node_ids', id))
      existingIds.forEach(id => params.append('existing_node_ids', id))
      
      const response = await fetch(`/api/graph/find-cross-bc-relations?${params}`)
      const relations = await response.json()
      
      let addedCount = 0
      relations.forEach(rel => {
        const edge = addEdge(rel.source, rel.target, rel.type)
        if (edge) addedCount++
      })
      
      console.log(`Found ${addedCount} cross-BC relations`)
    } catch (error) {
      console.error('Failed to find cross-BC relations:', error)
    }
  }
  
  // Find a position that avoids obstacles (existing nodes)
  function findAvoidingPosition(preferredX, preferredY, width, height) {
    const padding = 30
    const stepSize = 50
    const maxAttempts = 50
    
    // Get all existing node bounds
    const obstacles = nodes.value.map(n => {
      const config = nodeTypeConfig[n.data?.type] || { width: 150, height: 100 }
      const nodeWidth = n.type === 'boundedcontext' ? 
        parseInt(n.style?.width || '400') : config.width
      const nodeHeight = n.type === 'boundedcontext'
        ? parseInt(n.style?.height || '300')
        : getNodeHeight(n)
      
      return {
        x: n.position.x,
        y: n.position.y,
        width: nodeWidth,
        height: nodeHeight,
        right: n.position.x + nodeWidth,
        bottom: n.position.y + nodeHeight
      }
    })
    
    // Check if position collides with any obstacle
    function collides(x, y, w, h) {
      for (const obs of obstacles) {
        if (x < obs.right + padding &&
            x + w + padding > obs.x &&
            y < obs.bottom + padding &&
            y + h + padding > obs.y) {
          return true
        }
      }
      return false
    }
    
    // If preferred position is free, use it
    if (!collides(preferredX, preferredY, width, height)) {
      return { x: preferredX, y: preferredY }
    }
    
    // Try positions in expanding spiral pattern
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      // Try right
      let testX = preferredX + attempt * stepSize
      let testY = preferredY
      if (!collides(testX, testY, width, height)) {
        return { x: testX, y: testY }
      }
      
      // Try below
      testX = preferredX
      testY = preferredY + attempt * stepSize
      if (!collides(testX, testY, width, height)) {
        return { x: testX, y: testY }
      }
      
      // Try right-below diagonal
      testX = preferredX + attempt * stepSize
      testY = preferredY + attempt * stepSize
      if (!collides(testX, testY, width, height)) {
        return { x: testX, y: testY }
      }
    }
    
    // Fallback: place to the right of all existing nodes
    const maxRight = Math.max(0, ...obstacles.map(o => o.right))
    return { x: maxRight + padding + 50, y: preferredY }
  }
  
  // Expand Event to show triggered Policies and their BCs
  async function expandEventTriggers(eventId) {
    try {
      const response = await fetch(`/api/graph/event-triggers/${eventId}`)
      if (!response.ok) {
        console.log('No triggers found for event:', eventId)
        return []
      }
      
      const data = await response.json()
      
      if (!data.nodes || data.nodes.length === 0) {
        console.log('Event has no triggers:', eventId)
        return []
      }
      
      // Find the source event node to position new nodes relative to it
      const sourceEventNode = nodes.value.find(n => n.id === eventId)
      if (!sourceEventNode) {
        console.log('Source event node not found on canvas:', eventId)
        return []
      }
      
      const startX = sourceEventNode.position.x + 200
      const startY = sourceEventNode.position.y
      
      const newNodes = []
      const bcMap = {}
      
      // Group nodes by BC
      data.nodes.forEach(nodeData => {
        if (nodeData.type === 'BoundedContext') {
          // Always add to bcMap, even if BC is already on canvas (to add children)
          if (!bcMap[nodeData.id]) {
            bcMap[nodeData.id] = {
              bc: nodeData,
              children: []
            }
          }
        }
      })
      
      // If no BCs found in response, log and return
      if (Object.keys(bcMap).length === 0) {
        console.warn('No BoundedContexts found in API response for event:', eventId, 'nodes:', data.nodes)
        return []
      }
      
      data.nodes.forEach(nodeData => {
        if (nodeData.type !== 'BoundedContext' && nodeData.bcId) {
          if (bcMap[nodeData.bcId]) {
            bcMap[nodeData.bcId].children.push(nodeData)
          } else {
            console.warn('Child node has bcId but BC not in bcMap:', nodeData.type, nodeData.id, 'bcId:', nodeData.bcId)
          }
        }
      })
      
      // Place each BC with obstacle avoidance
      let bcOffsetY = 0
      for (const [bcId, { bc, children }] of Object.entries(bcMap)) {
        // Check if BC already exists - if so, use existing position
        const existingBC = nodes.value.find(n => n.id === bcId && n.type === 'boundedcontext')
        let bcNode
        let bcPosition
        // Ensure bcWidth/bcHeight are always defined (used for placement & offset increment)
        const bcWidth = 550
        let bcHeight = 300
        
        if (existingBC) {
          // BC already exists - use its current position (don't overwrite)
          bcNode = existingBC
          bcPosition = existingBC.position
          // Derive a reasonable height from existing style (fallback to default)
          try {
            const h = existingBC.style?.height
            const parsed = typeof h === 'string' ? parseInt(h, 10) : Number(h)
            if (!Number.isNaN(parsed) && parsed > 0) {
              bcHeight = parsed
            }
          } catch (e) {
            // keep default
          }
        } else {
          // Calculate BC size based on children
          const numChildren = children.length
          bcHeight = Math.max(300, 80 + Math.ceil(numChildren / 3) * 100 + 80)
          
          // Find position avoiding obstacles
          bcPosition = findAvoidingPosition(
            startX,
            startY + bcOffsetY,
            bcWidth,
            bcHeight
          )
          
          // Create BC container
          bcNode = {
            id: bc.id,
            type: 'boundedcontext',
            position: bcPosition,
            data: {
              ...bc,
              label: bc.name
            },
            style: {
              width: `${bcWidth}px`,
              height: `${bcHeight}px`
            },
            className: 'bc-group-node'
          }
          nodes.value.push(bcNode)
        }
        
        newNodes.push(bcNode)
        
        // Layout children inside BC
        // Consistent padding values (matching updateBCSize and calculatePositionInBC)
        // Layout: Policy(왼쪽) → Command(왼쪽) → Aggregate(중앙) → Event(오른쪽)
        const headerHeight = 50
        const topPadding = 30
        const leftPadding = 40
        const nodeHeight = 90
        const gapX = 5   // Tight spacing between stickers (almost adjacent)
        const gapY = 5   // Tight spacing between stickers (almost adjacent)
        let currentY = headerHeight + topPadding
        
        // Sticker widths for tight layout
        const commandWidth = nodeTypeConfig.Command?.width || 140
        const aggregateWidth = nodeTypeConfig.Aggregate?.width || 160
        const policyWidth = nodeTypeConfig.Policy?.width || 130
        
        // Calculate X positions: stickers almost adjacent
        const commandX = leftPadding
        const aggregateX = commandX + commandWidth + gapX
        const eventX = aggregateX + aggregateWidth + gapX
        const policyX = commandX - policyWidth - gapX
        
        // Group by type (include UI and ReadModel)
        const typeGroups = { Aggregate: [], Command: [], Event: [], Policy: [], UI: [], ReadModel: [] }
        children.forEach(child => {
          if (!isOnCanvas(child.id) && typeGroups[child.type]) {
            typeGroups[child.type].push(child)
          }
        })

        // Parent maps from relationships (preferred) or fallback fields)
        const commandToAggregate = {}
        const eventToCommand = {}
        const policyToCommand = {}  // Map Policy ID to Command ID via INVOKES relationship
        ;(data.relationships || []).forEach(rel => {
          if (rel.type === 'HAS_COMMAND' && rel.source && rel.target) commandToAggregate[rel.target] = rel.source
          if (rel.type === 'EMITS' && rel.source && rel.target) eventToCommand[rel.target] = rel.source
          if (rel.type === 'INVOKES' && rel.source && rel.target) policyToCommand[rel.source] = rel.target
        })
        
        // Fallback: derive parentId from HAS_COMMAND relationships if not already set
        // This ensures Command-Aggregate mapping works even if backend didn't include parentId
        if (data.relationships) {
          data.relationships.forEach(rel => {
            if (rel.type === 'HAS_COMMAND') {
              const cmd = children.find(c => c.id === rel.target && c.type === 'Command')
              if (cmd && !cmd.parentId) {
                cmd.parentId = rel.source  // Aggregate ID
              }
            }
          })
        }
        
        // Group Commands by their parent Aggregate
        const commandsByAggregate = {}
        typeGroups.Command.forEach(cmd => {
          const aggId = commandToAggregate[cmd.id] || cmd.parentId
          if (aggId) {
            if (!commandsByAggregate[aggId]) commandsByAggregate[aggId] = []
            commandsByAggregate[aggId].push(cmd)
          }
        })
        
        // Layout Commands (left) grouped by parent Aggregate and track positions
        const commandPositions = {}
        const aggregatePositions = {} // Track Y range for each aggregate
        let yCursor = currentY
        let maxBottom = currentY
        
        typeGroups.Aggregate.forEach(agg => {
          const aggCommands = commandsByAggregate[agg.id] || []
          const startY = yCursor
          
          aggCommands.forEach((cmd) => {
            const h = computeDynamicHeight('Command', cmd)
            const yPos = yCursor
            commandPositions[cmd.id] = { x: commandX, y: yPos, height: h }
            const node = {
              id: cmd.id,
              type: 'command',
              position: { x: commandX, y: yPos },
              data: { ...cmd, label: cmd.name, dynamicHeight: h },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, yPos + h)
            yCursor += h + gapY
          })
          
          // Track the Y range for this aggregate
          if (aggCommands.length > 0) {
            const endY = yCursor - gapY
            aggregatePositions[agg.id] = { startY, endY, commandCount: aggCommands.length }
          }
        })
        
        // Also layout any orphan commands (without parentId)
        const orphanCommands = typeGroups.Command.filter(cmd => !(commandToAggregate[cmd.id] || cmd.parentId))
        orphanCommands.forEach(cmd => {
          const h = computeDynamicHeight('Command', cmd)
          const yPos = yCursor
          commandPositions[cmd.id] = { x: commandX, y: yPos, height: h }
          const node = {
            id: cmd.id,
            type: 'command',
            position: { x: commandX, y: yPos },
            data: { ...cmd, label: cmd.name, dynamicHeight: h },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
          maxBottom = Math.max(maxBottom, yPos + h)
          yCursor += h + gapY
        })
        
        // Layout Aggregates (center) - height spans all its Commands
        typeGroups.Aggregate.forEach((agg, idx) => {
          const aggPos = aggregatePositions[agg.id]
          let aggY = currentY
          const baseAggHeight = computeDynamicHeight('Aggregate', agg)
          let aggHeight = baseAggHeight
          
          if (aggPos && aggPos.commandCount > 0) {
            // Position aggregate at the same Y as its first command
            aggY = aggPos.startY
            // Calculate height to span all commands (from first to last command bottom)
            aggHeight = aggPos.endY - aggPos.startY
            // Ensure minimum height
            aggHeight = Math.max(aggHeight, baseAggHeight)
          } else {
            // No commands for this aggregate - use default positioning
            aggY = currentY + idx * (baseAggHeight + gapY)
          }
          
          const node = {
            id: agg.id,
            type: 'aggregate',
            position: { x: aggregateX, y: aggY },
            data: { ...agg, label: agg.name, dynamicHeight: aggHeight },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
          maxBottom = Math.max(maxBottom, aggY + aggHeight)
        })
        
        // Layout Events (right)
        let eventCursor = currentY
        typeGroups.Event.forEach((evt) => {
          const h = computeDynamicHeight('Event', evt)
          const emitCmdId = eventToCommand[evt.id]
          const yPos = (emitCmdId && commandPositions[emitCmdId])
            ? commandPositions[emitCmdId].y
            : eventCursor
          const node = {
            id: evt.id,
            type: 'event',
            position: { x: eventX, y: yPos },
            data: { ...evt, label: evt.name, dynamicHeight: h },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
          maxBottom = Math.max(maxBottom, yPos + h)
          if (!(emitCmdId && commandPositions[emitCmdId])) {
            eventCursor += h + gapY
          }
        })
        
        // Layout Policies (left of their invoking command)
        // Group policies by the command they invoke to handle multiple policies per command
        const policiesByCommand = {}
        const orphanPolicies = []
        
        // Calculate policyX if not already defined (for expandEventTriggers)
        // policyWidth is already defined above, so reuse it
        const calculatedPolicyX = policyX || (commandX - policyWidth - gapX)
        
        typeGroups.Policy.forEach(pol => {
          // Try to find invokeCommandId from pol.invokeCommandId first, then from relationships
          const invokedCmdId = pol.invokeCommandId || policyToCommand[pol.id]
          if (invokedCmdId) {
            // Group by command ID even if command is not yet on canvas
            if (!policiesByCommand[invokedCmdId]) {
              policiesByCommand[invokedCmdId] = []
            }
            policiesByCommand[invokedCmdId].push(pol)
          } else {
            orphanPolicies.push(pol)
          }
        })
        
        // Layout policies grouped by command (stack vertically to the left of each command)
        // First, calculate total height of all policy groups to position them above commands
        const policyGroupHeights = {}
        Object.entries(policiesByCommand).forEach(([cmdId, policies]) => {
          let totalHeight = 0
          policies.forEach(pol => {
            totalHeight += computeDynamicHeight('Policy', pol) + gapY
          })
          totalHeight -= gapY // Remove last gap
          policyGroupHeights[cmdId] = totalHeight
        })
        
        Object.entries(policiesByCommand).forEach(([cmdId, policies]) => {
          const cmdPos = commandPositions[cmdId]
          
          // If command is on canvas, position policies above the command to avoid overlap
          // Otherwise stack policies below existing content
          let baseY, baseX
          if (cmdPos) {
            // Position policies above the command
            // Calculate total height of this policy group
            const groupHeight = policyGroupHeights[cmdId] || 0
            // Position so that the last policy ends at or above the command's top
            // This ensures policies don't extend below the command and overlap with Events
            baseY = Math.max(currentY, cmdPos.y - groupHeight - gapY)
            // Use calculatedPolicyX to ensure policies are left of command
            baseX = calculatedPolicyX
            
            console.log(`[expandEventTriggers] Policy group for command ${cmdId}:`, {
              cmdPos: { x: cmdPos.x, y: cmdPos.y },
              commandX,
              policyX,
              calculatedPolicyX,
              baseX,
              baseY,
              groupHeight,
              policyCount: policies.length
            })
          } else {
            // Command not on canvas, stack below existing content
            baseY = maxBottom + 20
            baseX = calculatedPolicyX
          }
          
          // Stack policies vertically starting from baseY
          // If policy group height exceeds command height, shift policies further left
          const cmdHeight = cmdPos ? cmdPos.height : 0
          const groupHeight = policyGroupHeights[cmdId] || 0
          const exceedsCommandHeight = groupHeight > cmdHeight
          
          // Calculate X position: if exceeds command height, shift further left
          const basePolicyX = calculatedPolicyX
          const shiftedPolicyX = basePolicyX - policyWidth - gapX
          const finalPolicyX = exceedsCommandHeight ? shiftedPolicyX : basePolicyX
          
          let policyY = baseY
          policies.forEach((pol, idx) => {
            const h = computeDynamicHeight('Policy', pol)
            
            // Calculate cumulative height up to this policy
            let cumulativeHeight = 0
            if (idx > 0) {
              for (let i = 0; i < idx; i++) {
                cumulativeHeight += computeDynamicHeight('Policy', policies[i]) + gapY
              }
            }
            policyY = baseY + cumulativeHeight
            
            // If policy extends beyond command height, use shifted X position
            const policyBottom = policyY + h
            const cmdBottom = cmdPos ? (cmdPos.y + cmdHeight) : Infinity
            const useShiftedX = policyBottom > cmdBottom
            
            const xPos = useShiftedX ? shiftedPolicyX : finalPolicyX
            
            console.log(`[expandEventTriggers] Policy ${pol.name} (${idx}/${policies.length - 1}):`, {
              xPos,
              yPos: policyY,
              height: h,
              cmdPos: cmdPos ? { x: cmdPos.x, y: cmdPos.y, height: cmdPos.height } : null,
              exceedsCommandHeight,
              useShiftedX
            })
            
            const node = {
              id: pol.id,
              type: 'policy',
              // Use xPos directly to ensure policies are left of command
              position: { x: xPos, y: policyY },
              data: { ...pol, label: pol.name, dynamicHeight: h },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, policyY + h)
          })
        })
        
        // Layout orphan policies (those without an invokeCommandId)
        // Stack them vertically to avoid overlap
        let policyOffsetY = 0
        orphanPolicies.forEach((pol) => {
          const h = computeDynamicHeight('Policy', pol)
          const yPos = (maxBottom + 20) + policyOffsetY
          const xPos = policyX
          
          const node = {
            id: pol.id,
            type: 'policy',
            position: { x: Math.max(leftPadding, xPos), y: yPos },
            data: { ...pol, label: pol.name, dynamicHeight: h },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
          maxBottom = Math.max(maxBottom, yPos + h)
          policyOffsetY += h + gapY
        })
        
        // Layout ReadModels (bottom section, stacked vertically)
        const readModelPositions = {}
        const readModelY = maxBottom + 40
        const readModelWidth = nodeTypeConfig.ReadModel?.width || 170
        const readModelX = aggregateX  // ReadModel below Aggregate
        
        typeGroups.ReadModel.forEach((rm, idx) => {
          if (!isOnCanvas(rm.id)) {
            const xPos = readModelX
            const yPos = readModelY + idx * (nodeHeight + gapY)
            readModelPositions[rm.id] = { x: xPos, y: yPos }
            const h = computeDynamicHeight('ReadModel', rm)
            const node = {
              id: rm.id,
              type: 'readmodel',
              position: { x: xPos, y: yPos },
              data: { ...rm, label: rm.name, dynamicHeight: h },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, yPos + h)
          }
        })
        
        // Layout UI stickers (positioned to the left of their attached Command/ReadModel)
        const uiWidth = nodeTypeConfig.UI?.width || 130
        const uiGap = 5
        let uiFallbackY = currentY
        let minUiX = Infinity
        
        typeGroups.UI.forEach((ui, idx) => {
          if (!isOnCanvas(ui.id)) {
            let xPos = policyX - uiWidth - gapX  // Left of Policy
            let yPos = uiFallbackY
            const uiH = computeDynamicHeight('UI', ui)
            
            if (ui.attachedToId) {
              if (commandPositions[ui.attachedToId]) {
                yPos = commandPositions[ui.attachedToId].y
                xPos = commandPositions[ui.attachedToId].x - uiWidth - uiGap
              } else if (readModelPositions[ui.attachedToId]) {
                yPos = readModelPositions[ui.attachedToId].y
                xPos = readModelPositions[ui.attachedToId].x - uiWidth - uiGap
              }
            } else if (typeGroups.Command.length > 0) {
              // Default: position to the left of the first command
              const firstCmd = typeGroups.Command[0]
              if (commandPositions[firstCmd.id]) {
                yPos = commandPositions[firstCmd.id].y
                xPos = commandPositions[firstCmd.id].x - uiWidth - uiGap
              }
            }
            
            minUiX = Math.min(minUiX, xPos)
            const node = {
              id: ui.id,
              type: 'ui',
              position: { x: xPos, y: yPos },
              data: { ...ui, label: ui.name, dynamicHeight: uiH },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            maxBottom = Math.max(maxBottom, yPos + uiH)
            uiFallbackY += uiH + gapY
          }
        })
        
        updateBCSize(bcId, true)
        bcOffsetY += bcHeight + 50
      }
      
      // Add relationships as edges
      data.relationships.forEach(rel => {
        addEdge(rel.source, rel.target, rel.type)
      })
      
      // Find additional cross-BC relations
      const newNodeIds = newNodes.map(n => n.id)
      await findCrossBCRelations(newNodeIds)
      
      return newNodes
    } catch (error) {
      console.error('Failed to expand event triggers:', error)
      return []
    }
  }
  
  return {
    nodes,
    edges,
    selectedNodeIds,
    selectedNodes,
    nodeIds,
    nodeTypeConfig,
    bcContainers,
    collapsedBCs,
    rightPanelMode,
    showDesignLevel, // Export showDesignLevel for reactivity
    isOnCanvas,
    isSelected,
    isBCCollapsed,
    toggleBCCollapse,
    toggleNodeSelection,
    selectNode,
    addToSelection,
    removeFromSelection,
    clearSelection,
    selectNodes,
    addNode,
    addNodesWithLayout,
    addEdge,
    removeNode,
    removeBC,
    clearCanvas,
    updateNodePosition,
    updateBCSize,
    findAndAddRelations,
    findCrossBCRelations,
    findAvoidingPosition,
    expandEventTriggers,
    addNodeToBC,
    syncAfterChanges,
    closeRightPanel,
    setRightPanelMode,
    toggleChatPanel,
    toggleInspectorPanel,
    rerouteEdgesForMovedNodes,
    syncBCPositionFromVueFlow,
    toggleDesignLevel,
    setShowDesignLevel
  }
})
