<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useSessionStore, type Sticker, type Position } from '../../stores/session'

const sessionStore = useSessionStore()

// Track the last sticker count to detect new additions
const lastStickerCount = ref(sessionStore.stickers.length)

const canvasRef = ref<HTMLDivElement | null>(null)
const isDragging = ref(false)
const draggedSticker = ref<string | null>(null)
const dragOffset = ref({ x: 0, y: 0 })
const viewOffset = ref({ x: 0, y: 0 })
const isPanning = ref(false)
const panStart = ref({ x: 0, y: 0 })
const scale = ref(1)

const selectedSticker = ref<string | null>(null)
const editingSticker = ref<string | null>(null)
const editText = ref('')

// Sticker colors by type
const stickerColors: Record<string, { bg: string; border: string }> = {
  event: { bg: '#ff9800', border: '#f57c00' },
  command: { bg: '#2196f3', border: '#1976d2' },
  policy: { bg: '#9c27b0', border: '#7b1fa2' },
  read_model: { bg: '#4caf50', border: '#388e3c' },
  external_system: { bg: '#e91e63', border: '#c2185b' }
}

// Handle mouse events for canvas panning
function handleCanvasMouseDown(e: MouseEvent) {
  if (e.button === 1 || (e.button === 0 && e.altKey)) {
    // Middle click or Alt+click to pan
    isPanning.value = true
    panStart.value = { x: e.clientX - viewOffset.value.x, y: e.clientY - viewOffset.value.y }
  }
}

function handleCanvasMouseMove(e: MouseEvent) {
  if (isPanning.value) {
    viewOffset.value = {
      x: e.clientX - panStart.value.x,
      y: e.clientY - panStart.value.y
    }
  } else if (isDragging.value && draggedSticker.value && canvasRef.value) {
    const rect = canvasRef.value.getBoundingClientRect()
    const x = (e.clientX - rect.left - viewOffset.value.x) / scale.value - dragOffset.value.x
    const y = (e.clientY - rect.top - viewOffset.value.y) / scale.value - dragOffset.value.y

    sessionStore.moveSticker(draggedSticker.value, { x, y })
  }

  // Update cursor position for collaboration
  if (canvasRef.value) {
    const rect = canvasRef.value.getBoundingClientRect()
    const x = (e.clientX - rect.left - viewOffset.value.x) / scale.value
    const y = (e.clientY - rect.top - viewOffset.value.y) / scale.value
    sessionStore.updateCursor(x, y)
  }
}

function handleCanvasMouseUp() {
  isPanning.value = false
  if (isDragging.value && draggedSticker.value) {
    const sticker = sessionStore.stickers.find(s => s.id === draggedSticker.value)
    if (sticker) {
      sessionStore.updateSticker(draggedSticker.value, { position: sticker.position })
    }
  }
  isDragging.value = false
  draggedSticker.value = null
}

// Handle wheel for zoom
function handleWheel(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newScale = Math.min(Math.max(scale.value * delta, 0.25), 3)
  
  // Zoom toward mouse position
  if (canvasRef.value) {
    const rect = canvasRef.value.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top
    
    viewOffset.value = {
      x: mouseX - (mouseX - viewOffset.value.x) * (newScale / scale.value),
      y: mouseY - (mouseY - viewOffset.value.y) * (newScale / scale.value)
    }
  }
  
  scale.value = newScale
}

// Sticker interaction
function handleStickerMouseDown(e: MouseEvent, sticker: Sticker) {
  e.stopPropagation()
  
  if (canvasRef.value) {
    const rect = canvasRef.value.getBoundingClientRect()
    const x = (e.clientX - rect.left - viewOffset.value.x) / scale.value
    const y = (e.clientY - rect.top - viewOffset.value.y) / scale.value
    
    dragOffset.value = {
      x: x - sticker.position.x,
      y: y - sticker.position.y
    }
  }
  
  isDragging.value = true
  draggedSticker.value = sticker.id
  selectedSticker.value = sticker.id
}

// Handle sticker click (separate from mousedown for selection)
function handleStickerClick(e: MouseEvent, sticker: Sticker) {
  e.stopPropagation() // Prevent canvas click from deselecting
  selectedSticker.value = sticker.id
}

function handleStickerDoubleClick(sticker: Sticker) {
  editingSticker.value = sticker.id
  editText.value = sticker.text
}

function finishEditing() {
  if (editingSticker.value && editText.value.trim()) {
    sessionStore.updateSticker(editingSticker.value, { text: editText.value })
  }
  editingSticker.value = null
  editText.value = ''
}

function deleteSelected() {
  if (selectedSticker.value) {
    sessionStore.deleteSticker(selectedSticker.value)
    selectedSticker.value = null
  }
}

// Keyboard shortcuts
function handleKeyDown(e: KeyboardEvent) {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    if (!editingSticker.value && selectedSticker.value) {
      deleteSelected()
    }
  } else if (e.key === 'Escape') {
    selectedSticker.value = null
    editingSticker.value = null
  } else if (e.key === 'Enter' && editingSticker.value) {
    finishEditing()
  }
}

// Watch for new stickers added by current user and auto-edit
watch(() => sessionStore.stickers.length, (newLen, oldLen) => {
  if (newLen > oldLen) {
    // A new sticker was added
    const newSticker = sessionStore.stickers[sessionStore.stickers.length - 1]
    
    // Check if this sticker was added by the current user
    if (newSticker && newSticker.author === sessionStore.currentUser) {
      // Select and enter edit mode for the new sticker
      selectedSticker.value = newSticker.id
      editingSticker.value = newSticker.id
      editText.value = newSticker.text
      
      // Focus the textarea after Vue updates the DOM
      nextTick(() => {
        const textarea = document.querySelector('.sticker.selected .sticker-edit textarea') as HTMLTextAreaElement
        if (textarea) {
          textarea.focus()
          textarea.select()
        }
      })
    }
  }
  lastStickerCount.value = newLen
})

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
  lastStickerCount.value = sessionStore.stickers.length
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

// Transform style for canvas
const canvasTransform = computed(() => 
  `translate(${viewOffset.value.x}px, ${viewOffset.value.y}px) scale(${scale.value})`
)
</script>

<template>
  <div
    ref="canvasRef"
    class="canvas-board"
    @mousedown="handleCanvasMouseDown"
    @mousemove="handleCanvasMouseMove"
    @mouseup="handleCanvasMouseUp"
    @mouseleave="handleCanvasMouseUp"
    @wheel="handleWheel"
    @click="selectedSticker = null"
  >
    <!-- Grid background -->
    <div class="grid-background" :style="{ transform: canvasTransform }"></div>

    <!-- Stickers container -->
    <div class="stickers-container" :style="{ transform: canvasTransform }">
      <!-- Connections -->
      <svg class="connections-layer">
        <line
          v-for="conn in sessionStore.connections"
          :key="conn.id"
          :x1="sessionStore.stickers.find(s => s.id === conn.source_id)?.position.x ?? 0 + 100"
          :y1="sessionStore.stickers.find(s => s.id === conn.source_id)?.position.y ?? 0 + 40"
          :x2="sessionStore.stickers.find(s => s.id === conn.target_id)?.position.x ?? 0"
          :y2="sessionStore.stickers.find(s => s.id === conn.target_id)?.position.y ?? 0 + 40"
          stroke="#666"
          stroke-width="2"
          marker-end="url(#arrowhead)"
        />
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" fill="#666" />
          </marker>
        </defs>
      </svg>

      <!-- Stickers -->
      <div
        v-for="sticker in sessionStore.stickers"
        :key="sticker.id"
        class="sticker"
        :class="{ 
          selected: selectedSticker === sticker.id,
          dragging: draggedSticker === sticker.id
        }"
        :style="{
          left: sticker.position.x + 'px',
          top: sticker.position.y + 'px',
          backgroundColor: stickerColors[sticker.type]?.bg || '#ffeb3b',
          borderColor: stickerColors[sticker.type]?.border || '#fbc02d'
        }"
        @mousedown="handleStickerMouseDown($event, sticker)"
        @click="handleStickerClick($event, sticker)"
        @dblclick="handleStickerDoubleClick(sticker)"
      >
        <!-- Delete button (shown on hover or when selected) -->
        <button 
          v-if="editingSticker !== sticker.id"
          class="delete-btn"
          @click.stop="() => { selectedSticker = sticker.id; deleteSelected(); }"
          title="삭제 (Delete)"
        >
          ✕
        </button>
        
        <div class="sticker-type">{{ sticker.type }}</div>
        <div v-if="editingSticker === sticker.id" class="sticker-edit">
          <textarea
            v-model="editText"
            @blur="finishEditing"
            @keydown.enter.prevent="finishEditing"
            autofocus
          />
        </div>
        <div v-else class="sticker-text">{{ sticker.text }}</div>
        <div class="sticker-author">{{ sticker.author }}</div>
      </div>

      <!-- Other users' cursors -->
      <div
        v-for="[id, cursor] in sessionStore.cursors"
        :key="id"
        class="remote-cursor"
        :style="{ left: cursor.x + 'px', top: cursor.y + 'px' }"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M5.5 3.21V20.8l6.14-6.14h7.57L5.5 3.21z"/>
        </svg>
        <span class="cursor-name">{{ cursor.name }}</span>
      </div>
    </div>

    <!-- Zoom controls -->
    <div class="zoom-controls">
      <button @click="scale = Math.min(scale * 1.2, 3)">+</button>
      <span>{{ Math.round(scale * 100) }}%</span>
      <button @click="scale = Math.max(scale * 0.8, 0.25)">-</button>
      <button @click="scale = 1; viewOffset = { x: 0, y: 0 }">⌂</button>
    </div>
  </div>
</template>

<style scoped>
.canvas-board {
  width: 100%;
  height: 100%;
  position: relative;
  overflow: hidden;
  background: #16213e;
  cursor: grab;
}

.canvas-board:active {
  cursor: grabbing;
}

.grid-background {
  position: absolute;
  top: -5000px;
  left: -5000px;
  width: 10000px;
  height: 10000px;
  background-image: 
    linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 50px 50px;
  pointer-events: none;
}

.stickers-container {
  position: absolute;
  top: 0;
  left: 0;
  transform-origin: 0 0;
  overflow: visible;
}

.connections-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 10000px;
  height: 10000px;
  pointer-events: none;
}

.sticker {
  position: absolute;
  width: 200px;
  min-height: 80px;
  padding: 12px;
  border-radius: 4px;
  border: 2px solid;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
  cursor: move;
  user-select: none;
  transition: box-shadow 0.2s, transform 0.1s;
  overflow: visible;
}

.sticker:hover {
  box-shadow: 0 6px 12px rgba(0, 0, 0, 0.4);
}

.sticker.selected {
  box-shadow: 0 0 0 3px #fff, 0 6px 12px rgba(0, 0, 0, 0.4);
}

.sticker.dragging {
  opacity: 0.8;
  transform: scale(1.05);
}

.delete-btn {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #f44336;
  color: white;
  border: 2px solid rgba(0,0,0,0.2);
  font-size: 14px;
  font-weight: bold;
  cursor: pointer;
  display: none;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
  z-index: 100;
}

/* Show delete button on sticker hover or when selected */
.sticker:hover .delete-btn,
.sticker.selected .delete-btn {
  display: flex;
}

.delete-btn:hover {
  background: #c62828;
  transform: scale(1.1);
}

.sticker-type {
  font-size: 10px;
  text-transform: uppercase;
  opacity: 0.7;
  margin-bottom: 4px;
  color: rgba(0, 0, 0, 0.7);
}

.sticker-text {
  font-size: 14px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.87);
  word-wrap: break-word;
}

.sticker-edit textarea {
  width: 100%;
  min-height: 60px;
  padding: 4px;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 2px;
  font-size: 14px;
  resize: none;
}

.sticker-author {
  font-size: 10px;
  opacity: 0.6;
  margin-top: 8px;
  color: rgba(0, 0, 0, 0.6);
}

.remote-cursor {
  position: absolute;
  pointer-events: none;
  color: #e94560;
  z-index: 1000;
}

.cursor-name {
  position: absolute;
  left: 20px;
  top: 16px;
  background: #e94560;
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}

.zoom-controls {
  position: absolute;
  bottom: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(0, 0, 0, 0.6);
  padding: 8px 12px;
  border-radius: 8px;
}

.zoom-controls button {
  width: 32px;
  height: 32px;
  border: none;
  background: rgba(255, 255, 255, 0.1);
  color: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 16px;
}

.zoom-controls button:hover {
  background: rgba(255, 255, 255, 0.2);
}

.zoom-controls span {
  color: white;
  font-size: 12px;
  min-width: 48px;
  text-align: center;
}
</style>

