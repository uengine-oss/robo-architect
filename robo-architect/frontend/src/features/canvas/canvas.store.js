import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useCanvasStore = defineStore('canvas', () => {
  // Nodes on the canvas
  const nodes = ref([])
  const edges = ref([])
  
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
          name: bcName || bcId.replace('BC-', ''),
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
    
    // Count existing nodes of same type in this BC
    const sameTypeInBC = nodes.value.filter(n => 
      n.parentNode === bcId && 
      n.data?.type === nodeType
    ).length
    
    return {
      x: offset.x,
      y: offset.baseY + (sameTypeInBC * (nodeHeight + 5))  // Tight spacing between stickers
    }
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
      const bottom = child.position.y + config.height
      
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
        label: nodeData.name
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
            bc: { id: parentBcId, name: parentBcId.replace('BC-', ''), type: 'BoundedContext' },
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
              label: nodeData.name
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
        
        // Fallback: derive parentId from HAS_COMMAND relationships if not already set
        // This ensures Command-Aggregate mapping works even if backend didn't include parentId
        relationships.forEach(rel => {
          if (rel.type === 'HAS_COMMAND') {
            const cmd = children.find(c => c.id === rel.target && c.type === 'Command')
            if (cmd && !cmd.parentId) {
              cmd.parentId = rel.source  // Aggregate ID
            }
          }
        })
        
        // Group Commands by their parent Aggregate
        const commandsByAggregate = {}
        typeGroups.Command.forEach(cmd => {
          const aggId = cmd.parentId
          if (aggId) {
            if (!commandsByAggregate[aggId]) commandsByAggregate[aggId] = []
            commandsByAggregate[aggId].push(cmd)
          }
        })
        
        // Layout Commands (left column) - track positions for policy/UI placement
        // Commands are now laid out grouped by their parent Aggregate
        const commandPositions = {}
        let commandIdx = 0
        const aggregatePositions = {} // Track Y range for each aggregate
        
        typeGroups.Aggregate.forEach(agg => {
          const aggCommands = commandsByAggregate[agg.id] || []
          const startIdx = commandIdx
          
          aggCommands.forEach((cmd) => {
            if (!isOnCanvas(cmd.id)) {
              const yPos = currentY + commandIdx * (nodeHeight + gapY)
              commandPositions[cmd.id] = { x: commandX, y: yPos }
              const node = {
                id: cmd.id,
                type: 'command',
                position: { x: commandX, y: yPos },
                data: { ...cmd, label: cmd.name },
                parentNode: bcId,
                extent: 'parent'
              }
              nodes.value.push(node)
              newNodes.push(node)
            }
            commandIdx++
          })
          
          // Track the Y range for this aggregate
          if (aggCommands.length > 0) {
            const startY = currentY + startIdx * (nodeHeight + gapY)
            const endY = currentY + (commandIdx - 1) * (nodeHeight + gapY) + nodeHeight
            aggregatePositions[agg.id] = { startY, endY, commandCount: aggCommands.length }
          }
        })
        
        // Also layout any orphan commands (without parentId)
        const orphanCommands = typeGroups.Command.filter(cmd => !cmd.parentId)
        orphanCommands.forEach(cmd => {
          if (!isOnCanvas(cmd.id)) {
            const yPos = currentY + commandIdx * (nodeHeight + gapY)
            commandPositions[cmd.id] = { x: commandX, y: yPos }
            const node = {
              id: cmd.id,
              type: 'command',
              position: { x: commandX, y: yPos },
              data: { ...cmd, label: cmd.name },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            commandIdx++
          }
        })
        
        // Layout Aggregates (center column) - height spans all its Commands
        const defaultAggHeight = nodeTypeConfig.Aggregate?.height || 80
        typeGroups.Aggregate.forEach((agg, idx) => {
          if (!isOnCanvas(agg.id)) {
            const aggPos = aggregatePositions[agg.id]
            let aggY = currentY
            let aggHeight = defaultAggHeight
            
            if (aggPos && aggPos.commandCount > 0) {
              // Position aggregate at the same Y as its first command
              aggY = aggPos.startY
              // Calculate height to span all commands (from first to last command bottom)
              aggHeight = aggPos.endY - aggPos.startY
              // Ensure minimum height
              aggHeight = Math.max(aggHeight, defaultAggHeight)
            } else {
              // No commands for this aggregate - use default positioning
              aggY = currentY + idx * (nodeHeight + gapY)
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
          }
        })
        
        // Layout Events (right column) - align with commands
        typeGroups.Event.forEach((evt, idx) => {
          if (!isOnCanvas(evt.id)) {
            const node = {
              id: evt.id,
              type: 'event',
              position: { x: eventX, y: currentY + idx * (nodeHeight + gapY) },
              data: { ...evt, label: evt.name },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
          }
        })
        
        // Layout Policies (left of their invoking command)
        let policyOffsetY = 0
        typeGroups.Policy.forEach((pol, idx) => {
          if (!isOnCanvas(pol.id)) {
            // Find the command this policy invokes
            const invokedCmdId = pol.invokeCommandId
            let yPos = currentY + policyOffsetY
            
            if (invokedCmdId && commandPositions[invokedCmdId]) {
              // Place policy at same Y as the command it invokes
              yPos = commandPositions[invokedCmdId].y
            } else {
              // Default: stack below existing content
              const maxY = Math.max(
                typeGroups.Command.length,
                typeGroups.Event.length
              ) * (nodeHeight + gapY) + currentY
              yPos = maxY + policyOffsetY
              policyOffsetY += nodeHeight + gapY
            }
            
            const node = {
              id: pol.id,
              type: 'policy',
              position: { x: policyX, y: yPos },
              data: { ...pol, label: pol.name },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
          }
        })

        // Layout ReadModels (bottom row, spanning horizontally)
        const readModelPositions = {}
        const baseRowsHeight = Math.max(typeGroups.Command.length, typeGroups.Event.length, typeGroups.Aggregate.length, 1)
        const readModelY = currentY + baseRowsHeight * (nodeHeight + gapY) + 40

        typeGroups.ReadModel.forEach((rm, idx) => {
          if (!isOnCanvas(rm.id)) {
            const xPos = readModelX + idx * (nodeWidth + gapX)
            const yPos = readModelY
            readModelPositions[rm.id] = { x: xPos, y: yPos }
            const node = {
              id: rm.id,
              type: 'readmodel',
              position: { x: xPos, y: yPos },
              data: { ...rm, label: rm.name },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
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

            if (ui.attachedToId) {
              if (commandPositions[ui.attachedToId]) {
                yPos = commandPositions[ui.attachedToId].y
                xPos = commandPositions[ui.attachedToId].x - uiWidth - 5  // Tight gap between UI and Command
              } else if (readModelPositions[ui.attachedToId]) {
                yPos = readModelPositions[ui.attachedToId].y
                xPos = readModelPositions[ui.attachedToId].x - uiWidth - 5  // Tight gap between UI and ReadModel
              }
            } else {
              uiFallbackY += nodeHeight + gapY
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
          const node = {
            id: ui.id,
            type: 'ui',
            position: { x: Math.max(leftPadding, xPos), y: yPos },
            data: { ...ui, label: ui.name },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
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
    
    const edge = {
      id: edgeId,
      source: sourceId,
      target: targetId,
      type: 'smoothstep',
      animated: edgeType === 'TRIGGERS',
      style: getEdgeStyle(edgeType),
      label: getEdgeLabel(edgeType),
      labelStyle: { fill: '#c1c2c5', fontSize: 10, fontWeight: 500 },
      labelBgStyle: { fill: '#1e1e2e', fillOpacity: 0.9 },
      labelBgPadding: [4, 4]
    }
    
    edges.value.push(edge)
    // Ensure consumers relying on reference changes (e.g. Vue Flow) observe updates.
    edges.value = [...edges.value]
    return edge
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
        bcId
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
        if (sourceId && isOnCanvas(sourceId) && isOnCanvas(targetId)) {
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
      const nodeHeight = n.type === 'boundedcontext' ? 
        parseInt(n.style?.height || '300') : config.height
      
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
      
      if (data.nodes.length === 0) {
        console.log('Event has no triggers:', eventId)
        return []
      }
      
      // Find the source event node to position new nodes relative to it
      const sourceEventNode = nodes.value.find(n => n.id === eventId)
      if (!sourceEventNode) return []
      
      const startX = sourceEventNode.position.x + 200
      const startY = sourceEventNode.position.y
      
      const newNodes = []
      const bcMap = {}
      
      // Group nodes by BC
      data.nodes.forEach(nodeData => {
        if (nodeData.type === 'BoundedContext') {
          if (!isOnCanvas(nodeData.id)) {
            bcMap[nodeData.id] = {
              bc: nodeData,
              children: []
            }
          }
        }
      })
      
      data.nodes.forEach(nodeData => {
        if (nodeData.type !== 'BoundedContext' && nodeData.bcId) {
          if (bcMap[nodeData.bcId]) {
            bcMap[nodeData.bcId].children.push(nodeData)
          }
        }
      })
      
      // Place each BC with obstacle avoidance
      let bcOffsetY = 0
      for (const [bcId, { bc, children }] of Object.entries(bcMap)) {
        // Calculate BC size based on children
        const numChildren = children.length
        const bcWidth = 550
        const bcHeight = Math.max(300, 80 + Math.ceil(numChildren / 3) * 100 + 80)
        
        // Find position avoiding obstacles
        const bcPosition = findAvoidingPosition(
          startX,
          startY + bcOffsetY,
          bcWidth,
          bcHeight
        )
        
        // Create BC container
        const bcNode = {
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
        
        // Group by type
        const typeGroups = { Aggregate: [], Command: [], Event: [], Policy: [] }
        children.forEach(child => {
          if (!isOnCanvas(child.id) && typeGroups[child.type]) {
            typeGroups[child.type].push(child)
          }
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
          const aggId = cmd.parentId
          if (aggId) {
            if (!commandsByAggregate[aggId]) commandsByAggregate[aggId] = []
            commandsByAggregate[aggId].push(cmd)
          }
        })
        
        // Layout Commands (left) grouped by parent Aggregate and track positions
        const commandPositions = {}
        let commandIdx = 0
        const aggregatePositions = {} // Track Y range for each aggregate
        
        typeGroups.Aggregate.forEach(agg => {
          const aggCommands = commandsByAggregate[agg.id] || []
          const startIdx = commandIdx
          
          aggCommands.forEach((cmd) => {
            const yPos = currentY + commandIdx * (nodeHeight + gapY)
            commandPositions[cmd.id] = { x: commandX, y: yPos }
            const node = {
              id: cmd.id,
              type: 'command',
              position: { x: commandX, y: yPos },
              data: { ...cmd, label: cmd.name },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
            commandIdx++
          })
          
          // Track the Y range for this aggregate
          if (aggCommands.length > 0) {
            const startY = currentY + startIdx * (nodeHeight + gapY)
            const endY = currentY + (commandIdx - 1) * (nodeHeight + gapY) + nodeHeight
            aggregatePositions[agg.id] = { startY, endY, commandCount: aggCommands.length }
          }
        })
        
        // Also layout any orphan commands (without parentId)
        const orphanCommands = typeGroups.Command.filter(cmd => !cmd.parentId)
        orphanCommands.forEach(cmd => {
          const yPos = currentY + commandIdx * (nodeHeight + gapY)
          commandPositions[cmd.id] = { x: commandX, y: yPos }
          const node = {
            id: cmd.id,
            type: 'command',
            position: { x: commandX, y: yPos },
            data: { ...cmd, label: cmd.name },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
          commandIdx++
        })
        
        // Layout Aggregates (center) - height spans all its Commands
        const defaultAggHeight = nodeTypeConfig.Aggregate?.height || 80
        typeGroups.Aggregate.forEach((agg, idx) => {
          const aggPos = aggregatePositions[agg.id]
          let aggY = currentY
          let aggHeight = defaultAggHeight
          
          if (aggPos && aggPos.commandCount > 0) {
            // Position aggregate at the same Y as its first command
            aggY = aggPos.startY
            // Calculate height to span all commands (from first to last command bottom)
            aggHeight = aggPos.endY - aggPos.startY
            // Ensure minimum height
            aggHeight = Math.max(aggHeight, defaultAggHeight)
          } else {
            // No commands for this aggregate - use default positioning
            aggY = currentY + idx * (nodeHeight + gapY)
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
        })
        
        // Layout Events (right)
        typeGroups.Event.forEach((evt, idx) => {
          const node = {
            id: evt.id,
            type: 'event',
            position: { x: eventX, y: currentY + idx * (nodeHeight + gapY) },
            data: { ...evt, label: evt.name },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
        })
        
        // Layout Policies (left of their invoking command)
        let policyOffsetY = 0
        typeGroups.Policy.forEach((pol, idx) => {
          const invokedCmdId = pol.invokeCommandId
          let yPos = currentY + policyOffsetY
          let xPos = policyX
          
          if (invokedCmdId && commandPositions[invokedCmdId]) {
            yPos = commandPositions[invokedCmdId].y
            xPos = commandPositions[invokedCmdId].x - 150
          } else {
            const maxY = Math.max(
              typeGroups.Command.length,
              typeGroups.Event.length,
              1
            ) * (nodeHeight + gapY) + currentY
            yPos = maxY + policyOffsetY
            policyOffsetY += nodeHeight + gapY
          }
          
          const node = {
            id: pol.id,
            type: 'policy',
            position: { x: Math.max(leftPadding, xPos), y: yPos },
            data: { ...pol, label: pol.name },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
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
    toggleInspectorPanel
  }
})
