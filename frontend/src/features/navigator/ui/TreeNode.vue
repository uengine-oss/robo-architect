<script setup>
import { computed, ref, onMounted, inject } from 'vue'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useAggregateViewerStore } from '@/features/canvas/aggregateViewer.store'
import { useBigPictureStore } from '@/features/canvas/bigpicture.store'
import { useInspectorRequestStore } from '@/features/canvas/inspectorRequest.store'
import { useModelModifierStore } from '@/features/modelModifier/modelModifier.store'
import { useIngestionStore } from '@/features/requirementsIngestion/ingestion.store'
import { useTerminologyStore } from '@/features/terminology/terminology.store'
import { useBpmnStore } from '@/features/canvas/bpmn.store'
import { useEventModelingStore } from '@/features/eventModeling/eventModeling.store'
import { useInvariantsStore } from '@/features/invariants/invariants.store'

const props = defineProps({
  node: {
    type: Object,
    required: true
  },
  tree: {
    type: Object,
    default: null
  },
  depth: {
    type: Number,
    default: 0
  }
})

const navigatorStore = useNavigatorStore()
const canvasStore = useCanvasStore()
const aggregateViewerStore = useAggregateViewerStore()
const bigPictureStore = useBigPictureStore()
const inspectorRequest = useInspectorRequestStore()
const chatStore = useModelModifierStore()
const ingestionStore = useIngestionStore()
const terminologyStore = useTerminologyStore()
const bpmnStore = useBpmnStore()
const eventModelingStore = useEventModelingStore()
const invariantsStore = useInvariantsStore()

// Event Modeling 캔버스에 표시된 BC IDs (reactive)
const eventModelingBcIds = computed(() =>
  new Set(eventModelingStore.systemSwimlanes.map(lane => lane.bcId))
)

// Inject activeTab from App.vue
const activeTab = inject('activeTab', ref('Design'))

const isDragging = ref(false)
const showEntrance = ref(false)

// Entrance animation for new items
onMounted(() => {
  if (navigatorStore.isNewlyAdded(props.node.id)) {
    showEntrance.value = true
    setTimeout(() => {
      showEntrance.value = false
    }, 2000)
  }
})

// Check if node is newly added
const isNewlyAdded = computed(() => navigatorStore.isNewlyAdded(props.node.id))

// Get node type icon
const nodeIcon = computed(() => {
  const icons = {
    UserStory: 'US',
    BoundedContext: 'BC',
    Aggregate: 'A',
    Command: 'C',
    Event: 'E',
    Policy: 'P',
    ReadModel: 'RM',
    UI: 'UI',
    CQRSOperation: '⚡',
    Property: '{ }',
    InvariantGroup: 'INV',
    Invariant: 'I',
    ImplementationFile: '📄',
    // 029 — designed sub-objects under the aggregate
    ValueObject: 'VO',
    Enumeration: 'EN',
    DomainException: 'EX',
    // 029 — group folder wrapping the BC's user stories
    UserStoryGroup: 'US',
    // 029 — group folder wrapping the aggregate's / read-model's properties
    PropertyGroup: '{ }'
  }
  // feature 029: ImplementationFile gets a language-specific icon
  // derived from the file extension so the developer can tell a .ts
  // from a .py from a .java at a glance.
  if (props.node.type === 'ImplementationFile') {
    const path = props.node.path || ''
    const ext = path.split('.').pop()?.toLowerCase()
    const fileIcons = {
      ts: 'TS', tsx: 'TSX',
      js: 'JS', jsx: 'JSX', mjs: 'JS', cjs: 'JS',
      py: 'PY',
      java: 'JV', kt: 'KT',
      go: 'GO',
      rb: 'RB', php: 'PHP',
      cs: 'C#', rs: 'RS',
      json: '{}', yaml: 'YML', yml: 'YML', md: 'MD',
      sql: 'SQL',
    }
    return fileIcons[ext] || '📄'
  }
  return icons[props.node.type] || '?'
})

// Format user story display name
const displayName = computed(() => {
  if (props.node.type === 'UserStory') {
    const role = props.node.role || 'user'
    const action = props.node.action || ''
    return `${role}: ${action.substring(0, 30)}${action.length > 30 ? '...' : ''}`
  }
  if (props.node.type === 'BoundedContext') {
    const label = terminologyStore.getLabel(props.node)
    const domainType = props.node.domainType || props.node.domain_type || props.node.domainType
    if (domainType) {
      const typeMap = {
        'Core Domain': 'core',
        'Supporting Domain': 'supporting',
        'Generic Domain': 'generic'
      }
      const shortLabel = typeMap[domainType] || domainType.toLowerCase().replace(' domain', '')
      return `${label} (${shortLabel})`
    }
    return label
  }
  if (props.node.type === 'CQRSOperation') {
    const opType = props.node.operationType || props.node.operation_type || 'OP'
    const trigger = props.node.triggerEventName || props.node.triggerEventId || props.node.trigger_event_id || ''
    return trigger ? `${opType} ← ${trigger}` : `${opType}`
  }
  if (props.node.type === 'Property') {
    const name = terminologyStore.getLabel(props.node) || props.node.id || 'property'
    const t = props.node.dataType || props.node.typeName || props.node.data_type || props.node.propType || ''
    return t ? `${name}: ${t}` : name
  }
  if (props.node.type === 'InvariantGroup') {
    return 'Invariants'
  }
  if (props.node.type === 'UserStoryGroup') {
    const count = (props.node.items || []).length
    return count > 0 ? `User Stories (${count})` : 'User Stories'
  }
  if (props.node.type === 'PropertyGroup') {
    const count = (props.node.items || []).length
    return count > 0 ? `Properties (${count})` : 'Properties'
  }
  if (props.node.type === 'Invariant') {
    const text = props.node.declaration || props.node.name || 'invariant'
    return `${text.substring(0, 40)}${text.length > 40 ? '...' : ''}`
  }
  if (props.node.type === 'ImplementationFile') {
    // Show just the basename + role tag — full path lives in the title attr
    const path = props.node.path || ''
    const basename = path.split('/').pop() || path
    const role = props.node.role
    return role && role !== 'primary' ? `${basename}  (${role})` : basename
  }
  if (props.node.type === 'ValueObject' || props.node.type === 'Enumeration' || props.node.type === 'DomainException') {
    // VO / Enum / Exception come from /full-tree as plain dicts (no id).
    // Prefer displayName when ubiquitous-language mode is on; otherwise name.
    const label = props.node.displayName || props.node.name || props.node.alias || props.node.id || ''
    return terminologyStore.ubiquitousLanguageMode ? (props.node.displayName || label) : label
  }
  return terminologyStore.getLabel(props.node)
})

// Get children based on node type
const children = computed(() => {
  const type = props.node.type
  
  if (type === 'BoundedContext') {
    if (!props.tree) return []

    // User Stories under this BC come first — wrapped in a "User Stories"
    // group folder so the BC root stays compact and the design objects
    // (Aggregate / Policy / ReadModel / UI) read at the same depth.
    const userStories = (props.tree.userStories || []).map(us => ({
      ...us,
      type: 'UserStory',
      name: us.name || `${us.role}: ${us.action?.substring(0, 25)}...`
    }))
    const userStoryGroup = userStories.length > 0 ? {
      id: `${props.node.id}::userstories`,
      type: 'UserStoryGroup',
      name: 'User Stories',
      bcId: props.node.id,
      items: userStories,
    } : null

    const aggregates = (props.tree.aggregates || []).map(a => ({
      ...a,
      type: 'Aggregate'
    }))
    const policies = (props.tree.policies || []).map(p => ({
      ...p,
      type: 'Policy'
    }))
    const readmodels = (props.tree.readmodels || []).map(rm => ({
      ...rm,
      type: 'ReadModel'
    }))
    const uis = (props.tree.uis || []).map(ui => ({
      ...ui,
      type: 'UI'
    }))
    return [
      ...(userStoryGroup ? [userStoryGroup] : []),
      ...aggregates,
      ...policies,
      ...readmodels,
      ...uis,
    ]
  }

  if (type === 'UserStoryGroup') {
    return props.node.items || []
  }
  
  if (type === 'Aggregate') {
    const commands = (props.node.commands || []).map(c => ({
      ...c,
      type: 'Command'
    }))
    const events = (props.node.events || []).map(e => ({
      ...e,
      type: 'Event'
    }))
    // 029 — the user wants ALL designed sub-objects under the aggregate,
    // each followed by the implementation files registered for them.
    // VO / Enumeration / Exception don't have graph ids in the current
    // schema, so they appear in the tree but can't (yet) link to files;
    // properties live as their own leaves.
    const valueObjects = (props.node.valueObjects || []).map(v => ({
      ...v,
      id: `${props.node.id}::vo::${v.name}`,
      type: 'ValueObject',
      aggregateId: props.node.id
    }))
    const enumerations = (props.node.enumerations || []).map(e => ({
      ...e,
      id: `${props.node.id}::enum::${e.name}`,
      type: 'Enumeration',
      aggregateId: props.node.id
    }))
    const exceptions = (props.node.exceptions || []).map(x => ({
      ...x,
      id: `${props.node.id}::exc::${x.name || x.id || ''}`,
      type: 'DomainException',
      aggregateId: props.node.id
    }))
    // 029 — wrap the 9+ properties under a "Properties (N)" folder so the
    // aggregate root stays compact (matches the User Stories pattern).
    const aggProps = (props.node.properties || []).map(p => ({
      ...p,
      dataType: p.dataType || (p.type && p.type !== 'Property' ? p.type : p.data_type),
      type: 'Property'
    }))
    const propertyGroup = aggProps.length > 0 ? {
      id: `${props.node.id}::properties`,
      type: 'PropertyGroup',
      name: 'Properties',
      parentId: props.node.id,
      items: aggProps,
    } : null
    // Invariants (027) — a drill-down group below the Aggregate's other
    // design objects. Always present so a planner can add the first one.
    const invariantGroup = {
      id: `${props.node.id}::invariants`,
      type: 'InvariantGroup',
      name: 'Invariants',
      aggregateId: props.node.id
    }
    // feature 029: implementation files [:IMPLEMENTED_IN] also drill-down
    const files = (props.node.implementationFiles || []).map(f => ({
      ...f,
      id: `${props.node.id}::file::${f.path}`,
      // basename so the inspector header doesn't show the long pseudo-id.
      name: (f.path || '').split('/').pop() || f.path,
      type: 'ImplementationFile',
      elementId: props.node.id,
      elementKind: 'Aggregate',
      elementName: props.node.name
    }))
    return [
      ...(propertyGroup ? [propertyGroup] : []),
      ...commands,
      ...events,
      ...valueObjects,
      ...enumerations,
      ...exceptions,
      invariantGroup,
      ...files,
    ]
  }

  if (type === 'PropertyGroup') {
    return props.node.items || []
  }

  // 029 — VO/Enum/Exception leaves. They currently have no implementation
  // files in the graph (no [:IMPLEMENTED_IN] because the schema doesn't
  // give them ids), so they have no expandable children. Once the backend
  // mints ids for these elements, we can attach files exactly like Events.
  if (type === 'ValueObject' || type === 'Enumeration' || type === 'DomainException') {
    const files = (props.node.implementationFiles || []).map(f => ({
      ...f,
      id: `${props.node.id}::file::${f.path}`,
      name: (f.path || '').split('/').pop() || f.path,
      type: 'ImplementationFile',
      elementId: props.node.id,
      elementKind: type,
      elementName: props.node.name
    }))
    return files
  }

  if (type === 'InvariantGroup') {
    const aggId = props.node.aggregateId
    return invariantsStore.itemsFor(aggId).map(inv => ({
      ...inv,
      type: 'Invariant',
      aggregateId: aggId
    }))
  }

  if (type === 'Invariant') {
    return []
  }

  if (type === 'Command') {
    const events = (props.node.events || []).map(e => ({
      ...e,
      type: 'Event'
    }))
    const files = (props.node.implementationFiles || []).map(f => ({
      ...f,
      id: `${props.node.id}::file::${f.path}`,
      name: (f.path || '').split('/').pop() || f.path,
      type: 'ImplementationFile',
      elementId: props.node.id,
      elementKind: 'Command',
      elementName: props.node.name
    }))
    return [...events, ...files]
  }

  if (type === 'Event') {
    const files = (props.node.implementationFiles || []).map(f => ({
      ...f,
      id: `${props.node.id}::file::${f.path}`,
      name: (f.path || '').split('/').pop() || f.path,
      type: 'ImplementationFile',
      elementId: props.node.id,
      elementKind: 'Event',
      elementName: props.node.name
    }))
    return files
  }

  if (type === 'ReadModel') {
    const ops = (props.node.operations || props.node.cqrsOperations || []).map(op => ({
      ...op,
      type: 'CQRSOperation',
      name: op.name || op.operationType || op.operation_type || op.id
    }))
    const propsList = (props.node.properties || []).map(p => ({
      ...p,
      dataType: p.dataType || (p.type && p.type !== 'Property' ? p.type : p.data_type),
      type: 'Property'
    }))
    const propertyGroup = propsList.length > 0 ? {
      id: `${props.node.id}::properties`,
      type: 'PropertyGroup',
      name: 'Properties',
      parentId: props.node.id,
      items: propsList,
    } : null
    const files = (props.node.implementationFiles || []).map(f => ({
      ...f,
      id: `${props.node.id}::file::${f.path}`,
      name: (f.path || '').split('/').pop() || f.path,
      type: 'ImplementationFile',
      elementId: props.node.id,
      elementKind: 'ReadModel',
      elementName: props.node.name
    }))
    return [...ops, ...(propertyGroup ? [propertyGroup] : []), ...files]
  }

  if (type === 'ImplementationFile') {
    return []  // leaf
  }
  
  // UserStory has no children
  if (type === 'UserStory') {
    return []
  }
  
  return []
})

const hasChildren = computed(() => {
  // The Invariants group is always expandable (lazy-loaded on expand).
  if (props.node.type === 'InvariantGroup') return true
  return children.value.length > 0
})

const isExpanded = computed(() => navigatorStore.isExpanded(props.node.id))

// Check if node is on the currently active viewer's canvas
// Only check the active viewer to ensure proper synchronization
const isOnCanvas = computed(() => {
  const nodeId = props.node.id
  const nodeType = props.node.type
  const currentTab = activeTab.value
  
  // For BoundedContext, check only the active viewer
  if (nodeType === 'BoundedContext') {
    if (currentTab === 'Event Modeling') {
      return eventModelingBcIds.value.has(nodeId)
    } else if (currentTab === 'Design') {
      return canvasStore.nodeIds.includes(nodeId)
    } else if (currentTab === 'Aggregate') {
      const selectedBcIdsArray = Array.from(aggregateViewerStore.selectedBcIds)
      return selectedBcIdsArray.includes(nodeId)
    } else if (currentTab === 'Big picture') {
      const swimlanes = bigPictureStore.swimlanes
      return swimlanes.some(lane => lane.bcId === nodeId)
    }
    return canvasStore.nodeIds.includes(nodeId)
  }
  
  // For other node types, check Design Viewer (default behavior)
  if (currentTab === 'Design') {
    return canvasStore.nodeIds.includes(nodeId)
  }
  // Other viewers don't show non-BC nodes in navigator
  return false
})

function toggleExpand(event) {
  // If Ctrl/Cmd is pressed, add to chat selection instead of toggling expand
  // This works both during normal operation and during ingestion pause
  if (event.ctrlKey || event.metaKey) {
    event.preventDefault()
    event.stopPropagation()
    addToChatSelection()
    return
  }

  // 029 — ImplementationFile leaf: open the source in the right-side
  // InspectorPanel via the inspectorRequest bridge. No expand to toggle.
  if (props.node.type === 'ImplementationFile') {
    if (activeTab && activeTab.value !== 'Design') {
      activeTab.value = 'Design'
    }
    inspectorRequest.request(props.node)
    return
  }

  // Normal click: toggle expand/collapse (works in all states including pause)
  navigatorStore.toggleExpanded(props.node.id)

  // Lazy-load invariants when the Invariants group is opened (027). The first
  // load also triggers the backend's legacy-text migration.
  if (props.node.type === 'InvariantGroup' && navigatorStore.isExpanded(props.node.id)) {
    invariantsStore.ensureLoaded(props.node.aggregateId)
  }
}

// Create a new Invariant under an Aggregate from the Invariants group header.
async function addInvariant(event) {
  event.stopPropagation()
  const aggId = props.node.aggregateId
  const declaration = (window.prompt('새 인베리언트 선언문을 입력하세요') || '').trim()
  if (!declaration) return
  try {
    await invariantsStore.create(aggId, declaration)
    if (!navigatorStore.isExpanded(props.node.id)) {
      navigatorStore.toggleExpanded(props.node.id)
    }
  } catch (e) {
    console.error('Failed to create invariant:', e)
    window.alert(`인베리언트 생성 실패: ${e.message || e}`)
  }
}

// Add node to chat selection
function addToChatSelection() {
  // Skip nodes that are not modifiable via chat.
  if (['UserStory', 'Invariant', 'InvariantGroup'].includes(props.node.type)) {
    return
  }
  
  // Convert navigator node format to chat selection format
  const selectedNode = {
    id: props.node.id,
    name: props.node.name || props.node.id,
    type: props.node.type,
    description: props.node.description,
    bcId: props.node.bcId,
    bcName: props.node.bcName,
    aggregateId: props.node.aggregateId,
    ...props.node
  }
  
  // Add to selection (check if already selected)
  const currentNodes = chatStore.currentSelectedNodes
  const isAlreadySelected = currentNodes.some(n => (n.id || n.data?.id) === selectedNode.id)
  
  if (!isAlreadySelected) {
    // Add to selection based on viewer
    if (chatStore.selectedNodes.length > 0) {
      // Other viewer (Big Picture, Aggregate)
      chatStore.setSelectedNodes([...chatStore.selectedNodes, selectedNode])
    } else {
      // Design viewer - add to canvas selection if node exists on canvas
      const existingNode = canvasStore.nodes.find(n => n.id === selectedNode.id)
      if (existingNode) {
        canvasStore.addToSelection(selectedNode.id)
      } else {
        // Node not on canvas, add to chat selection directly
        chatStore.setSelectedNodes([selectedNode])
      }
    }
  }
}

// Double click handler — UserStory opens in the unified InspectorPanel
// (spec 019-userstory-properties-panel); other types add to canvas.
async function handleDoubleClick() {
  if (props.node.type === 'UserStory') {
    if (activeTab && activeTab.value !== 'Design') {
      activeTab.value = 'Design'
    }
    inspectorRequest.request(props.node)
  } else if (props.node.type === 'Invariant') {
    // 027 — open the Invariant in the right-side property panel (InspectorPanel).
    if (activeTab && activeTab.value !== 'Design') {
      activeTab.value = 'Design'
    }
    inspectorRequest.request(props.node)
  } else if (props.node.type === 'InvariantGroup') {
    // Group node — single click already toggles; nothing extra to do.
  } else if (
    // 029 — these nodes use synthetic ids (no graph node behind them),
    // so /expand-with-bc has nothing to fetch. Don't try to add to canvas.
    props.node.type === 'ImplementationFile' ||
    props.node.type === 'ValueObject' ||
    props.node.type === 'Enumeration' ||
    props.node.type === 'DomainException' ||
    props.node.type === 'UserStoryGroup' ||
    props.node.type === 'PropertyGroup'
  ) {
    // no-op
  } else {
    await addToCanvas()
  }
}

// Drag handlers
function handleDragStart(event) {
  // Invariants are never placed on the canvas (027) — block their drag.
  // 029 — also block the synthetic UserStoryGroup wrapper and the per-element
  // ImplementationFile / VO / Enum / Exception leaves (no graph node behind them).
  if ([
    'Invariant', 'InvariantGroup',
    'UserStoryGroup', 'PropertyGroup',
    'ImplementationFile', 'ValueObject', 'Enumeration', 'DomainException',
  ].includes(props.node.type)) {
    event.preventDefault()
    return
  }
  isDragging.value = true
  // Include both formats for compatibility
  event.dataTransfer.setData('application/json', JSON.stringify({
    id: props.node.id,
    type: props.node.type,
    nodeId: props.node.id,
    nodeType: props.node.type,
    nodeData: props.node
  }))
  event.dataTransfer.effectAllowed = 'copy'
}

function handleDragEnd() {
  isDragging.value = false
}

// Add node to canvas with expanded data (including BC container)
async function addToCanvas() {
  const currentTab = activeTab.value
  
  // Check if already on the active viewer's canvas
  if (isOnCanvas.value) return
  
  // For BoundedContext, check which viewer to add to based on activeTab
  if (props.node.type === 'BoundedContext') {
    if (currentTab === 'Event Modeling') {
      return  // Event Modeling은 프로세스 단위로 추가
    } else if (currentTab === 'Aggregate') {
      await aggregateViewerStore.fetchAggregatesForBC(props.node.id)
      return
    } else if (currentTab === 'Big picture') {
      await bigPictureStore.addBCWithOutboundFlow(props.node.id)
      return
    }
  }
  
  // For other node types or BC when Design Viewer is active, add to Design Viewer
  try {
    // Use the new API that includes BC context
    const response = await fetch(`/api/graph/expand-with-bc/${props.node.id}`)
    const data = await response.json()
    
    // Track which nodes are being added
    const newNodeIds = data.nodes.map(n => n.id)
    
    canvasStore.addNodesWithLayout(data.nodes, data.relationships, data.bcContext)
    
    // Find cross-BC relations (Event → TRIGGERS → Policy)
    await canvasStore.findCrossBCRelations(newNodeIds)
    
    // Also find any other relations
    await canvasStore.findAndAddRelations()
  } catch (error) {
    console.error('Failed to expand node:', error)
    // Fallback: add just this node
    canvasStore.addNode(props.node)
  }
}
</script>

<template>
  <div class="tree-node" :class="{ 'is-new': isNewlyAdded }">
    <div 
      class="tree-node__header"
      :class="{ 'is-dragging': isDragging, 'is-on-canvas': isOnCanvas, 'is-newly-added': isNewlyAdded }"
      :style="{ paddingLeft: `${depth * 10}px` }"
      :draggable="true"
      @click="toggleExpand"
      @dblclick="handleDoubleClick"
      @dragstart="handleDragStart"
      @dragend="handleDragEnd"
    >
      <!-- Toggle Arrow -->
      <span 
        class="tree-node__toggle"
        :class="{ 'is-expanded': isExpanded, 'is-hidden': !hasChildren }"
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
      </span>
      
      <!-- Type Icon -->
      <span 
        class="tree-node__icon"
        :class="`tree-node__icon--${node.type.toLowerCase()}`"
      >
        {{ nodeIcon }}
      </span>
      
      <!-- Label -->
      <span 
        class="tree-node__label" 
        :title="node.type === 'UserStory' 
          ? `As a ${node.role || 'user'}, I want to ${node.action || '...'}${node.benefit ? ', so that ' + node.benefit : ''}\n\n(Double-click to edit)`
          : node.description"
      >
        {{ displayName }}
      </span>
      
      <!-- Policy trigger info -->
      <span v-if="node.type === 'Policy' && node.triggerEventId" class="tree-node__trigger">
        ← {{ node.triggerEventId.replace(/^EVT-/, '').replace(/-/g, ' ').toLowerCase() }}
      </span>
      
      <!-- Badge for children count -->
      <span v-if="hasChildren && !isExpanded" class="tree-node__badge">
        {{ children.length }}
      </span>
      
      <!-- Add button for the Invariants group (027) -->
      <button
        v-if="node.type === 'InvariantGroup'"
        class="tree-node__edit-btn"
        title="인베리언트 추가"
        @click.stop="addInvariant"
      >
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
      </button>

      <!-- Edit button for user stories -->
      <button
        v-if="node.type === 'UserStory'"
        class="tree-node__edit-btn"
        title="Edit User Story (Double-click)"
        @click.stop="handleDoubleClick"
      >
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
        </svg>
      </button>
      
      <!-- On canvas indicator -->
      <span v-if="isOnCanvas" class="tree-node__on-canvas">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"></polyline>
        </svg>
      </span>
    </div>
    
    <!-- Children -->
    <div v-if="isExpanded && hasChildren" class="tree-node__children">
      <TreeNode
        v-for="child in children"
        :key="child.id"
        :node="child"
        :tree="null"
        :depth="depth + 1"
      />
    </div>
  </div>
</template>

<style scoped>
.tree-node.is-new {
  animation: slideInNode 0.4s ease-out;
}

@keyframes slideInNode {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.tree-node__header.is-on-canvas {
  background: rgba(34, 139, 230, 0.1);
}

.tree-node__header.is-on-canvas:hover {
  background: rgba(34, 139, 230, 0.15);
}

.tree-node__header.is-newly-added {
  animation: pulseGlow 1.5s ease-in-out 2;
  position: relative;
}

.tree-node__header.is-newly-added::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, var(--color-accent), var(--color-event));
  border-radius: 2px;
  animation: slideDown 0.5s ease-out;
}

@keyframes pulseGlow {
  0%, 100% {
    background: transparent;
  }
  50% {
    background: rgba(34, 139, 230, 0.15);
  }
}

@keyframes slideDown {
  from {
    transform: scaleY(0);
    opacity: 0;
  }
  to {
    transform: scaleY(1);
    opacity: 1;
  }
}

.tree-node__on-canvas {
  color: var(--color-accent);
  display: flex;
  align-items: center;
}

.tree-node__trigger {
  font-size: 0.55rem;
  color: var(--color-text-light);
  opacity: 0.7;
  font-style: italic;
  margin-left: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
}

/* Edit button for user stories */
.tree-node__edit-btn {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: var(--radius-sm);
  color: var(--color-text-light);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.tree-node__header:hover .tree-node__edit-btn {
  opacity: 1;
}

.tree-node__edit-btn:hover {
  background: rgba(32, 201, 151, 0.2);
  color: #20c997;
}

/* User story specific styling */
.tree-node__header:has(.tree-node__icon--userstory) {
  border-left: 2px solid transparent;
  transition: border-color 0.15s;
}

.tree-node__header:has(.tree-node__icon--userstory):hover {
  border-left-color: #20c997;
}
</style>

