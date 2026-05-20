<script setup>
import { ref, computed } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * Add Requirement dialog (026 — US3).
 * Natural-language mode runs propose → review → confirm (Constitution IV).
 * Manual mode writes role/action/benefit directly via confirm.
 */
const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'added'])

const store = useRequirementsStore()

const mode = ref('nl') // 'nl' | 'manual'
const busy = ref(false)
const errorMsg = ref('')

// Natural-language state
const nlText = ref('')
const proposals = ref([])
const warnings = ref([])
const proposed = ref(false)

// Manual state
const manual = ref({ role: '', action: '', benefit: '', boundedContextId: '', featureId: '' })

const bcOptions = computed(() =>
  (store.tree.epics || []).map((e) => ({ id: e.id, name: e.name })),
)
function featureOptions(bcId) {
  const epic = (store.tree.epics || []).find((e) => e.id === bcId)
  return epic ? epic.features || [] : []
}

function close() {
  emit('update:modelValue', false)
  resetState()
}
function resetState() {
  mode.value = 'nl'
  nlText.value = ''
  proposals.value = []
  warnings.value = []
  proposed.value = false
  errorMsg.value = ''
  manual.value = { role: '', action: '', benefit: '', boundedContextId: '', featureId: '' }
}

async function runPropose() {
  if (!nlText.value.trim()) return
  busy.value = true
  errorMsg.value = ''
  try {
    const res = await store.proposeUserStory(nlText.value.trim())
    proposals.value = (res.proposals || []).map((p) => ({
      role: p.role || '',
      action: p.action || '',
      benefit: p.benefit || '',
      boundedContextId: p.suggestedBoundedContextId || '',
      featureId: p.suggestedFeatureId || '',
      newFeatureName: p.suggestedFeatureId ? '' : p.suggestedFeatureName || '',
    }))
    warnings.value = res.warnings || []
    proposed.value = true
  } catch (e) {
    errorMsg.value = String(e)
  } finally {
    busy.value = false
  }
}

async function confirmProposal(p, index) {
  busy.value = true
  errorMsg.value = ''
  try {
    await store.confirmUserStory({
      role: p.role,
      action: p.action,
      benefit: p.benefit,
      boundedContextId: p.boundedContextId || null,
      featureId: p.featureId || null,
      newFeatureName: p.featureId ? null : p.newFeatureName || null,
    })
    proposals.value.splice(index, 1)
    emit('added')
    if (!proposals.value.length) close()
  } catch (e) {
    errorMsg.value = String(e)
  } finally {
    busy.value = false
  }
}

async function confirmManual() {
  if (!manual.value.action.trim()) {
    errorMsg.value = 'action(원하는 행동)은 필수입니다.'
    return
  }
  busy.value = true
  errorMsg.value = ''
  try {
    await store.confirmUserStory({
      role: manual.value.role || '사용자',
      action: manual.value.action,
      benefit: manual.value.benefit,
      boundedContextId: manual.value.boundedContextId || null,
      featureId: manual.value.featureId || null,
    })
    emit('added')
    close()
  } catch (e) {
    errorMsg.value = String(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div v-if="modelValue" class="dialog-backdrop" @click.self="close">
    <div class="dialog">
      <div class="dialog__head">
        <h3>요구사항 추가</h3>
        <button class="dialog__close" @click="close">×</button>
      </div>

      <div class="dialog__tabs">
        <button :class="{ active: mode === 'nl' }" @click="mode = 'nl'">자연어 입력</button>
        <button :class="{ active: mode === 'manual' }" @click="mode = 'manual'">수동 입력</button>
      </div>

      <div class="dialog__body">
        <p v-if="errorMsg" class="dialog__error">{{ errorMsg }}</p>

        <!-- Natural-language mode -->
        <template v-if="mode === 'nl'">
          <textarea
            v-model="nlText"
            class="nl-input"
            placeholder="추가할 요구사항을 자연어로 설명하세요..."
            rows="4"
          />
          <button class="btn btn--primary" :disabled="busy || !nlText.trim()" @click="runPropose">
            {{ busy ? '분석 중...' : '분석' }}
          </button>

          <div v-if="warnings.length" class="warnings">
            <p v-for="(w, i) in warnings" :key="i" class="warning">⚠ {{ w.message }}</p>
          </div>

          <div v-if="proposed && !proposals.length" class="empty-hint">
            제안된 User Story가 없습니다.
          </div>
          <div v-for="(p, i) in proposals" :key="i" class="proposal">
            <label>역할 <input v-model="p.role" /></label>
            <label>행동 <input v-model="p.action" /></label>
            <label>효과 <input v-model="p.benefit" /></label>
            <label>BC
              <select v-model="p.boundedContextId">
                <option value="">(미분류)</option>
                <option v-for="bc in bcOptions" :key="bc.id" :value="bc.id">{{ bc.name }}</option>
              </select>
            </label>
            <label>Feature
              <select v-model="p.featureId">
                <option value="">(새 Feature / 미분류)</option>
                <option v-for="f in featureOptions(p.boundedContextId)" :key="f.id" :value="f.id">
                  {{ f.name }}
                </option>
              </select>
            </label>
            <label v-if="!p.featureId">새 Feature 이름
              <input v-model="p.newFeatureName" placeholder="(비우면 미분류)" />
            </label>
            <button class="btn btn--primary" :disabled="busy" @click="confirmProposal(p, i)">추가</button>
          </div>
        </template>

        <!-- Manual mode -->
        <template v-else>
          <label>역할 (As a) <input v-model="manual.role" placeholder="예: 고객" /></label>
          <label>행동 (I want) <input v-model="manual.action" placeholder="예: 주문을 취소한다" /></label>
          <label>효과 (so that) <input v-model="manual.benefit" placeholder="예: 환불을 받을 수 있다" /></label>
          <label>Bounded Context
            <select v-model="manual.boundedContextId">
              <option value="">(미분류)</option>
              <option v-for="bc in bcOptions" :key="bc.id" :value="bc.id">{{ bc.name }}</option>
            </select>
          </label>
          <label>Feature
            <select v-model="manual.featureId">
              <option value="">(미분류)</option>
              <option v-for="f in featureOptions(manual.boundedContextId)" :key="f.id" :value="f.id">
                {{ f.name }}
              </option>
            </select>
          </label>
          <button class="btn btn--primary" :disabled="busy" @click="confirmManual">추가</button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.dialog {
  width: 520px; max-height: 80vh; background: var(--color-bg-secondary);
  border-radius: 10px; display: flex; flex-direction: column; overflow: hidden;
}
.dialog__head {
  display: flex; align-items: center; padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.dialog__head h3 { margin: 0; font-size: 0.95rem; }
.dialog__close {
  margin-left: auto; border: none; background: transparent; font-size: 1.2rem;
  cursor: pointer; color: var(--color-text-light);
}
.dialog__tabs { display: flex; gap: 4px; padding: 8px 16px 0; }
.dialog__tabs button {
  padding: 6px 12px; border: none; border-radius: 6px 6px 0 0; cursor: pointer;
  background: var(--color-bg-tertiary); color: var(--color-text-light); font-size: 0.78rem;
}
.dialog__tabs button.active { background: var(--color-accent); color: #fff; }
.dialog__body { padding: 14px 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; }
.dialog__error { color: #e03131; font-size: 0.78rem; }
.nl-input, label input, label select, textarea {
  width: 100%; box-sizing: border-box; padding: 6px 8px; font-size: 0.8rem;
  background: var(--color-bg-tertiary); border: 1px solid var(--color-border);
  border-radius: 6px; color: var(--color-text);
}
label { display: flex; flex-direction: column; gap: 3px; font-size: 0.72rem; color: var(--color-text-light); }
.btn {
  padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer;
  font-size: 0.78rem; align-self: flex-start;
}
.btn--primary { background: var(--color-accent); color: #fff; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.proposal {
  display: flex; flex-direction: column; gap: 6px; padding: 10px;
  border: 1px solid var(--color-border); border-radius: 8px;
}
.warnings { display: flex; flex-direction: column; gap: 3px; }
.warning { font-size: 0.74rem; color: #fd7e14; margin: 0; }
.empty-hint { font-size: 0.78rem; color: var(--color-text-light); }
</style>
