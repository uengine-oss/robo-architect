<script setup>
import { computed, ref, onMounted, inject } from 'vue'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useCanvasStore } from '@/features/canvas/canvas.store'
import { useAggregateViewerStore } from '@/features/canvas/aggregateViewer.store'
import { useBigPictureStore } from '@/features/canvas/bigpicture.store'
import { useUserStoryEditorStore } from '@/features/userStories/userStoryEditor.store'
import { useModelModifierStore } from '@/features/modelModifier/modelModifier.store'
import { useIngestionStore } from '@/features/requirementsIngestion/ingestion.store'
import { useTerminologyStore } from '@/features/terminology/terminology.store'

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
const userStoryEditor = useUserStoryEditorStore()
const chatStore = useModelModifierStore()
const ingestionStore = useIngestionStore()
const terminologyStore = useTerminologyStore()

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
    Property: '{ }'
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
  return terminologyStore.getLabel(props.node)
})

// Get children based on node type
const children = computed(() => {
  const type = props.node.type
  
  if (type === 'BoundedContext') {
    if (!props.tree) return []
    
    // User Stories under this BC come first
    const userStories = (props.tree.userStories || []).map(us => ({
      ...us,
      type: 'UserStory',
      name: us.name || `${us.role}: ${us.action?.substring(0, 25)}...`
    }))
    
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
    return [...userStories, ...aggregates, ...policies, ...readmodels, ...uis]
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
    return [...commands, ...events]
  }
  
  if (type === 'Command') {
    return (props.node.events || []).map(e => ({
      ...e,
      type: 'Event'
    }))
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
    return [...ops, ...propsList]
  }
  
  // UserStory has no children
  if (type === 'UserStory') {
    return []
  }
  
  return []
})

const hasChildren = computed(() => children.value.length > 0)

const isExpanded = computed(() => navigatorStore.isExpanded(props.node.id))

// Check if node is on the currently active viewer's canvas
// Only check the active viewer to ensure proper synchronization
const isOnCanvas = computed(() => {
  const nodeId = props.node.id
  const nodeType = props.node.type
  const currentTab = activeTab.value
  
  // For BoundedContext, check only the active viewer
  if (nodeType === 'BoundedContext') {
    if (currentTab === 'Design') {
      // Design Viewer - use nodeIds computed (reactive)
      return canvasStore.nodeIds.includes(nodeId)
    } else if (currentTab === 'Aggregate') {
      // Aggregate Viewer - check selectedBcIds
      const selectedBcIdsArray = Array.from(aggregateViewerStore.selectedBcIds)
      return selectedBcIdsArray.includes(nodeId)
    } else if (currentTab === 'Big picture') {
      // Big Picture Viewer - check swimlanes
      const swimlanes = bigPictureStore.swimlanes
      return swimlanes.some(lane => lane.bcId === nodeId)
    }
    // Default to Design Viewer
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
  
  // Normal click: toggle expand/collapse (works in all states including pause)
  navigatorStore.toggleExpanded(props.node.id)
}

// Add node to chat selection
function addToChatSelection() {
  // Skip UserStory nodes (they're not modifiable via chat)
  if (props.node.type === 'UserStory') {
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

// Double click handler - for UserStory opens edit modal, for others adds to canvas
async function handleDoubleClick() {
  if (props.node.type === 'UserStory') {
    // Open edit modal for user stories (User Stories feature)
    userStoryEditor.open(props.node)
  } else {
    // Add other node types to canvas
    await addToCanvas()
  }
}

// Drag handlers
function handleDragStart(event) {
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
    if (currentTab === 'Aggregate') {
      // Add to Aggregate Viewer
      await aggregateViewerStore.fetchAggregatesForBC(props.node.id)
      return
    } else if (currentTab === 'Big picture') {
      // Add to Big Picture Viewer with outbound flow
      await bigPictureStore.addBCWithOutboundFlow(props.node.id)
      return
    }
    // Fall through to Design Viewer for 'Design' tab or other cases
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

