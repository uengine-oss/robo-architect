<script setup>
import { onMounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

const props = defineProps({
  changeId: { type: String, required: true },
  autoStart: { type: Boolean, default: false },
  includePriorChangeIds: { type: Array, default: () => [] },
})
const emit = defineEmits(['started', 'done'])

const store = useRequirementsStore()
const tasks = ref([])
const phase = ref('')
const percentage = ref(0)
const running = ref(false)
const done = ref(false)
let stopFn = null

const STATUS_ICON = { PENDING: '○', IN_PROGRESS: '◉', DONE: '✓', FAILED: '✗' }
const STATUS_COLOR = { PENDING: 'var(--color-text-light)', IN_PROGRESS: 'var(--color-accent)', DONE: '#40c057', FAILED: '#fa5252' }

function startImpl() {
  running.value = true; done.value = false
  emit('started')
  stopFn = store.implementChange(props.changeId, {
    includePriorChangeIds: props.includePriorChangeIds,
    onProgress(data) {
      phase.value = data.phase || ''
      percentage.value = data.percentage || 0
      if (data.tasks) tasks.value = data.tasks
    },
    onDone() { done.value = true; running.value = false; emit('done') },
    onError(e) { running.value = false; console.error(e) },
  })
}

onMounted(() => { if (props.autoStart) startImpl() })
</script>

<template>
  <div class="ctv-root">
    <div v-if="!running && !done && !tasks.length" class="ctv-start">
      <button class="tb-btn tb-btn--primary" @click="startImpl">구현 시작</button>
    </div>

    <template v-if="running || tasks.length">
      <div class="ctv-progress">
        <span class="ctv-phase">{{ phase.toUpperCase() }}</span>
        <div class="ctv-bar-wrap">
          <div class="ctv-bar" :style="{ width: percentage + '%' }"></div>
        </div>
        <span class="ctv-pct">{{ percentage }}%</span>
      </div>

      <div class="ctv-tasks">
        <div v-for="task in tasks" :key="task.taskId" class="ctv-task">
          <span class="ctv-task__icon" :style="{ color: STATUS_COLOR[task.status] }">{{ STATUS_ICON[task.status] }}</span>
          <span class="ctv-task__id">{{ task.taskId }}</span>
          <span class="ctv-task__title">{{ task.title }}</span>
        </div>
      </div>
    </template>

    <div v-if="done" class="ctv-done">✓ 구현이 완료되었습니다.</div>
  </div>
</template>

<style scoped>
.ctv-root { display: flex; flex-direction: column; gap: 12px; }
.ctv-start { display: flex; justify-content: center; padding: 24px; }
.ctv-progress { display: flex; align-items: center; gap: 8px; }
.ctv-phase { font-size: 0.65rem; font-weight: 700; color: var(--color-text-light); min-width: 70px; }
.ctv-bar-wrap {
  flex: 1;
  height: 6px;
  background: var(--color-bg-tertiary);
  border-radius: 3px;
  overflow: hidden;
}
.ctv-bar {
  height: 100%;
  background: var(--color-accent);
  border-radius: 3px;
  transition: width 0.3s ease;
}
.ctv-pct { font-size: 0.68rem; color: var(--color-text-light); min-width: 30px; text-align: right; }
.ctv-tasks { display: flex; flex-direction: column; gap: 3px; }
.ctv-task { display: flex; align-items: center; gap: 6px; padding: 4px 8px; border-radius: 4px; background: var(--color-bg-tertiary); }
.ctv-task__icon { font-size: 0.75rem; width: 14px; flex-shrink: 0; }
.ctv-task__id { font-family: monospace; font-size: 0.65rem; color: var(--color-text-light); min-width: 40px; }
.ctv-task__title { font-size: 0.72rem; color: var(--color-text); }
.ctv-done {
  padding: 10px 14px;
  background: rgba(64, 192, 87, 0.1);
  border: 1px solid rgba(64, 192, 87, 0.3);
  border-radius: 4px;
  font-size: 0.75rem;
  color: #40c057;
  font-weight: 600;
}
</style>
