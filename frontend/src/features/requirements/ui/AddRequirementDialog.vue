<script setup>
import { ref, computed, watch } from 'vue'
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

const unit = ref('userStory') // 'epic' | 'feature' | 'userStory' (034 US1)
const mode = ref('nl') // 'nl' | 'manual' (User Story only)
const busy = ref(false)
const errorMsg = ref('')

// Epic / Feature create state (034 US1) — manual form + AI 제안 sub-mode.
const efMode = ref('manual') // 'manual' | 'ai' (for Epic/Feature units)
const epicForm = ref({ name: '', displayName: '', description: '' })
const featureForm = ref({ boundedContextId: '', name: '', description: '' })
// AI 제안 state
const efText = ref('')
const efProposed = ref(false)
const efProposals = ref([]) // [{name, description, boundedContextId?}]

/**
 * 다이얼로그를 열 때, 트리에서 선택된 노드 기준으로 추가 단위를 자동 선택한다(034):
 *  - 아무것도 선택 안 됨 → Epic
 *  - Epic 선택 → 그 Epic 하위 Feature (소속 Epic 미리 채움)
 *  - Feature 선택 → 그 Feature 하위 User Story (소속 Epic·Feature 미리 채움)
 */
function applyContextDefault() {
  const node = store.selectedNode || { type: null }
  if (node.type === 'feature' && store.selectedFeature) {
    unit.value = 'userStory'
    mode.value = 'manual' // 미리 채운 소속을 바로 보여주기 위해 수동 탭
    manual.value.boundedContextId = store.selectedFeature.boundedContextId || ''
    manual.value.featureId = store.selectedFeature.id
  } else if (node.type === 'epic' && store.selectedEpic) {
    unit.value = 'feature'
    featureForm.value.boundedContextId = store.selectedEpic.id
  } else {
    unit.value = 'epic'
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) applyContextDefault()
  },
  { immediate: true },
)

async function runProposeEpic() {
  if (!efText.value.trim()) return
  busy.value = true
  errorMsg.value = ''
  try {
    const res = await store.proposeEpic(efText.value.trim())
    efProposals.value = res.proposals || []
    efProposed.value = true
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

async function runProposeFeature() {
  if (!efText.value.trim()) return
  busy.value = true
  errorMsg.value = ''
  try {
    const res = await store.proposeFeature(efText.value.trim(), featureForm.value.boundedContextId || null)
    efProposals.value = res.proposals || []
    efProposed.value = true
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

async function addProposedEpic(p, i) {
  busy.value = true
  errorMsg.value = ''
  try {
    await store.createEpic(p.name, p.description || null, (p.displayName || '').trim() || null)
    efProposals.value.splice(i, 1)
    emit('added')
    if (!efProposals.value.length) close()
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

async function addProposedFeature(p, i) {
  const bcId = p.boundedContextId || featureForm.value.boundedContextId
  if (!bcId) {
    errorMsg.value = '소속 Epic을 선택하세요.'
    return
  }
  busy.value = true
  errorMsg.value = ''
  try {
    await store.createFeature(bcId, p.name, p.description || null)
    efProposals.value.splice(i, 1)
    emit('added')
    if (!efProposals.value.length) close()
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

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
  unit.value = 'userStory'
  mode.value = 'nl'
  nlText.value = ''
  proposals.value = []
  warnings.value = []
  proposed.value = false
  errorMsg.value = ''
  manual.value = { role: '', action: '', benefit: '', boundedContextId: '', featureId: '' }
  epicForm.value = { name: '', displayName: '', description: '' }
  featureForm.value = { boundedContextId: '', name: '', description: '' }
  efMode.value = 'manual'
  efText.value = ''
  efProposed.value = false
  efProposals.value = []
}

async function confirmEpic() {
  if (!epicForm.value.name.trim()) {
    errorMsg.value = 'Epic 이름은 필수입니다.'
    return
  }
  busy.value = true
  errorMsg.value = ''
  try {
    await store.createEpic(
      epicForm.value.name.trim(),
      epicForm.value.description || null,
      epicForm.value.displayName.trim() || null,
    )
    emit('added')
    close()
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}

async function confirmFeature() {
  if (!featureForm.value.boundedContextId) {
    errorMsg.value = '소속 Epic을 선택하세요.'
    return
  }
  if (!featureForm.value.name.trim()) {
    errorMsg.value = 'Feature 이름은 필수입니다.'
    return
  }
  busy.value = true
  errorMsg.value = ''
  try {
    await store.createFeature(
      featureForm.value.boundedContextId,
      featureForm.value.name.trim(),
      featureForm.value.description || null,
    )
    emit('added')
    close()
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
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

      <!-- Unit selector (034 US1): Epic / Feature / User Story -->
      <div class="dialog__units">
        <button :class="{ active: unit === 'epic' }" @click="unit = 'epic'">Epic</button>
        <button :class="{ active: unit === 'feature' }" @click="unit = 'feature'">Feature</button>
        <button :class="{ active: unit === 'userStory' }" @click="unit = 'userStory'">User Story</button>
      </div>

      <div v-if="unit === 'userStory'" class="dialog__tabs">
        <button :class="{ active: mode === 'nl' }" @click="mode = 'nl'">자연어 입력</button>
        <button :class="{ active: mode === 'manual' }" @click="mode = 'manual'">수동 입력</button>
      </div>

      <div v-if="unit === 'epic' || unit === 'feature'" class="dialog__tabs">
        <button :class="{ active: efMode === 'ai' }" @click="efMode = 'ai'">AI 제안</button>
        <button :class="{ active: efMode === 'manual' }" @click="efMode = 'manual'">수동 입력</button>
      </div>

      <div class="dialog__body">
        <p v-if="errorMsg" class="dialog__error">{{ errorMsg }}</p>

        <!-- Epic — AI 제안 (034 US1) -->
        <template v-if="unit === 'epic' && efMode === 'ai'">
          <textarea v-model="efText" class="nl-input" rows="4"
            placeholder="만들고 싶은 업무 영역(Epic)을 자연어로 설명하세요..." />
          <button class="btn btn--primary" :disabled="busy || !efText.trim()" @click="runProposeEpic">
            {{ busy ? '제안 중...' : '제안 받기' }}
          </button>
          <div v-if="efProposed && !efProposals.length" class="empty-hint">제안된 Epic이 없습니다. 수동 입력으로 추가하세요.</div>
          <div v-for="(p, i) in efProposals" :key="i" class="proposal">
            <label>기술명 (영문 권장) <input v-model="p.name" placeholder="예: OrderManagement" /></label>
            <label>표시명 (선택) <input v-model="p.displayName" placeholder="예: 주문 관리" /></label>
            <label>설명 <input v-model="p.description" /></label>
            <button class="btn btn--primary" :disabled="busy" @click="addProposedEpic(p, i)">추가</button>
          </div>
        </template>

        <!-- Epic — 수동 (034 US1) -->
        <template v-else-if="unit === 'epic'">
          <label>기술명 (영문 권장) <input v-model="epicForm.name" placeholder="예: OrderManagement" /></label>
          <label>표시명 (선택) <input v-model="epicForm.displayName" placeholder="예: 주문 관리 — 비우면 기술명 사용" /></label>
          <label>설명 (선택)
            <textarea v-model="epicForm.description" rows="3" placeholder="이 Epic(Bounded Context)의 책임" />
          </label>
          <button class="btn btn--primary" :disabled="busy || !epicForm.name.trim()" @click="confirmEpic">
            {{ busy ? '추가 중...' : 'Epic 추가' }}
          </button>
        </template>

        <!-- Feature — AI 제안 (034 US1) -->
        <template v-else-if="unit === 'feature' && efMode === 'ai'">
          <label>소속 Epic
            <select v-model="featureForm.boundedContextId">
              <option value="">(선택)</option>
              <option v-for="bc in bcOptions" :key="bc.id" :value="bc.id">{{ bc.name }}</option>
            </select>
          </label>
          <textarea v-model="efText" class="nl-input" rows="4"
            placeholder="추가하고 싶은 기능(Feature)을 자연어로 설명하세요..." />
          <p v-if="!featureForm.boundedContextId" class="empty-hint">소속 Epic을 먼저 선택하세요.</p>
          <button
            class="btn btn--primary"
            :disabled="busy || !efText.trim() || !featureForm.boundedContextId"
            @click="runProposeFeature"
          >
            {{ busy ? '제안 중...' : '제안 받기' }}
          </button>
          <div v-if="efProposed && !efProposals.length" class="empty-hint">제안된 Feature가 없습니다. 수동 입력으로 추가하세요.</div>
          <div v-for="(p, i) in efProposals" :key="i" class="proposal">
            <label>이름 <input v-model="p.name" /></label>
            <label>설명 <input v-model="p.description" /></label>
            <button class="btn btn--primary" :disabled="busy" @click="addProposedFeature(p, i)">추가</button>
          </div>
        </template>

        <!-- Feature — 수동 (034 US1) -->
        <template v-else-if="unit === 'feature'">
          <label>소속 Epic
            <select v-model="featureForm.boundedContextId">
              <option value="">(선택)</option>
              <option v-for="bc in bcOptions" :key="bc.id" :value="bc.id">{{ bc.name }}</option>
            </select>
          </label>
          <label>Feature 이름 <input v-model="featureForm.name" placeholder="예: 주문 취소" /></label>
          <label>설명 (선택)
            <textarea v-model="featureForm.description" rows="3" placeholder="이 Feature가 묶는 기능" />
          </label>
          <button
            class="btn btn--primary"
            :disabled="busy || !featureForm.name.trim() || !featureForm.boundedContextId"
            @click="confirmFeature"
          >{{ busy ? '추가 중...' : 'Feature 추가' }}</button>
        </template>

        <!-- Natural-language mode (User Story) -->
        <template v-if="unit === 'userStory' && mode === 'nl'">
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

        <!-- Manual mode (User Story) -->
        <template v-else-if="unit === 'userStory'">
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
.dialog__units {
  display: flex; gap: 4px; padding: 10px 16px 0;
}
.dialog__units button {
  flex: 1; padding: 6px 10px; border: 1px solid var(--color-border); border-radius: 6px;
  cursor: pointer; background: var(--color-bg-tertiary); color: var(--color-text-light);
  font-size: 0.76rem;
}
.dialog__units button.active {
  background: var(--color-accent); color: #fff; border-color: transparent; font-weight: 600;
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
  flex-shrink: 0; /* flex column 본문에서 제안 카드 추가 시 입력란이 수축하지 않도록 */
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
