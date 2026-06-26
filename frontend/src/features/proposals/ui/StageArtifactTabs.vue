<template>
  <div class="stage-artifact-tabs">
    <div class="stage-artifact-tabs__chips">
      <button
        type="button"
        :class="['stage-artifact-tabs__chip', activeKey === baseKey ? 'is-active' : '']"
        @click="select(baseKey)"
      >
        {{ baseLabel }}
      </button>
      <button
        v-for="stage in stages"
        :key="stage"
        type="button"
        :class="['stage-artifact-tabs__chip', activeKey === stage ? 'is-active' : '']"
        @click="select(stage)"
      >
        {{ shortLabel(stage) }}
      </button>
    </div>

    <div v-if="activeKey === baseKey" class="stage-artifact-tabs__pane">
      <slot name="base" />
    </div>
    <div v-else class="stage-artifact-tabs__readonly">
      <div class="stage-artifact-tabs__readonly-head">
        <span>{{ longLabel(activeKey) }} <em class="stage-artifact-tabs__ro-tag">읽기 전용</em></span>
      </div>
      <StageReadonly :stage="activeKey" :artifact="artifacts[activeKey]" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StageReadonly from './stages/StageReadonly.vue'

const props = defineProps({
  modelValue: { type: String, required: true },
  baseKey: { type: String, required: true },
  baseLabel: { type: String, required: true },
  stages: { type: Array, default: () => [] },
  artifacts: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])

const SHORT_LABELS = {
  DISCOVER: 'Discover',
  DECOMPOSE: 'Decompose',
  STRATEGIZE: 'Strategize',
  CONNECT: 'Connect',
  DEFINE: 'Define',
  TACTICAL: 'Tactical',
}
const LONG_LABELS = {
  DISCOVER: 'Discover — 이벤트 발굴',
  DECOMPOSE: 'Decompose — 서브도메인',
  STRATEGIZE: 'Strategize — Core/Supporting/Generic',
  CONNECT: 'Connect — 컨텍스트 연동',
  DEFINE: 'Define — Bounded Context',
  TACTICAL: 'Tactical — Aggregate 설계',
}

const validKeys = computed(() => new Set([props.baseKey, ...props.stages]))
const activeKey = computed(() => validKeys.value.has(props.modelValue) ? props.modelValue : props.baseKey)

function shortLabel(stage) {
  return SHORT_LABELS[stage] || stage
}

function longLabel(stage) {
  return LONG_LABELS[stage] || stage
}

function select(key) {
  emit('update:modelValue', key)
}
</script>

<style scoped>
.stage-artifact-tabs { min-width: 0; }
.stage-artifact-tabs__chips { display: flex; gap: 6px; margin-bottom: 12px; flex-wrap: wrap; }
.stage-artifact-tabs__chip {
  font-size: 11px;
  padding: 4px 12px;
  border-radius: 12px;
  border: none;
  background: var(--color-bg-tertiary);
  color: var(--color-text-light);
  cursor: pointer;
}
.stage-artifact-tabs__chip.is-active { background: var(--color-accent); color: #fff; }
.stage-artifact-tabs__pane,
.stage-artifact-tabs__readonly { min-width: 0; }
.stage-artifact-tabs__readonly-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 13px;
  color: var(--color-text-bright);
}
.stage-artifact-tabs__ro-tag {
  font-size: 10px;
  font-weight: 400;
  font-style: normal;
  color: var(--color-text-light);
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 1px 6px;
  margin-left: 6px;
}
</style>
