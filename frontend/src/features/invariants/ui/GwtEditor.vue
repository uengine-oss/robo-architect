<script setup>
/**
 * Reusable Given-When-Then bundle editor (feature 027).
 *
 * Parent-agnostic: `parentType` ("Command" | "Policy" | "Invariant") + `parentId`.
 * The editor is *optionalized* — the When row is hidden for `parentType="Invariant"`
 * (an invariant's GWT is Given + Then only; "When" is meaningless for a rule).
 *
 * The Then may declare an Exception outcome — chosen from, or added to, the
 * owning Aggregate's exception domain-object catalog (`aggregateId`). This
 * applies to Command and Invariant GWT alike.
 */
import { ref, computed, watch } from 'vue'
import { invariantsApi } from '../invariants.api'

const props = defineProps({
  parentType: { type: String, required: true },
  parentId: { type: String, required: true },
  aggregateId: { type: String, default: null },
})
const emit = defineEmits(['saved'])

// Optionalized: the When row is hidden for invariant GWT.
const showWhen = computed(() => props.parentType !== 'Invariant')

const loading = ref(false)
const saving = ref(false)
const error = ref(null)
const savedAt = ref(null)

const givenText = ref('')
const whenText = ref('')
const thenText = ref('')
const refsMeta = ref({ given: {}, when: {}, then: {} })
const scenarios = ref([])

// Exception catalog of the owning Aggregate + the Then's chosen exception.
const exceptions = ref([])
const selectedException = ref('')
const newExceptionOpen = ref(false)
const newException = ref({ name: '', message: '', fields: [] })

function parseRef(raw) {
  if (!raw) return {}
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return {}
  }
}

async function loadExceptions() {
  if (!props.aggregateId) return
  try {
    const res = await invariantsApi.getExceptions(props.aggregateId)
    exceptions.value = res.exceptions || []
  } catch {
    exceptions.value = []
  }
}

async function load() {
  if (!props.parentId) return
  loading.value = true
  error.value = null
  try {
    await loadExceptions()
    const res = await invariantsApi.getGwt(props.parentType, props.parentId)
    const gwt = res?.gwt
    const g = parseRef(gwt?.givenRef)
    const w = parseRef(gwt?.whenRef)
    const t = parseRef(gwt?.thenRef)
    givenText.value = g.name || ''
    whenText.value = w.name || ''
    thenText.value = t.name || ''
    selectedException.value = t.exceptionName || ''
    refsMeta.value = { given: g, when: w, then: t }
    let tc = gwt?.testCases
    if (typeof tc === 'string') {
      try { tc = JSON.parse(tc) } catch { tc = [] }
    }
    scenarios.value = Array.isArray(tc) ? tc : []
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

function addScenario() {
  scenarios.value.push({
    scenarioDescription: '',
    givenFieldValues: {},
    whenFieldValues: {},
    thenFieldValues: {},
  })
}
function removeScenario(idx) {
  scenarios.value.splice(idx, 1)
}

function addExceptionField() {
  newException.value.fields.push({ name: '', type: 'String', description: '' })
}
function removeExceptionField(idx) {
  newException.value.fields.splice(idx, 1)
}

async function saveNewException() {
  const name = (newException.value.name || '').trim()
  if (!name) {
    error.value = 'Exception 이름을 입력하세요'
    return
  }
  if (!props.aggregateId) {
    error.value = 'aggregateId가 없어 Exception을 저장할 수 없습니다'
    return
  }
  const next = exceptions.value.filter((e) => e.name !== name)
  next.push({
    name,
    message: newException.value.message || '',
    fields: (newException.value.fields || []).filter((f) => (f.name || '').trim()),
  })
  try {
    const res = await invariantsApi.putExceptions(props.aggregateId, next)
    exceptions.value = res.exceptions || next
    selectedException.value = name
    newExceptionOpen.value = false
    newException.value = { name: '', message: '', fields: [] }
  } catch (e) {
    error.value = e.message || String(e)
  }
}

function buildRef(text, meta, extra = {}) {
  const t = (text || '').trim()
  const hasContent = t || meta?.referencedNodeId || extra.exceptionName
  if (!hasContent) return null
  return {
    name: t,
    referencedNodeId: meta?.referencedNodeId || null,
    referencedNodeType: meta?.referencedNodeType || null,
    ...extra,
  }
}

async function save() {
  saving.value = true
  error.value = null
  try {
    await invariantsApi.upsertGwt({
      parentType: props.parentType,
      parentId: props.parentId,
      givenRef: buildRef(givenText.value, refsMeta.value.given),
      whenRef: showWhen.value ? buildRef(whenText.value, refsMeta.value.when) : null,
      thenRef: buildRef(thenText.value, refsMeta.value.then, {
        exceptionName: selectedException.value || null,
      }),
      testCases: scenarios.value,
    })
    savedAt.value = Date.now()
    emit('saved')
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

watch(() => `${props.parentType}:${props.parentId}`, load, { immediate: true })

defineExpose({ reload: load })
</script>

<template>
  <div class="gwt-editor">
    <div v-if="loading" class="gwt-editor__hint">불러오는 중…</div>
    <template v-else>
      <label class="gwt-editor__field">
        <span class="gwt-editor__tag gwt-editor__tag--given">Given</span>
        <textarea v-model="givenText" rows="2" placeholder="전제 조건 — 어떤 상태에서" />
      </label>

      <label v-if="showWhen" class="gwt-editor__field">
        <span class="gwt-editor__tag gwt-editor__tag--when">When</span>
        <textarea v-model="whenText" rows="2" placeholder="행위 — 무엇이 일어나면" />
      </label>

      <label class="gwt-editor__field">
        <span class="gwt-editor__tag gwt-editor__tag--then">Then</span>
        <textarea v-model="thenText" rows="2" placeholder="결과 — 어떤 결과가 보장되어야 하는가" />
      </label>

      <!-- Then may declare an Exception outcome (027). -->
      <div class="gwt-editor__exception">
        <div class="gwt-editor__exception-head">
          <span class="gwt-editor__tag gwt-editor__tag--exc">Exception</span>
          <select v-model="selectedException">
            <option value="">(예외 없음)</option>
            <option v-for="ex in exceptions" :key="ex.name" :value="ex.name">{{ ex.name }}</option>
          </select>
          <button type="button" @click="newExceptionOpen = !newExceptionOpen">
            {{ newExceptionOpen ? '닫기' : '+ 새 Exception' }}
          </button>
        </div>
        <div v-if="newExceptionOpen" class="gwt-editor__new-exc">
          <input v-model="newException.name" placeholder="Exception 이름 (식별자)" />
          <input v-model="newException.message" placeholder="사용자에게 제시될 메시지" />
          <div class="gwt-editor__exc-fields">
            <div v-for="(f, i) in newException.fields" :key="i" class="gwt-editor__exc-field">
              <input v-model="f.name" placeholder="필드명" />
              <input v-model="f.type" placeholder="타입" />
              <button type="button" class="gwt-editor__remove" @click="removeExceptionField(i)">✕</button>
            </div>
            <button type="button" @click="addExceptionField">+ 필드</button>
          </div>
          <button type="button" class="gwt-editor__save" @click="saveNewException">
            Exception 저장 (어그리거트 카탈로그)
          </button>
        </div>
      </div>

      <div class="gwt-editor__scenarios">
        <div class="gwt-editor__scenarios-head">
          <span>시나리오 ({{ scenarios.length }})</span>
          <button type="button" @click="addScenario">+ 추가</button>
        </div>
        <div v-for="(sc, idx) in scenarios" :key="idx" class="gwt-editor__scenario">
          <input v-model="sc.scenarioDescription" placeholder="시나리오 설명" />
          <button type="button" class="gwt-editor__remove" @click="removeScenario(idx)">✕</button>
        </div>
      </div>

      <div class="gwt-editor__footer">
        <span v-if="error" class="gwt-editor__error">{{ error }}</span>
        <span v-else-if="savedAt" class="gwt-editor__ok">저장됨</span>
        <button type="button" class="gwt-editor__save" :disabled="saving" @click="save">
          {{ saving ? '저장 중…' : 'GWT 저장' }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.gwt-editor { display: flex; flex-direction: column; gap: 8px; }
.gwt-editor__hint { font-size: 0.8rem; color: var(--color-text-light); }
.gwt-editor__field { display: flex; gap: 8px; align-items: flex-start; }
.gwt-editor__tag {
  flex-shrink: 0;
  width: 64px;
  text-align: center;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 4px 0;
  border-radius: 4px;
  color: #fff;
}
.gwt-editor__tag--given { background: #4c6ef5; }
.gwt-editor__tag--when { background: #f59f00; }
.gwt-editor__tag--then { background: #37b24d; }
.gwt-editor__tag--exc { background: #e8590c; }
.gwt-editor__field textarea,
.gwt-editor__scenario input,
.gwt-editor__new-exc input,
.gwt-editor__exception select {
  flex: 1;
  background: var(--color-bg-tertiary, #1e1e1e);
  border: 1px solid var(--color-border, #444);
  border-radius: 4px;
  color: var(--color-text, #eee);
  padding: 6px 8px;
  font-size: 0.82rem;
  font-family: inherit;
  resize: vertical;
}
.gwt-editor__exception { display: flex; flex-direction: column; gap: 6px; }
.gwt-editor__exception-head { display: flex; gap: 6px; align-items: center; }
.gwt-editor__new-exc {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 8px;
  border: 1px dashed var(--color-border, #444);
  border-radius: 4px;
}
.gwt-editor__exc-fields { display: flex; flex-direction: column; gap: 4px; }
.gwt-editor__exc-field { display: flex; gap: 4px; }
.gwt-editor__scenarios-head,
.gwt-editor__exc-fields button {
  font-size: 0.72rem;
  color: var(--color-text-light);
}
.gwt-editor__scenarios-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 4px;
}
.gwt-editor__scenario { display: flex; gap: 6px; margin-top: 4px; }
.gwt-editor__remove,
.gwt-editor__scenarios-head button,
.gwt-editor__exception-head button,
.gwt-editor__exc-fields button {
  background: transparent;
  border: 1px solid var(--color-border, #444);
  border-radius: 4px;
  color: var(--color-text-light);
  cursor: pointer;
  padding: 3px 8px;
  font-size: 0.72rem;
}
.gwt-editor__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 4px;
}
.gwt-editor__error { color: #ff6b6b; font-size: 0.75rem; }
.gwt-editor__ok { color: #37b24d; font-size: 0.75rem; }
.gwt-editor__save {
  background: var(--color-accent, #228be6);
  border: none;
  border-radius: 4px;
  color: #fff;
  cursor: pointer;
  padding: 6px 14px;
  font-size: 0.78rem;
}
.gwt-editor__save:disabled { opacity: 0.5; cursor: default; }
</style>
