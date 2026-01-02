import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useCanvasStore = defineStore('canvas', () => {
  // Nodes on the canvas
  const nodes = ref([])
  const edges = ref([])

  // Selected nodes (for chat-based modification)
  const selectedNodeIds = ref(new Set())
  
  // Track BC containers and their children
  const bcContainers = ref({}) // { bcId: { nodeIds: [], bounds: {} } }
  
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
    
    const padding = 60
    const headerHeight = 50
    const nodeWidth = nodeTypeConfig[nodeType]?.width || 140
    const nodeHeight = nodeTypeConfig[nodeType]?.height || 80
    
    // Layout: Aggregates on left, Commands/Events flow to the right
    const typeOffsets = {
      Aggregate: { x: 30, baseY: headerHeight + 20 },
      Command: { x: 200, baseY: headerHeight + 20 },
      Event: { x: 380, baseY: headerHeight + 20 },
      Policy: { x: 290, baseY: headerHeight + 150 },
      // Place ReadModel roughly below the main flow
      ReadModel: { x: 180, baseY: headerHeight + 230 },
      // UI stickers default to left side (more accurate placement happens in addNodesWithLayout)
      UI: { x: 30, baseY: headerHeight + 20 }
    }
    
    const offset = typeOffsets[nodeType] || { x: 30, baseY: headerHeight + 20 }
    
    // Count existing nodes of same type in this BC
    const sameTypeInBC = nodes.value.filter(n => 
      n.parentNode === bcId && 
      n.data?.type === nodeType
    ).length
    
    return {
      x: offset.x,
      y: offset.baseY + (sameTypeInBC * (nodeHeight + 20))
    }
  }
  
  // Update BC container size based on children
  function updateBCSize(bcId) {
    const bcNode = nodes.value.find(n => n.id === bcId)
    if (!bcNode) return
    
    const children = nodes.value.filter(n => n.parentNode === bcId)
    if (children.length === 0) {
      bcNode.style = { width: '550px', height: '350px' }
      return
    }
    
    // Calculate bounds
    let minX = Infinity
    let maxX = 0
    let maxY = 0
    
    children.forEach(child => {
      const config = nodeTypeConfig[child.data?.type] || { width: 140, height: 80 }
      const left = child.position.x
      const right = child.position.x + config.width
      const bottom = child.position.y + config.height
      
      minX = Math.min(minX, left)
      maxX = Math.max(maxX, right)
      maxY = Math.max(maxY, bottom)
    })
    
    // Add padding
    const padding = 40
    const newWidth = Math.max(550, maxX + padding)
    const newHeight = Math.max(350, maxY + padding)
    
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
        
        const headerHeight = 50
        const padding = 30
        const nodeWidth = 140
        const nodeHeight = 90
        const gapX = 20
        const gapY = 20
        
        // Calculate center position for Aggregate
        const aggregateX = padding + 180  // Center column
        const commandX = padding          // Left of Aggregate
        const eventX = padding + 360      // Right of Aggregate
        const policyX = padding - 10      // Left of Command (will adjust based on invokeCommandId)
        const readModelX = padding + 180  // Base X for read models row (we'll spread horizontally)
        const uiX = padding - 120         // Default UI x (will be adjusted if attached)
        
        let currentY = headerHeight + 20
        
        // Find which command each policy invokes
        const policyCommandMap = {}
        typeGroups.Policy.forEach(pol => {
          if (pol.invokeCommandId) {
            policyCommandMap[pol.id] = pol.invokeCommandId
          }
        })
        
        // Layout Commands (left column) - track positions for policy/UI placement
        const commandPositions = {}
        typeGroups.Command.forEach((cmd, idx) => {
          if (!isOnCanvas(cmd.id)) {
            const yPos = currentY + idx * (nodeHeight + gapY)
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
        })
        
        // Layout Aggregates (center column)
        const aggStartY = currentY + (typeGroups.Command.length > 0 ? 
          Math.floor((typeGroups.Command.length - 1) / 2) * (nodeHeight + gapY) : 0)
        typeGroups.Aggregate.forEach((agg, idx) => {
          if (!isOnCanvas(agg.id)) {
            const node = {
              id: agg.id,
              type: 'aggregate',
              position: { x: aggregateX, y: aggStartY + idx * (nodeHeight + gapY) },
              data: { ...agg, label: agg.name },
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

        // Layout UI stickers (positioned to the left of their attached Command/ReadModel when possible)
        let uiFallbackY = currentY
        typeGroups.UI.forEach((ui, idx) => {
          if (!isOnCanvas(ui.id)) {
            let xPos = uiX
            let yPos = uiFallbackY

            if (ui.attachedToId) {
              if (commandPositions[ui.attachedToId]) {
                yPos = commandPositions[ui.attachedToId].y
                xPos = commandPositions[ui.attachedToId].x - 150
              } else if (readModelPositions[ui.attachedToId]) {
                yPos = readModelPositions[ui.attachedToId].y
                xPos = readModelPositions[ui.attachedToId].x - 150
              }
            } else {
              uiFallbackY += nodeHeight + gapY
            }

            const node = {
              id: ui.id,
              type: 'ui',
              position: { x: Math.max(padding, xPos), y: yPos },
              data: { ...ui, label: ui.name },
              parentNode: bcId,
              extent: 'parent'
            }
            nodes.value.push(node)
            newNodes.push(node)
          }
        })
        
        // Update BC size
        updateBCSize(bcId)
        
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
  }

  // Add a new node to an existing BC on canvas (used by chat create action)
  function addNodeToBC(nodeData, bcId) {
    if (isOnCanvas(nodeData.id)) return null

    const bcNode = nodes.value.find(n => n.id === bcId && n.type === 'boundedcontext')
    if (!bcNode) return null

    const position = calculatePositionInBC(bcId, nodeData.type, 0)
    const node = {
      id: nodeData.id,
      type: nodeData.type.toLowerCase(),
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
    updateBCSize(bcId)
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
        // Layout: Policy(왼쪽) → Command(왼쪽) → Aggregate(중앙) → Event(오른쪽)
        const headerHeight = 50
        const padding = 30
        const nodeHeight = 90
        const gapY = 20
        let currentY = headerHeight + 20
        
        const aggregateX = padding + 180
        const commandX = padding + 20
        const eventX = padding + 360
        const policyX = padding - 100
        
        // Group by type
        const typeGroups = { Aggregate: [], Command: [], Event: [], Policy: [] }
        children.forEach(child => {
          if (!isOnCanvas(child.id) && typeGroups[child.type]) {
            typeGroups[child.type].push(child)
          }
        })
        
        // Layout Commands (left) and track positions
        const commandPositions = {}
        typeGroups.Command.forEach((cmd, idx) => {
          const yPos = currentY + idx * (nodeHeight + gapY)
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
        })
        
        // Layout Aggregates (center)
        const aggStartY = currentY + (typeGroups.Command.length > 0 ? 
          Math.floor((typeGroups.Command.length - 1) / 2) * (nodeHeight + gapY) : 0)
        typeGroups.Aggregate.forEach((agg, idx) => {
          const node = {
            id: agg.id,
            type: 'aggregate',
            position: { x: aggregateX, y: aggStartY + idx * (nodeHeight + gapY) },
            data: { ...agg, label: agg.name },
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
            position: { x: Math.max(padding, xPos), y: yPos },
            data: { ...pol, label: pol.name },
            parentNode: bcId,
            extent: 'parent'
          }
          nodes.value.push(node)
          newNodes.push(node)
        })
        
        updateBCSize(bcId)
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
    isOnCanvas,
    isSelected,
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
    clearCanvas,
    updateNodePosition,
    updateBCSize,
    findAndAddRelations,
    findCrossBCRelations,
    findAvoidingPosition,
    expandEventTriggers,
    addNodeToBC,
    syncAfterChanges
  }
})
