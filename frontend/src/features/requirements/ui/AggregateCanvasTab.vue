<script setup>
import { ref, watch } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * Aggregate Design Canvas tab (035 — US5).
 * 그래프 Aggregate 노드의 투영 뷰. 상태전이(Mermaid)/커맨드/이벤트/불변조건/보정정책/throughput.
 * 편집은 속성만 PATCH(관계 보존). 불변조건은 spec 027 표현 재사용.
 */
const props = defineProps({
  aggregateId: { type: String, required: true },
})

const store = useRequirementsStore()
const canvas = ref(null)
const loading = ref(false)
const saving = ref(false)
const errorMsg = ref('')
const editing = ref(false)
const buf = ref({ description: '', stateTransitions: '', invariants: '', correctivePolicies: '', throughput: '' })

async function load() {
  if (!props.aggregateId) return
  loading.value = true
  errorMsg.value = ''
  try {
    canvas.value = await store.fetchAggregateCanvas(props.aggregateId)
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    loading.value = false
  }
}

function startEdit() {
  const c = canvas.value || {}
  buf.value = {
    description: c.description || '',
    stateTransitions: c.stateTransitions || '',
    invariants: (c.invariants || []).join('\n'),
    correctivePolicies: (c.correctivePolicies || []).join('\n'),
    throughput: c.throughput || '',
  }
  editing.value = true
}

function _lines(s) {
  return (s || '').split('\n').map((x) => x.trim()).filter(Boolean)
}

async function save() {
  saving.value = true
  errorMsg.value = ''
  try {
    canvas.value = await store.patchAggregateCanvas(
      props.aggregateId,
      {
        description: buf.value.description,
        stateTransitions: buf.value.stateTransitions,
        invariants: _lines(buf.value.invariants),
        correctivePolicies: _lines(buf.value.correctivePolicies),
        throughput: buf.value.throughput,
      },
      canvas.value?.version,
    )
    editing.value = false
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    saving.value = false
  }
}

watch(() => props.aggregateId, load, { immediate: true })
</script>

<template>
  <div class="agg-canvas">
    <div v-if="loading" class="ac-empty">불러오는 중…</div>
    <template v-else-if="canvas">
      <div class="ac-toolbar">
        <strong class="ac-name">{{ canvas.name }}</strong>
        <span class="ac-spacer" />
        <button v-if="!editing" class="ac-btn" @click="startEdit">✎ 편집</button>
        <button v-if="editing" class="ac-btn primary" @click="save" :disabled="saving">저장</button>
        <button v-if="editing" class="ac-btn" @click="editing = false">취소</button>
      </div>

      <p v-if="errorMsg" class="ac-error">{{ errorMsg }}</p>

      <template v-if="!editing">
        <section class="ac-sec">
          <h4>설명</h4>
          <p v-if="canvas.description">{{ canvas.description }}</p>
          <p v-else class="muted">미정</p>
        </section>
        <section class="ac-sec">
          <h4>상태 전이</h4>
          <pre v-if="canvas.stateTransitions" class="ac-mermaid">{{ canvas.stateTransitions }}</pre>
          <p v-else class="muted">미정</p>
        </section>
        <div class="ac-row">
          <section class="ac-sec">
            <h4>커맨드</h4>
            <ul v-if="canvas.commands?.length"><li v-for="(c, i) in canvas.commands" :key="i">{{ c }}</li></ul>
            <p v-else class="muted">없음</p>
          </section>
          <section class="ac-sec">
            <h4>이벤트</h4>
            <ul v-if="canvas.events?.length"><li v-for="(e, i) in canvas.events" :key="i">{{ e }}</li></ul>
            <p v-else class="muted">없음</p>
          </section>
        </div>
        <section class="ac-sec">
          <h4>불변 조건 (Invariants)</h4>
          <ul v-if="canvas.invariants?.length"><li v-for="(iv, i) in canvas.invariants" :key="i">{{ iv }}</li></ul>
          <p v-else class="muted">없음</p>
        </section>
        <section class="ac-sec">
          <h4>보정 정책</h4>
          <ul v-if="canvas.correctivePolicies?.length"><li v-for="(p, i) in canvas.correctivePolicies" :key="i">{{ p }}</li></ul>
          <p v-else class="muted">없음</p>
        </section>
        <section v-if="canvas.throughput" class="ac-sec">
          <h4>Throughput</h4>
          <p>{{ canvas.throughput }}</p>
        </section>
      </template>

      <template v-else>
        <label class="ac-field"><span>설명</span><textarea v-model="buf.description" rows="2" /></label>
        <label class="ac-field"><span>상태 전이 (Mermaid stateDiagram 소스)</span><textarea v-model="buf.stateTransitions" rows="5" /></label>
        <label class="ac-field"><span>불변 조건 (한 줄에 하나)</span><textarea v-model="buf.invariants" rows="4" /></label>
        <label class="ac-field"><span>보정 정책 (한 줄에 하나)</span><textarea v-model="buf.correctivePolicies" rows="3" /></label>
        <label class="ac-field"><span>Throughput</span><textarea v-model="buf.throughput" rows="2" /></label>
      </template>
    </template>
    <div v-else class="ac-empty">{{ errorMsg || '캔버스를 불러올 수 없습니다.' }}</div>
  </div>
</template>

<style scoped>
.agg-canvas { padding: 10px 4px; }
.ac-toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.ac-name { font-size: 0.9rem; }
.ac-spacer { flex: 1; }
.ac-btn { border: 1px solid var(--color-border); background: var(--color-bg-tertiary); color: var(--color-text); border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer; }
.ac-btn.primary { border-color: var(--color-accent); color: var(--color-accent); }
.ac-btn:hover { filter: brightness(1.1); }
.ac-sec { margin-bottom: 12px; }
.ac-sec h4 { margin: 0 0 4px; font-size: 0.72rem; text-transform: uppercase; color: var(--color-text-light); }
.ac-sec ul { margin: 0; padding-left: 18px; font-size: 0.82rem; }
.ac-sec p { margin: 0; font-size: 0.82rem; white-space: pre-wrap; }
.ac-mermaid { background: var(--color-bg-tertiary); padding: 8px; border-radius: 6px; font-size: 0.74rem; white-space: pre-wrap; overflow-x: auto; }
.ac-row { display: flex; gap: 14px; }
.ac-row .ac-sec { flex: 1; }
.muted { color: var(--color-text-light); font-style: italic; }
.ac-field { display: block; margin-bottom: 8px; }
.ac-field span { display: block; font-size: 0.7rem; color: var(--color-text-light); margin-bottom: 3px; }
.ac-field textarea { width: 100%; box-sizing: border-box; font-size: 0.82rem; padding: 5px 7px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-bg); color: var(--color-text); resize: vertical; font-family: inherit; }
.ac-error { color: #e03131; font-size: 0.76rem; margin: 4px 0; }
.ac-empty { color: var(--color-text-light); font-style: italic; font-size: 0.82rem; padding: 12px 0; }
</style>
