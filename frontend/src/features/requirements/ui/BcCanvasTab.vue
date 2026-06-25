<script setup>
import { ref, watch } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * Bounded Context Canvas tab (035 — US3).
 * 그래프 BC 노드의 투영 뷰. 책임/전략분류/유비쿼터스 언어/인·아웃바운드/비즈니스 결정.
 * 편집은 속성만 PATCH(관계 보존, If-Match 낙관버전). 자동생성은 ddd-spec 재사용.
 */
const props = defineProps({
  bcId: { type: String, required: true },
})

const store = useRequirementsStore()
const canvas = ref(null)
const loading = ref(false)
const saving = ref(false)
const errorMsg = ref('')
const editing = ref(false)
// 편집 버퍼(줄바꿈 텍스트 ↔ 배열)
const buf = ref({ purpose: '', ubiquitousLanguage: '', businessDecisions: '', assumptions: '', domainRoles: '' })

const CLASS_BADGE = {
  core: { label: 'Core', color: '#e03131', bg: 'rgba(224,49,49,0.14)' },
  supporting: { label: 'Supporting', color: '#f08c00', bg: 'rgba(240,140,0,0.14)' },
  generic: { label: 'Generic', color: '#868e96', bg: 'rgba(134,142,150,0.14)' },
}

async function load() {
  if (!props.bcId) return
  loading.value = true
  errorMsg.value = ''
  try {
    canvas.value = await store.fetchBcCanvas(props.bcId)
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    loading.value = false
  }
}

function startEdit() {
  const c = canvas.value || {}
  buf.value = {
    purpose: c.purpose || '',
    ubiquitousLanguage: (c.ubiquitousLanguage || []).join('\n'),
    businessDecisions: (c.businessDecisions || []).join('\n'),
    assumptions: (c.assumptions || []).join('\n'),
    domainRoles: (c.domainRoles || []).join('\n'),
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
    canvas.value = await store.patchBcCanvas(
      props.bcId,
      {
        purpose: buf.value.purpose,
        ubiquitousLanguage: _lines(buf.value.ubiquitousLanguage),
        businessDecisions: _lines(buf.value.businessDecisions),
        assumptions: _lines(buf.value.assumptions),
        domainRoles: _lines(buf.value.domainRoles),
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

async function autoGenerate() {
  saving.value = true
  errorMsg.value = ''
  try {
    await store.generateBcCanvas(props.bcId)
    await load() // 생성기는 그래프/스펙을 갱신 → 캔버스 재투영
  } catch (e) {
    errorMsg.value = '자동생성 실패: ' + String(e.message || e)
  } finally {
    saving.value = false
  }
}

watch(() => props.bcId, load, { immediate: true })
</script>

<template>
  <div class="bc-canvas">
    <div v-if="loading" class="bcc-empty">불러오는 중…</div>
    <template v-else-if="canvas">
      <div class="bcc-toolbar">
        <span
          v-if="canvas.classification"
          class="bcc-badge"
          :style="{ color: CLASS_BADGE[canvas.classification]?.color, background: CLASS_BADGE[canvas.classification]?.bg }"
        >{{ CLASS_BADGE[canvas.classification]?.label || canvas.classification }}</span>
        <span class="bcc-spacer" />
        <button v-if="!editing" class="bcc-btn" @click="autoGenerate" :disabled="saving">✨ 자동생성</button>
        <button v-if="!editing" class="bcc-btn" @click="startEdit">✎ 편집</button>
        <button v-if="editing" class="bcc-btn primary" @click="save" :disabled="saving">저장</button>
        <button v-if="editing" class="bcc-btn" @click="editing = false">취소</button>
      </div>

      <p v-if="errorMsg" class="bcc-error">{{ errorMsg }}</p>

      <!-- 읽기 모드 -->
      <template v-if="!editing">
        <section class="bcc-sec">
          <h4>책임 (Purpose)</h4>
          <p v-if="canvas.purpose">{{ canvas.purpose }}</p>
          <p v-else class="muted">미정</p>
        </section>
        <section class="bcc-sec">
          <h4>유비쿼터스 언어</h4>
          <ul v-if="canvas.ubiquitousLanguage?.length"><li v-for="(t, i) in canvas.ubiquitousLanguage" :key="i">{{ t }}</li></ul>
          <p v-else class="muted">없음</p>
        </section>
        <div class="bcc-row">
          <section class="bcc-sec">
            <h4>인바운드</h4>
            <ul v-if="canvas.inbound?.length"><li v-for="(m, i) in canvas.inbound" :key="i">{{ m.otherBcName }} → {{ m.message }}</li></ul>
            <p v-else class="muted">없음</p>
          </section>
          <section class="bcc-sec">
            <h4>아웃바운드</h4>
            <ul v-if="canvas.outbound?.length"><li v-for="(m, i) in canvas.outbound" :key="i">{{ m.message }} → {{ m.otherBcName }}</li></ul>
            <p v-else class="muted">없음</p>
          </section>
        </div>
        <section class="bcc-sec">
          <h4>비즈니스 결정</h4>
          <ul v-if="canvas.businessDecisions?.length"><li v-for="(d, i) in canvas.businessDecisions" :key="i">{{ d }}</li></ul>
          <p v-else class="muted">없음</p>
        </section>
        <section class="bcc-sec">
          <h4>가정</h4>
          <ul v-if="canvas.assumptions?.length"><li v-for="(a, i) in canvas.assumptions" :key="i">{{ a }}</li></ul>
          <p v-else class="muted">없음</p>
        </section>
      </template>

      <!-- 편집 모드 -->
      <template v-else>
        <label class="bcc-field"><span>책임 (Purpose)</span>
          <textarea v-model="buf.purpose" rows="2" /></label>
        <label class="bcc-field"><span>유비쿼터스 언어 (한 줄에 하나)</span>
          <textarea v-model="buf.ubiquitousLanguage" rows="4" /></label>
        <label class="bcc-field"><span>도메인 역할 (한 줄에 하나)</span>
          <textarea v-model="buf.domainRoles" rows="2" /></label>
        <label class="bcc-field"><span>비즈니스 결정 (한 줄에 하나)</span>
          <textarea v-model="buf.businessDecisions" rows="3" /></label>
        <label class="bcc-field"><span>가정 (한 줄에 하나)</span>
          <textarea v-model="buf.assumptions" rows="3" /></label>
      </template>
    </template>
    <div v-else class="bcc-empty">{{ errorMsg || '캔버스를 불러올 수 없습니다.' }}</div>
  </div>
</template>

<style scoped>
.bc-canvas { padding: 10px 4px; }
.bcc-toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.bcc-spacer { flex: 1; }
.bcc-badge { font-size: 0.62rem; font-weight: 700; padding: 2px 7px; border-radius: 10px; }
.bcc-btn { border: 1px solid var(--color-border); background: var(--color-bg-tertiary); color: var(--color-text); border-radius: 6px; font-size: 0.72rem; padding: 3px 8px; cursor: pointer; }
.bcc-btn.primary { border-color: var(--color-accent); color: var(--color-accent); }
.bcc-btn:hover { filter: brightness(1.1); }
.bcc-sec { margin-bottom: 12px; }
.bcc-sec h4 { margin: 0 0 4px; font-size: 0.72rem; text-transform: uppercase; color: var(--color-text-light); }
.bcc-sec ul { margin: 0; padding-left: 18px; font-size: 0.82rem; }
.bcc-sec p { margin: 0; font-size: 0.82rem; white-space: pre-wrap; }
.bcc-row { display: flex; gap: 14px; }
.bcc-row .bcc-sec { flex: 1; }
.muted { color: var(--color-text-light); font-style: italic; }
.bcc-field { display: block; margin-bottom: 8px; }
.bcc-field span { display: block; font-size: 0.7rem; color: var(--color-text-light); margin-bottom: 3px; }
.bcc-field textarea { width: 100%; box-sizing: border-box; font-size: 0.82rem; padding: 5px 7px; border: 1px solid var(--color-border); border-radius: 6px; background: var(--color-bg); color: var(--color-text); resize: vertical; }
.bcc-error { color: #e03131; font-size: 0.76rem; margin: 4px 0; }
.bcc-empty { color: var(--color-text-light); font-style: italic; font-size: 0.82rem; padding: 12px 0; }
</style>
