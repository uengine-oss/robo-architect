<script setup>
// 044 — 완성 설계 Import 모달 (Design 탭 진입점).
// 완성된 이벤트스토밍 설계 문서(마크다운)를 LLM 없이 결정론적으로 파싱→미리보기→적재.
import { ref, computed } from 'vue'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'imported'])

const file = ref(null)
const fileName = ref('')
const mode = ref('replace')
const preview = ref(null)
const busy = ref(false)
const error = ref('')
const done = ref(null)

function reset() {
  file.value = null; fileName.value = ''; preview.value = null
  error.value = ''; done.value = null; busy.value = false
}
function close() { reset(); emit('close') }

function onFile(e) {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  file.value = f; fileName.value = f.name; preview.value = null; done.value = null
}

function formData() {
  const fd = new FormData()
  if (file.value) fd.append('file', file.value)
  fd.append('mode', mode.value)
  return fd
}

async function runPreview() {
  if (!file.value) { error.value = '설계 문서를 선택하세요.'; return }
  busy.value = true; error.value = ''; done.value = null
  try {
    const res = await fetch('/api/graph/design-import/preview', { method: 'POST', body: formData() })
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
    preview.value = await res.json()
  } catch (e) { error.value = String(e.message || e) } finally { busy.value = false }
}

async function runApply() {
  if (!file.value) return
  busy.value = true; error.value = ''
  try {
    const res = await fetch('/api/graph/design-import/apply', { method: 'POST', body: formData() })
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText)
    done.value = await res.json()
    emit('imported', done.value)
  } catch (e) { error.value = String(e.message || e) } finally { busy.value = false }
}

const counts = computed(() => preview.value?.counts || done.value?.counts || null)
</script>

<template>
  <div v-if="open" class="dim-overlay" @click.self="close">
    <div class="dim-modal">
      <header class="dim-head">
        <h3>완성 설계 가져오기 (Design Import)</h3>
        <button class="dim-x" @click="close">×</button>
      </header>

      <p class="dim-sub">
        완성된 이벤트스토밍 설계 문서(BC별 Aggregate·Command·Event·Policy 표가 정리된 마크다운)를
        LLM 재해석 없이 <b>결정론적으로</b> 그래프에 적재합니다.
      </p>

      <div class="dim-row">
        <label class="dim-file">
          <input type="file" accept=".md,.markdown,.txt" @change="onFile" />
          <span>{{ fileName || '파일 선택 (.md)' }}</span>
        </label>
      </div>

      <div class="dim-row dim-mode">
        <label><input type="radio" value="replace" v-model="mode" /> 교체 <small>(기존 모델 비우고 대체)</small></label>
        <label><input type="radio" value="merge" v-model="mode" /> 병합 <small>(기존 모델에 추가)</small></label>
      </div>

      <div class="dim-row">
        <button class="dim-btn" :disabled="busy || !file" @click="runPreview">미리보기</button>
        <button class="dim-btn dim-primary" :disabled="busy || !preview" @click="runApply">적재 확정</button>
      </div>

      <p v-if="error" class="dim-error">{{ error }}</p>

      <div v-if="counts" class="dim-counts">
        <span>BC <b>{{ counts.boundedContexts }}</b></span>
        <span>Aggregate <b>{{ counts.aggregates }}</b></span>
        <span>Command <b>{{ counts.commands }}</b></span>
        <span>Event <b>{{ counts.events }}</b></span>
        <span>Policy <b>{{ counts.policies }}</b></span>
        <span>ReadModel <b>{{ counts.readModels }}</b></span>
        <span>사가 스파인 <b>{{ counts.spine }}</b></span>
      </div>

      <div v-if="preview?.replaceImpact?.boundedContextsRemoved" class="dim-impact">
        ⚠ 교체 시 기존 BC {{ preview.replaceImpact.boundedContextsRemoved }}개가 제거됩니다.
      </div>

      <div v-if="preview && preview.boundedContexts?.length" class="dim-bclist">
        <table>
          <thead><tr><th>Bounded Context</th><th>Agg</th><th>Cmd</th><th>Evt</th><th>Pol</th></tr></thead>
          <tbody>
            <tr v-for="bc in preview.boundedContexts" :key="bc.name">
              <td>{{ bc.display || bc.name }}</td>
              <td>{{ bc.aggregates }}</td><td>{{ bc.commands }}</td>
              <td>{{ bc.events }}</td><td>{{ bc.policies }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <details v-if="(preview?.warnings || done?.warnings || []).length" class="dim-warn">
        <summary>경고 {{ (preview?.warnings || done?.warnings || []).length }}건</summary>
        <ul><li v-for="(w, i) in (preview?.warnings || done?.warnings)" :key="i">{{ w }}</li></ul>
      </details>

      <div v-if="done" class="dim-done">
        ✅ 적재 완료 — {{ done.applied }}개 항목 반영 ({{ done.mode }}). Design 탭을 새로고침합니다.
        <button class="dim-btn dim-primary" @click="close">닫기</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dim-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex;
  align-items: center; justify-content: center; z-index: 4000; }
.dim-modal { width: 620px; max-width: 92vw; max-height: 88vh; overflow: auto; background: #fff;
  border-radius: 12px; padding: 20px 22px; box-shadow: 0 12px 40px rgba(0,0,0,.25); }
.dim-head { display: flex; justify-content: space-between; align-items: center; }
.dim-head h3 { margin: 0; font-size: 17px; }
.dim-x { border: none; background: none; font-size: 24px; cursor: pointer; color: #888; }
.dim-sub { color: #555; font-size: 13px; line-height: 1.5; margin: 6px 0 14px; }
.dim-row { display: flex; gap: 10px; align-items: center; margin: 10px 0; }
.dim-file { border: 1px dashed #bbb; border-radius: 8px; padding: 10px 14px; cursor: pointer;
  flex: 1; color: #444; }
.dim-file input { display: none; }
.dim-mode label { font-size: 13px; margin-right: 16px; }
.dim-mode small { color: #888; }
.dim-btn { padding: 8px 16px; border: 1px solid #ccc; border-radius: 8px; background: #f6f6f6;
  cursor: pointer; font-size: 13px; }
.dim-btn:disabled { opacity: .5; cursor: not-allowed; }
.dim-primary { background: #2563eb; color: #fff; border-color: #2563eb; }
.dim-error { color: #c0392b; font-size: 13px; }
.dim-counts { display: flex; flex-wrap: wrap; gap: 12px; background: #f3f6fb; border-radius: 8px;
  padding: 10px 12px; font-size: 13px; margin: 8px 0; }
.dim-counts b { color: #2563eb; }
.dim-impact { color: #b9770e; font-size: 13px; margin: 6px 0; }
.dim-bclist { max-height: 230px; overflow: auto; margin: 8px 0; }
.dim-bclist table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
.dim-bclist th, .dim-bclist td { border-bottom: 1px solid #eee; padding: 5px 8px; text-align: left; }
.dim-bclist td:not(:first-child) { text-align: center; color: #555; }
.dim-warn { font-size: 12.5px; color: #8a6d3b; margin: 8px 0; }
.dim-warn li { margin: 2px 0; }
.dim-done { background: #eafaf0; border-radius: 8px; padding: 12px; font-size: 13px;
  display: flex; align-items: center; gap: 12px; justify-content: space-between; }
</style>
