<script setup>
/**
 * 생성 모델 고르기 — P-GPT `/models` 목록에서 **내가** 쓸 모델을 고른다.
 *
 * 바꾸는 것은 설계 생성·채팅에 쓰는 모델뿐이다. 임베딩(검색)과 레거시 분석(analyzer)은 서버 설정을 따른다.
 * 고른 값은 이 브라우저에 사번별로 남고, 다음 요청부터 실린다(이미 돌고 있는 생성에는 안 닿는다).
 */
import { computed, onMounted, ref } from 'vue'
import { useAuthStore } from '@/features/auth/auth.store.js'
import { llmModelChoice, loadChoice, saveChoice } from '../llmModelChoice.js'

const auth = useAuthStore()
const uid = computed(() => (auth.user || {}).uid || null)

const loading = ref(false)
const models = ref([])
const defaultModel = ref('')
const error = ref('')

const value = computed({
  get: () => llmModelChoice.value,
  set: (v) => saveChoice(uid.value, v),
})

// 골라 둔 모델이 목록에서 사라졌으면(게이트웨이가 바뀜) 알려 준다 — 서버는 이미 기본값으로 돈다.
const stale = computed(() =>
  !!value.value && models.value.length > 0 && !models.value.includes(value.value),
)

async function refresh(force = false) {
  loading.value = true
  error.value = ''
  try {
    const r = await fetch(`/api/llm/models${force ? '?refresh=1' : ''}`)
    const body = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`)
    models.value = body.models || []
    defaultModel.value = body.default || ''
    if (body.error) error.value = `모델 목록을 받지 못했습니다 — ${body.error}`
  } catch (e) {
    error.value = `모델 목록을 받지 못했습니다 — ${e.message || e}`
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadChoice(uid.value)
  refresh()
})
</script>

<template>
  <div class="settings-section">
    <div class="settings-section__header">
      <h3 class="settings-section__title">생성 모델</h3>
      <span class="settings-section__description">
        설계 생성·채팅에 쓸 모델(P-GPT). 나에게만 적용됩니다. 임베딩·레거시 분석은 서버 설정을 따릅니다.
      </span>
    </div>
    <div class="settings-section__control settings-section__control--stack">
      <div class="llm-model__row">
        <select v-model="value" class="llm-model__select" :disabled="loading" data-testid="llm-model-select">
          <option value="">기본값{{ defaultModel ? ` (${defaultModel})` : '' }}</option>
          <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
          <option v-if="stale" :value="value">{{ value }} (목록에 없음)</option>
        </select>
        <button class="llm-model__refresh" :disabled="loading" title="목록 다시 받기" @click="refresh(true)">↻</button>
      </div>
      <span v-if="stale" class="llm-model__note llm-model__note--warn">
        골라 둔 모델이 지금 목록에 없어 기본값으로 생성합니다.
      </span>
      <span v-if="error" class="llm-model__note llm-model__note--warn">{{ error }}</span>
    </div>
  </div>
</template>

<style scoped>
.llm-model__row { display: flex; gap: 6px; align-items: center; }
.llm-model__select {
  min-width: 220px; padding: 6px 8px; border-radius: 6px;
  background: var(--color-bg-tertiary, #2a2a2a); color: var(--color-text, inherit);
  border: 1px solid var(--color-border, #444);
}
.llm-model__refresh {
  padding: 4px 8px; border-radius: 6px; cursor: pointer;
  background: transparent; color: inherit; border: 1px solid var(--color-border, #444);
}
.llm-model__note { font-size: 12px; opacity: 0.85; }
.llm-model__note--warn { color: var(--color-warning, #e0a040); }
</style>
