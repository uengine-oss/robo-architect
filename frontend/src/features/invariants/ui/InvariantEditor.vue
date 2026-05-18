<script setup>
/**
 * Invariant property editor (feature 027) — an inline section rendered inside
 * the right-side property panel (`InspectorPanel.vue`), not a modal.
 *
 * Edits the declaration statement and the detailed GWT conditions: an
 * invariant-owned bundle (Given + Then only — `GwtEditor` hides "When" for
 * invariants) and/or shared references to a Command's acceptance criteria.
 */
import { ref, watch } from 'vue'
import { useInvariantsStore } from '../invariants.store'
import { invariantsApi } from '../invariants.api'
import GwtEditor from './GwtEditor.vue'

const props = defineProps({
  invariantId: { type: String, required: true },
})
const emit = defineEmits(['deleted'])

const store = useInvariantsStore()

const detail = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref(null)

const declaration = ref('')
const name = ref('')
const description = ref('')

const candidates = ref([])
const candidatesOpen = ref(false)
const ownGwtOpen = ref(false)
const expandedRefs = ref([])

async function loadDetail() {
  if (!props.invariantId) {
    detail.value = null
    return
  }
  loading.value = true
  error.value = null
  candidatesOpen.value = false
  ownGwtOpen.value = false
  expandedRefs.value = []
  try {
    const d = await invariantsApi.get(props.invariantId)
    detail.value = d
    declaration.value = d.declaration || ''
    name.value = d.name || ''
    description.value = d.description || ''
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}
watch(() => props.invariantId, loadDetail, { immediate: true })

async function refreshAggregate() {
  const aggId = detail.value?.aggregateId
  if (aggId) await store.reload(aggId)
}

async function saveDeclaration() {
  if (!detail.value) return
  saving.value = true
  error.value = null
  try {
    detail.value = await invariantsApi.update(detail.value.id, {
      declaration: declaration.value,
      name: name.value,
      description: description.value,
    })
    await refreshAggregate()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

async function reloadDetail() {
  if (!detail.value) return
  detail.value = await invariantsApi.get(detail.value.id)
  await refreshAggregate()
}

async function openCandidates() {
  candidatesOpen.value = !candidatesOpen.value
  if (candidatesOpen.value && detail.value) {
    try {
      const res = await invariantsApi.referenceCandidates(detail.value.id)
      candidates.value = res.candidates || []
    } catch (e) {
      error.value = e.message || String(e)
    }
  }
}

async function addReference(commandId) {
  try {
    detail.value = await invariantsApi.addReference(detail.value.id, commandId)
    await refreshAggregate()
    candidatesOpen.value = false
  } catch (e) {
    error.value = e.message || String(e)
  }
}

async function removeReference(commandId) {
  try {
    await invariantsApi.removeReference(detail.value.id, commandId)
    await reloadDetail()
  } catch (e) {
    error.value = e.message || String(e)
  }
}

function toggleRef(commandId) {
  const i = expandedRefs.value.indexOf(commandId)
  if (i >= 0) expandedRefs.value.splice(i, 1)
  else expandedRefs.value.push(commandId)
}

async function deleteInvariant() {
  if (!detail.value) return
  if (!confirm('이 인베리언트를 삭제할까요? 공유 참조된 커맨드 GWT는 보존됩니다.')) return
  try {
    const aggId = detail.value.aggregateId
    await invariantsApi.remove(detail.value.id)
    if (aggId) await store.reload(aggId)
    emit('deleted')
  } catch (e) {
    error.value = e.message || String(e)
  }
}
</script>

<template>
  <div class="inv-editor">
    <div v-if="loading" class="inv-editor__hint">불러오는 중…</div>
    <div v-else-if="!detail" class="inv-editor__hint">인베리언트를 찾을 수 없습니다.</div>

    <template v-else>
      <span
        class="inv-editor__status"
        :class="detail.isSpecified ? 'is-specified' : 'is-declaration-only'"
      >
        {{ detail.isSpecified ? '구체화됨' : '선언만 — 세부 조건 없음' }}
      </span>

      <!-- Declaration -->
      <section class="inv-section">
        <h3>선언문</h3>
        <textarea v-model="declaration" rows="2" placeholder="이 어그리거트가 항상 준수해야 하는 규칙" />
        <label class="inv-field">
          <span>제목</span>
          <input v-model="name" placeholder="짧은 제목" />
        </label>
        <label class="inv-field">
          <span>설명</span>
          <textarea v-model="description" rows="2" placeholder="(선택) 부가 설명" />
        </label>
        <div class="inv-section__actions">
          <button class="inv-btn inv-btn--primary" :disabled="saving" @click="saveDeclaration">
            {{ saving ? '저장 중…' : '선언문 저장' }}
          </button>
        </div>
      </section>

      <!-- Invariant-owned GWT (Given + Then only) -->
      <section class="inv-section">
        <h3>
          <button class="inv-disclosure" @click="ownGwtOpen = !ownGwtOpen">
            {{ ownGwtOpen ? '▾' : '▸' }} 인베리언트 전용 조건 (Given · Then)
          </button>
        </h3>
        <p class="inv-section__hint">이 인베리언트에서만 선언되는 조건입니다. "When"은 인베리언트에 해당되지 않아 숨겨집니다.</p>
        <GwtEditor
          v-if="ownGwtOpen"
          parent-type="Invariant"
          :parent-id="detail.id"
          :aggregate-id="detail.aggregateId"
          @saved="reloadDetail"
        />
      </section>

      <!-- Shared references -->
      <section class="inv-section">
        <h3>커맨드 인수조건 공유 참조 ({{ detail.referencedConditions.length }})</h3>
        <p class="inv-section__hint">
          참조한 커맨드의 GWT 인수조건이 이 인베리언트의 검증 조건이 됩니다.
          여기서 편집하면 커맨드 쪽에도 그대로 반영됩니다.
        </p>

        <div v-for="ref in detail.referencedConditions" :key="ref.commandId" class="inv-ref">
          <div class="inv-ref__head">
            <button class="inv-disclosure" @click="toggleRef(ref.commandId)">
              {{ expandedRefs.includes(ref.commandId) ? '▾' : '▸' }} {{ ref.commandName }}
            </button>
            <span v-if="!ref.hasGwt" class="inv-ref__nogwt">GWT 없음</span>
            <button class="inv-btn inv-btn--ghost" @click="removeReference(ref.commandId)">참조 해제</button>
          </div>
          <GwtEditor
            v-if="expandedRefs.includes(ref.commandId)"
            parent-type="Command"
            :parent-id="ref.commandId"
            :aggregate-id="detail.aggregateId"
            @saved="reloadDetail"
          />
        </div>

        <div class="inv-section__actions">
          <button class="inv-btn" @click="openCandidates">
            {{ candidatesOpen ? '닫기' : '+ 커맨드 참조 추가' }}
          </button>
        </div>
        <ul v-if="candidatesOpen" class="inv-candidates">
          <li v-if="candidates.length === 0" class="inv-editor__hint">참조 가능한 커맨드가 없습니다.</li>
          <li v-for="c in candidates" :key="c.commandId">
            <button class="inv-candidate" :disabled="c.alreadyReferenced" @click="addReference(c.commandId)">
              {{ c.commandName }}
              <span v-if="c.alreadyReferenced" class="inv-candidate__tag">참조됨</span>
              <span v-else-if="!c.hasGwt" class="inv-candidate__tag">GWT 없음</span>
            </button>
          </li>
        </ul>
      </section>

      <p v-if="error" class="inv-editor__error">{{ error }}</p>

      <div class="inv-section__actions">
        <button class="inv-btn inv-btn--danger" @click="deleteInvariant">인베리언트 삭제</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.inv-editor { display: flex; flex-direction: column; }
.inv-editor__hint { color: var(--color-text-light); font-size: 0.82rem; padding: 8px 0; }
.inv-editor__error { color: #ff6b6b; font-size: 0.78rem; margin: 8px 0 0; }
.inv-editor__status {
  display: inline-block;
  align-self: flex-start;
  font-size: 0.7rem;
  padding: 2px 8px;
  border-radius: 10px;
  margin-bottom: 10px;
}
.inv-editor__status.is-specified { background: rgba(55, 178, 77, 0.2); color: #51cf66; }
.inv-editor__status.is-declaration-only { background: rgba(245, 159, 0, 0.2); color: #ffa94d; }
.inv-section {
  border-top: 1px solid var(--color-border, #3a3a3a);
  padding: 12px 0;
}
.inv-section:first-of-type { border-top: none; padding-top: 0; }
.inv-section h3 { font-size: 0.82rem; margin: 0 0 6px; }
.inv-section__hint { font-size: 0.72rem; color: var(--color-text-light); margin: 0 0 8px; }
.inv-section__actions { margin-top: 8px; }
.inv-field {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 8px;
  font-size: 0.72rem;
  color: var(--color-text-light);
}
.inv-section textarea,
.inv-field input {
  width: 100%;
  box-sizing: border-box;
  background: var(--color-bg-tertiary, #1e1e1e);
  border: 1px solid var(--color-border, #444);
  border-radius: 4px;
  color: var(--color-text, #eee);
  padding: 6px 8px;
  font-size: 0.82rem;
  font-family: inherit;
  resize: vertical;
}
.inv-disclosure {
  background: transparent;
  border: none;
  color: var(--color-text, #eee);
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0;
}
.inv-ref {
  border: 1px solid var(--color-border, #3a3a3a);
  border-radius: 4px;
  padding: 8px;
  margin-bottom: 6px;
}
.inv-ref__head { display: flex; align-items: center; gap: 8px; }
.inv-ref__head .inv-disclosure { flex: 1; text-align: left; }
.inv-ref__nogwt { font-size: 0.68rem; color: #ffa94d; }
.inv-btn {
  background: var(--color-bg-tertiary, #2a2a2a);
  border: 1px solid var(--color-border, #444);
  border-radius: 4px;
  color: var(--color-text, #eee);
  cursor: pointer;
  padding: 5px 12px;
  font-size: 0.76rem;
}
.inv-btn--primary { background: var(--color-accent, #228be6); border-color: transparent; color: #fff; }
.inv-btn--danger { color: #ff6b6b; }
.inv-btn--ghost { background: transparent; }
.inv-btn:disabled { opacity: 0.5; cursor: default; }
.inv-candidates { list-style: none; padding: 6px 0 0; margin: 0; }
.inv-candidates li { margin-top: 4px; }
.inv-candidate {
  width: 100%;
  text-align: left;
  background: var(--color-bg-tertiary, #1e1e1e);
  border: 1px solid var(--color-border, #444);
  border-radius: 4px;
  color: var(--color-text, #eee);
  cursor: pointer;
  padding: 6px 8px;
  font-size: 0.78rem;
}
.inv-candidate:disabled { opacity: 0.55; cursor: default; }
.inv-candidate__tag { float: right; font-size: 0.66rem; color: var(--color-text-light); }
</style>
