<script setup lang="ts">
import { ref } from 'vue'
import { useSessionStore } from '../../state/session.store'

const sessionStore = useSessionStore()

interface StickerTemplate {
  type: 'event' | 'command' | 'policy' | 'read_model' | 'external_system'
  label: string
  color: string
  icon: string
  description: string
}

const templates: StickerTemplate[] = [
  {
    type: 'event',
    label: 'Event',
    color: '#ff9800',
    icon: '⚡',
    description: '도메인 이벤트 (과거형)'
  },
  {
    type: 'command',
    label: 'Command',
    color: '#2196f3',
    icon: '▶️',
    description: '명령 (이벤트 트리거)'
  },
  {
    type: 'policy',
    label: 'Policy',
    color: '#9c27b0',
    icon: '📋',
    description: '정책 (When X, do Y)'
  },
  {
    type: 'read_model',
    label: 'Read Model',
    color: '#4caf50',
    icon: '📊',
    description: '읽기 모델 (데이터 뷰)'
  },
  {
    type: 'external_system',
    label: 'External',
    color: '#e91e63',
    icon: '🔗',
    description: '외부 시스템'
  }
]

const dragging = ref<StickerTemplate | null>(null)

function handleDragStart(e: DragEvent, template: StickerTemplate) {
  dragging.value = template
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'copy'
    e.dataTransfer.setData('sticker-type', template.type)
  }
}

function handleDragEnd() {
  dragging.value = null
}

// For touch devices / click to add
function addSticker(template: StickerTemplate) {
  // Add at center of visible canvas (simple implementation)
  const position = {
    x: 400 + Math.random() * 200,
    y: 200 + Math.random() * 200
  }

  const defaultText = template.type === 'event'
    ? '이벤트가 발생했다'
    : template.type === 'command'
      ? '명령 실행'
      : template.type === 'policy'
        ? 'When X, then Y'
        : template.type === 'read_model'
          ? '데이터 뷰'
          : '외부 시스템'

  sessionStore.addSticker(template.type, defaultText, position)
}
</script>

<template>
  <div class="sticker-palette">
    <h3 class="palette-title">Stickers</h3>

    <div class="sticker-list">
      <div
        v-for="template in templates"
        :key="template.type"
        class="palette-item"
        :class="{ dragging: dragging?.type === template.type }"
        :style="{ '--sticker-color': template.color }"
        draggable="true"
        @dragstart="handleDragStart($event, template)"
        @dragend="handleDragEnd"
        @click="addSticker(template)"
      >
        <div class="item-icon">{{ template.icon }}</div>
        <div class="item-label">{{ template.label }}</div>
      </div>
    </div>

    <div class="palette-help">
      <p>클릭하거나 드래그하여 캔버스에 추가</p>
    </div>
  </div>
</template>

<style scoped>
.sticker-palette {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.palette-title {
  font-size: 11px;
  text-transform: uppercase;
  color: #888;
  margin: 0;
  padding: 8px;
  text-align: center;
}

.sticker-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px;
}

.palette-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  background: var(--sticker-color);
  border-radius: 6px;
  cursor: grab;
  transition: all 0.2s;
  user-select: none;
}

.palette-item:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.palette-item:active,
.palette-item.dragging {
  cursor: grabbing;
  transform: scale(0.95);
  opacity: 0.7;
}

.item-icon {
  font-size: 20px;
  margin-bottom: 2px;
}

.item-label {
  font-size: 9px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.7);
  text-align: center;
}

.palette-help {
  padding: 8px;
  text-align: center;
}

.palette-help p {
  font-size: 9px;
  color: #666;
  margin: 0;
  line-height: 1.3;
}
</style>


