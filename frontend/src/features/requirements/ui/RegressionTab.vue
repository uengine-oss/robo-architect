<script setup>
import { onMounted, ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

const props = defineProps({ changeId: { type: String, required: true } })
const store = useRequirementsStore()
const data = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    data.value = await store.fetchRegression(props.changeId)
  } catch (e) {
    data.value = { error: e.message }
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="rt-root">
    <div v-if="loading" class="rt-loading">불러오는 중...</div>
    <div v-else-if="data?.error" class="rt-error">{{ data.error }}</div>
    <template v-else-if="data">
      <div class="rt-summary">
        영향받는 테스트: <strong>{{ data.regressionTests?.length || 0 }}</strong>개
      </div>
      <div v-if="data.regressionTests?.length" class="rt-list">
        <div v-for="(t, i) in data.regressionTests" :key="t.testId || `${t.testType}-${t.affectedNodeId}-${i}`" class="rt-item">
          <div class="rt-item__top">
            <span v-if="t.testType" class="rt-type">{{ t.testType }}</span>
            <span v-if="t.testId" class="rt-id">{{ t.testId }}</span>
            <span class="rt-name">{{ t.description || t.testName || '(설명 없음)' }}</span>
          </div>
          <div v-if="t.affectedNodeId" class="rt-affected">
            대상: {{ t.affectedNodeLabel ? `${t.affectedNodeLabel} ` : '' }}{{ t.affectedNodeId }}
          </div>
        </div>
      </div>
      <div v-else class="rt-empty">영향받는 테스트가 없습니다.</div>
    </template>
  </div>
</template>

<style scoped>
.rt-root { display: flex; flex-direction: column; gap: 8px; }
.rt-loading, .rt-empty { font-size: 0.72rem; color: var(--color-text-light); padding: 8px 0; }
.rt-error { font-size: 0.72rem; color: #fa5252; padding: 8px 0; }
.rt-summary { font-size: 0.72rem; color: var(--color-text-light); }
.rt-summary strong { color: var(--color-text); }
.rt-list { display: flex; flex-direction: column; gap: 4px; }
.rt-item {
  background: var(--color-bg-tertiary);
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 7px 10px;
}
.rt-item__top { display: flex; align-items: center; gap: 8px; margin-bottom: 2px; }
.rt-type {
  font-size: 0.6rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.03em; color: var(--color-accent);
  border: 1px solid var(--color-accent); border-radius: 3px; padding: 1px 5px;
}
.rt-id { font-family: monospace; font-size: 0.68rem; font-weight: 700; color: var(--color-text-light); }
.rt-name { font-size: 0.72rem; color: var(--color-text); }
.rt-affected { font-size: 0.65rem; color: var(--color-text-light); }
</style>
