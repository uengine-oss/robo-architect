<script setup>
import { computed, onMounted } from 'vue'
import { useFigmaBindingStore } from '../figmaBinding.store'

defineProps({
  modelValue: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])

const store = useFigmaBindingStore()

onMounted(() => {
  store.loadBinding()
})

const dotClass = computed(() => {
  if (!store.binding) return 'figma-btn__dot--none'
  if (store.status === 'active') return 'figma-btn__dot--active'
  if (store.status === 'unreachable') return 'figma-btn__dot--unreachable'
  return 'figma-btn__dot--none'
})

const titleText = computed(() => {
  if (!store.binding) return 'Figma 다큐먼트 연동'
  if (store.status === 'unreachable') return `연결 끊김: ${store.fileName}`
  return `연동됨: ${store.fileName}`
})

const labelText = computed(() => {
  if (!store.binding) return 'Figma'
  return store.fileName
    ? `Figma · ${truncate(store.fileName, 14)}`
    : 'Figma'
})

function truncate(s, n) {
  if (!s) return ''
  return s.length <= n ? s : s.slice(0, n - 1) + '…'
}

function open() {
  emit('update:modelValue', true)
}
</script>

<template>
  <button class="figma-btn" :title="titleText" @click="open">
    <span class="figma-btn__dot" :class="dotClass" />
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 2v20"/>
      <path d="M5 7a4 4 0 0 1 4-4h6a4 4 0 0 1 0 8H9a4 4 0 0 1-4-4z"/>
      <path d="M5 16a4 4 0 0 1 4-4h6a4 4 0 0 1 0 8H9a4 4 0 0 1-4-4z"/>
    </svg>
    <span>{{ labelText }}</span>
  </button>
</template>

<style scoped>
.figma-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: linear-gradient(135deg, #0acf83 0%, #1abc9c 100%);
  border: none;
  border-radius: 4px;
  color: #fff;
  font-size: 0.7rem;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.figma-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(10, 207, 131, 0.4);
}

.figma-btn:active {
  transform: translateY(0);
}

.figma-btn__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 auto;
}

.figma-btn__dot--active {
  background: #fff;
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.4);
}

.figma-btn__dot--unreachable {
  background: #ef4444;
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.4);
}

.figma-btn__dot--none {
  background: rgba(255, 255, 255, 0.5);
}
</style>
