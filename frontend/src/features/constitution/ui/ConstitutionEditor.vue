<template>
  <div class="cse-backdrop" @click.self="$emit('close')">
    <div class="cse">
      <div class="cse__head">
        <h3 class="cse__title">
          <span class="cse__icon">📜</span>
          {{ scope === 'PROJECT' ? '프로젝트 헌장 (Constitution)' : 'Bounded Context 헌장' }}
          <span v-if="scope === 'BOUNDED_CONTEXT'" class="cse__bc">{{ bcId }}</span>
        </h3>
        <button class="cse__close" @click="$emit('close')" title="닫기">✕</button>
      </div>

      <!-- Plan 게이트 진입(autoInterview) — 왜 지금 헌장을 작성하는지 먼저 설명한다 -->
      <div v-if="autoInterview" class="cse__gate">
        <strong>아직 이 프로젝트의 헌장(Constitution)이 없습니다.</strong>
        Plan(전술 설계·아키텍처)은 프로젝트의 <strong>설계 원칙·기술 스택·모놀리식/마이크로서비스·레포 전략</strong> 위에서 결정됩니다.
        그래서 Plan 을 생성하기 전에 이 헌장을 <strong>한 번</strong> 확정해야 합니다.
        아래에서 Claude Code 가 이 제안(proposal)을 분석해 추천을 제시하며, 인터뷰를 완료하면 <strong>자동으로 Plan 생성이 이어집니다.</strong>
        (이후 보기/수정은 Design 탭의 헌장 진입점에서 합니다.)
      </div>
      <p v-else class="cse__hint">
        헌장은 <strong>하나의 Markdown 문서</strong>입니다. 구획(##)을 나누어 설계 원칙·기술 스택·아키텍처·레포 전략 등을 선언만 하세요.
        저장하면 이 헌장에 의존하는 Proposal Plan 이 stale 로 표시됩니다.
        <template v-if="scope === 'BOUNDED_CONTEXT'">
          <br />이 BC 헌장은 프로젝트-루트 헌장을 <strong>오버라이드</strong>합니다.
          <strong>레포 전략·모놀리식/마이크로서비스 같은 결정은 프로젝트 루트에서만</strong> 정합니다 — 여기서는 이 BC 고유의 설계 원칙·도메인 규칙·기술 선택만 적으세요.
        </template>
      </p>

      <div v-if="loading" class="cse__loading">불러오는 중...</div>

      <!-- ===================== 인터뷰 모드 (Markdown 편집기 숨김) ===================== -->
      <template v-else-if="mode === 'interview'">
        <div class="cse__iv-screen">
          <div v-if="iv.analyzing || iv.synthesizing">
            <div class="cse__iv-status">
              <span class="cse__iv-spinner">●</span>
              {{ iv.synthesizing ? 'Claude Code 가 답변을 바탕으로 헌장을 작성 중입니다…' : 'Claude Code 가 제안(proposal)을 분석하고 있습니다…' }}
            </div>
            <!-- 진행 상태 로그 (백엔드 narration) -->
            <div v-if="iv.logLines?.length" class="cse__iv-log">
              <div v-for="(line, i) in iv.logLines" :key="i" class="cse__iv-logline">{{ line }}</div>
            </div>
          </div>

          <template v-else>
            <div class="cse__iv-status">
              질문 {{ iv.idx + 1 }} / {{ iv.steps.length }}<span v-if="!iv.complete"> (진행 중)</span>
            </div>

            <!-- 현재 질문 -->
            <div v-if="cur" class="cse__iv-q">
              <div class="cse__iv-qtitle">{{ cur.question.question }}</div>
              <div v-if="cur.question.rationale" class="cse__iv-rationale">근거: {{ cur.question.rationale }}</div>
              <div class="cse__iv-opts">
                <button
                  v-for="(opt, oi) in (cur.question.options || [])"
                  :key="oi"
                  class="btn"
                  :class="optVal(opt) === cur.answer ? 'btn--primary' : 'btn--ghost'"
                  @click="store.selectInterviewAnswer(optVal(opt))"
                >{{ optLabel(opt) }}<span v-if="optVal(opt) === cur.question.recommended"> · 추천</span></button>
              </div>
              <input
                v-if="cur.question.allowFree"
                class="cse__input cse__iv-free"
                :value="cur.answer || ''"
                :placeholder="cur.question.placeholder || '직접 입력'"
                @input="store.selectInterviewAnswer($event.target.value)"
              />
            </div>

            <div v-if="iv.error" class="error-msg">{{ iv.error }}</div>

            <!-- 네비게이션 -->
            <div class="cse__iv-nav">
              <button class="btn btn--ghost" :disabled="iv.idx === 0 || iv.busy" @click="store.prevInterviewStep()">← 이전 질문</button>
              <button
                v-if="!(iv.complete && iv.idx === iv.steps.length - 1)"
                class="btn btn--primary"
                :disabled="iv.busy || !cur || (cur.answer == null || cur.answer === '')"
                @click="store.nextInterviewStep()"
              >다음 질문 →</button>
              <button
                v-else
                class="btn btn--primary"
                :disabled="iv.busy"
                @click="store.generateConstitution()"
              >✓ 헌장 생성</button>
            </div>
          </template>

          <div class="cse__actions">
            <button class="btn btn--ghost" @click="cancelInterview">편집기로 돌아가기</button>
          </div>
        </div>
      </template>

      <!-- ===================== 편집 모드 (Markdown) ===================== -->
      <template v-else>
        <!-- 인터뷰로 설정 (프로젝트 루트) — 클릭 시 인터뷰 화면으로 전환 -->
        <div v-if="scope === 'PROJECT'" class="cse__interview-bar">
          <button class="btn btn--ghost" @click="startInterview">🅰️ 인터뷰로 설정</button>
          <span class="cse__interview-hint">Claude Code 가 핵심 질문/추천으로 헌장 초안을 작성합니다 (API 키 불필요).</span>
        </div>

        <!-- 헌장 본문: 기본 뷰(렌더링) ↔ 편집 토글 -->
        <div class="cse__viewbar">
          <label class="cse__label cse__label--block">헌장</label>
          <div class="cse__seg">
            <button class="cse__seg-btn" :class="{ 'is-on': !editing }" @click="editing = false">미리보기</button>
            <button class="cse__seg-btn" :class="{ 'is-on': editing }" @click="editing = true">편집</button>
          </div>
        </div>

        <!-- 뷰 모드: Markdown 렌더링 -->
        <div v-if="!editing" class="cse__rendered" v-html="renderedHtml"></div>
        <!-- 편집 모드: 원문 textarea -->
        <textarea v-else v-model="raw" rows="18" class="cse__editor" :disabled="saving"
                  :placeholder="placeholder"></textarea>

        <!-- BC: 병합된 effective(읽기 전용) -->
        <details v-if="scope === 'BOUNDED_CONTEXT' && effective" class="cse__effective">
          <summary>유효(병합) 헌장 — 프로젝트-루트 + 이 BC 오버라이드</summary>
          <pre v-if="effective.raw" class="cse__eff-raw">{{ effective.raw }}</pre>
          <p v-else class="cse__eff-empty">프로젝트-루트 헌장이 아직 없습니다.</p>
        </details>

        <!-- 042 — 지속 DDD 전략 메모리(차별성·Core/Supporting/Generic·결합 posture·유비쿼터스 언어) -->
        <details v-if="scope === 'PROJECT'" class="cse__memory">
          <summary>전략 메모리 (DDD) — 차별성 · Core/Supporting/Generic · 결합 posture</summary>
          <textarea v-model="memoryJson" rows="10" class="cse__editor" spellcheck="false"
                    placeholder='{"differentiation": {...}, "couplingPosture": {...}, "contexts": {...}}'></textarea>
          <div class="cse__actions">
            <button class="btn btn--secondary" :disabled="savingMemory" @click="saveMemory">
              {{ savingMemory ? '저장 중...' : '전략 메모리 저장' }}
            </button>
            <span v-if="memoryNote" class="cse__saved">✓ 저장됨 (의존 plan 들이 stale 처리됨)</span>
            <span v-if="memoryError" class="error-msg">{{ memoryError }}</span>
          </div>
        </details>

        <div class="cse__actions">
          <button class="btn btn--primary" :disabled="saving" @click="save">
            {{ saving ? '저장 중...' : '저장' }}
          </button>
          <button
            v-if="scope === 'BOUNDED_CONTEXT' && hasOverride"
            class="btn btn--danger"
            :disabled="saving"
            @click="removeOverride"
          >override 제거</button>
          <span v-if="savedNote" class="cse__saved">✓ 저장되었습니다.</span>
        </div>
        <p v-if="error" class="error-msg">{{ error }}</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useConstitutionStore } from '../constitution.store'

const props = defineProps({
  scope: { type: String, required: true }, // 'PROJECT' | 'BOUNDED_CONTEXT'
  bcId: { type: String, default: null },
  // Proposal Plan 게이트가 헌장 부재 시 곧장 인터뷰 화면으로 진입시키려고 쓴다.
  autoInterview: { type: Boolean, default: false },
  // 설정되면 인터뷰가 Claude Code 로 이 제안을 먼저 분석해 추천을 만든다(Plan 게이트).
  proposalId: { type: String, default: null },
})
const emit = defineEmits(['close', 'saved'])

const store = useConstitutionStore()
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const savedNote = ref(false)
const raw = ref('')
const mode = ref('edit')     // 'edit' | 'interview'
const editing = ref(false)   // false = 미리보기(렌더링), true = 편집(원문)
// 042 — 전략 메모리 편집.
const memoryJson = ref('')
const savingMemory = ref(false)
const memoryNote = ref(false)
const memoryError = ref('')

const iv = computed(() => store.interview)
const cur = computed(() => store.interview.steps?.[store.interview.idx] || null)
const effective = computed(() => store.bc?.effective || null)
const hasOverride = computed(() => !!store.bc?.override)

// --- 경량 안전 Markdown 렌더러(헌장 표시용: 제목/목록/인용/굵게/코드) ---
function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function inline(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*]+)\*/g, '$1<em>$2</em>')
}
function renderMarkdown(src) {
  if (!src || !src.trim()) {
    return '<p class="cse__rendered-empty">헌장이 아직 없습니다. 위 <b>편집</b> 또는 <b>인터뷰로 설정</b>으로 작성하세요.</p>'
  }
  const lines = String(src).replace(/\r\n/g, '\n').split('\n')
  const out = []
  let inList = false, inQuote = false, para = []
  const flushPara = () => { if (para.length) { out.push('<p>' + para.map(inline).join('<br>') + '</p>'); para = [] } }
  const closeList = () => { if (inList) { out.push('</ul>'); inList = false } }
  const closeQuote = () => { if (inQuote) { out.push('</blockquote>'); inQuote = false } }
  for (const ln of lines) {
    const t = ln.trimEnd()
    let m
    if ((m = t.match(/^(#{1,6})\s+(.*)$/))) { flushPara(); closeList(); closeQuote(); const lvl = m[1].length; out.push(`<h${lvl}>${inline(m[2])}</h${lvl}>`); continue }
    if ((m = t.match(/^\s*[-*]\s+(.*)$/))) { flushPara(); closeQuote(); if (!inList) { out.push('<ul>'); inList = true } out.push(`<li>${inline(m[1])}</li>`); continue }
    if ((m = t.match(/^>\s?(.*)$/))) { flushPara(); closeList(); if (!inQuote) { out.push('<blockquote>'); inQuote = true } out.push(inline(m[1]) + '<br>'); continue }
    if (t.trim() === '') { flushPara(); closeList(); closeQuote(); continue }
    closeList(); closeQuote(); para.push(t)
  }
  flushPara(); closeList(); closeQuote()
  return out.join('\n')
}
const renderedHtml = computed(() => renderMarkdown(raw.value))

const placeholder = computed(() => props.scope === 'PROJECT'
  ? '# 프로젝트 헌장\n\n## 설계 원칙\n- DDD, 이벤트 드리븐\n\n## 기술 스택\n- Backend: ...\n- Frontend: ...\n\n## 아키텍처\n- Style: MONOLITH | MICROSERVICES\n\n## 레포 전략\n- MONO_REPO | REPO_PER_SERVICE\n'
  : `# ${props.bcId} 헌장 (오버라이드)\n\n## 설계 원칙\n- 이 BC 고유 규칙...\n\n## 기술 선택\n- 이 BC 한정...\n`)

onMounted(async () => {
  loading.value = true
  try {
    if (props.scope === 'PROJECT') {
      const data = await store.getProjectConstitution()
      raw.value = data?.raw || ''
      memoryJson.value = data?.strategicMemory ? JSON.stringify(data.strategicMemory, null, 2) : ''
    } else {
      const data = await store.getBcConstitution(props.bcId)
      raw.value = data?.override?.raw || ''
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
  // Plan 게이트에서 진입(autoInterview)했고 아직 헌장이 없으면 곧장 인터뷰 시작.
  if (props.autoInterview && props.scope === 'PROJECT' && !raw.value.trim()) {
    startInterview()
  }
})

// 인터뷰가 끝나면(최종 done) 편집기로 전환하고 생성된 본문을 채운다.
// 헌장은 이 시점에 백엔드에 이미 저장되었으므로 'saved' 를 올려 게이트(Plan)를 풀게 한다.
watch(() => store.interview.done, (done) => {
  if (done && mode.value === 'interview') {
    raw.value = store.project?.raw || raw.value
    mode.value = 'edit'
    emit('saved', { scope: 'PROJECT', bcId: null })
  }
})

async function saveMemory() {
  memoryError.value = ''
  memoryNote.value = false
  let parsed
  try { parsed = memoryJson.value.trim() ? JSON.parse(memoryJson.value) : {} }
  catch { memoryError.value = 'JSON 형식 오류'; return }
  savingMemory.value = true
  try {
    await store.saveProjectStrategicMemory(parsed)
    memoryNote.value = true
    emit('saved', { scope: 'PROJECT', bcId: null })
  } catch (e) { memoryError.value = e.message } finally { savingMemory.value = false }
}

function optVal(opt) { return typeof opt === 'object' ? (opt.value ?? opt.label) : opt }
function optLabel(opt) { return typeof opt === 'object' ? (opt.label ?? opt.value) : opt }

// 인터뷰 화면으로 전환 + 새 인터뷰 시작(이전 답변 초기화; Markdown 편집기는 숨겨진다).
function startInterview() {
  mode.value = 'interview'
  // proposalId 가 있으면 Claude Code 가 제안을 먼저 분석한다(Plan 게이트).
  store.startProjectInterview(props.proposalId)
}
function cancelInterview() {
  store.stopProjectInterview()
  mode.value = 'edit'
}

async function save() {
  error.value = ''
  savedNote.value = false
  saving.value = true
  try {
    if (props.scope === 'PROJECT') {
      await store.saveProjectConstitution(raw.value)
    } else {
      await store.saveBcConstitution(props.bcId, { raw: raw.value })
    }
    savedNote.value = true
    emit('saved', { scope: props.scope, bcId: props.bcId })
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

async function removeOverride() {
  error.value = ''
  saving.value = true
  try {
    await store.deleteBcConstitution(props.bcId)
    raw.value = ''
    savedNote.value = true
    emit('saved', { scope: props.scope, bcId: props.bcId })
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.cse-backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 1300; display: flex; align-items: center; justify-content: center; }
.cse { width: 680px; max-width: calc(100vw - 32px); max-height: calc(100vh - 48px); overflow-y: auto; background: var(--color-bg-secondary); border-radius: 12px; padding: 18px 20px; border: 1px solid var(--color-border); }
.cse__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.cse__title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 0; font-size: 15px; color: var(--color-text-bright); }
.cse__icon { font-size: 1.1rem; }
.cse__bc { font-family: monospace; font-size: 12px; color: var(--color-text-light); background: var(--color-bg-tertiary); padding: 2px 6px; border-radius: 3px; }
.cse__close { background: none; border: none; cursor: pointer; color: var(--color-text-light); font-size: 14px; }
.cse__close:hover { color: var(--color-text); }
.cse__hint { font-size: 12px; color: var(--color-text-light); line-height: 1.5; margin: 0 0 12px; }
.cse__gate { font-size: 13px; color: var(--color-text); line-height: 1.6; margin: 0 0 14px; padding: 12px 14px; background: var(--status-blue-bg); border-radius: 8px; }
.cse__gate strong { color: var(--color-text-bright); }
.cse__loading { color: var(--color-text-light); padding: 24px 0; font-style: italic; }
.cse__interview-bar { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.cse__interview-hint { font-size: 11px; color: var(--color-text-light); }
.cse__interview { border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; margin-bottom: 12px; background: var(--color-bg); max-height: 300px; overflow-y: auto; }
.cse__iv-line { font-size: 12px; color: var(--color-text-light); line-height: 1.5; }
.cse__iv-screen { min-height: 200px; }
.cse__iv-status { font-size: 12px; font-weight: 600; color: var(--color-text); margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
.cse__iv-spinner { color: var(--color-accent); animation: cse-pulse 1s ease-in-out infinite; }
@keyframes cse-pulse { 0%,100% { opacity: 0.3; } 50% { opacity: 1; } }
.cse__iv-log { margin-top: 10px; background: #0f172a; border-radius: 6px; padding: 10px 12px; max-height: 240px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #cbd5e1; }
.cse__iv-logline { padding: 1px 0; white-space: pre-wrap; word-break: break-word; line-height: 1.5; }
.cse__iv-q { margin-top: 8px; border: 1px solid var(--color-accent); border-radius: 6px; padding: 12px; background: var(--color-bg); }
.cse__iv-qtitle { font-size: 14px; font-weight: 700; color: var(--color-text-bright); margin-bottom: 4px; }
.cse__iv-rationale { font-size: 12px; color: var(--color-text-light); margin-bottom: 8px; }
.cse__iv-opts { display: flex; gap: 8px; flex-wrap: wrap; }
.cse__iv-free { width: 100%; margin-top: 8px; }
.cse__iv-nav { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 14px; }
.cse__input { font-size: 13px; border: 1px solid var(--color-border); border-radius: 4px; padding: 6px 8px; background: var(--color-bg); color: var(--color-text); box-sizing: border-box; }
.cse__label { font-size: 12px; font-weight: 600; color: var(--color-text); }
.cse__label--block { display: block; margin: 6px 0 4px; }
.cse__editor { width: 100%; font-family: monospace; font-size: 12px; border: 1px solid var(--color-border); border-radius: 4px; padding: 8px; background: var(--color-bg); color: var(--color-text); box-sizing: border-box; resize: vertical; min-height: 280px; }
/* 뷰/편집 토글 */
.cse__viewbar { display: flex; align-items: center; justify-content: space-between; margin: 6px 0 6px; }
.cse__seg { display: inline-flex; border: 1px solid var(--color-border); border-radius: 6px; overflow: hidden; }
.cse__seg-btn { padding: 4px 12px; font-size: 12px; background: var(--color-bg); color: var(--color-text-light); border: none; cursor: pointer; }
.cse__seg-btn.is-on { background: var(--color-accent); color: #fff; font-weight: 600; }
/* 렌더링된 헌장 */
.cse__rendered { border: 1px solid var(--color-border); border-radius: 6px; padding: 12px 16px; background: var(--color-bg); color: var(--color-text); min-height: 280px; max-height: 460px; overflow-y: auto; font-size: 13px; line-height: 1.6; }
.cse__rendered :deep(h1) { font-size: 18px; font-weight: 700; margin: 4px 0 10px; color: var(--color-text-bright); }
.cse__rendered :deep(h2) { font-size: 15px; font-weight: 700; margin: 16px 0 8px; color: var(--color-text-bright); border-bottom: 1px solid var(--color-border); padding-bottom: 4px; }
.cse__rendered :deep(h3) { font-size: 13px; font-weight: 700; margin: 12px 0 4px; color: var(--color-text); }
.cse__rendered :deep(p) { margin: 6px 0; }
.cse__rendered :deep(ul) { margin: 6px 0; padding-left: 20px; }
.cse__rendered :deep(li) { margin: 2px 0; }
.cse__rendered :deep(blockquote) { margin: 8px 0; padding: 6px 12px; border-left: 3px solid var(--color-accent); background: var(--color-bg-secondary); color: var(--color-text-light); }
.cse__rendered :deep(code) { font-family: monospace; font-size: 12px; background: var(--color-bg-tertiary); padding: 1px 5px; border-radius: 3px; }
.cse__rendered :deep(strong) { color: var(--color-text-bright); }
.cse__rendered :deep(.cse__rendered-empty) { color: var(--color-text-light); font-style: italic; }
.cse__effective { margin: 12px 0; border: 1px solid var(--color-border); border-radius: 6px; padding: 8px 10px; background: var(--color-bg); }
.cse__effective summary { font-size: 12px; font-weight: 600; cursor: pointer; color: var(--color-text-light); }
.cse__eff-raw { white-space: pre-wrap; word-break: break-word; font-size: 11px; font-family: monospace; color: var(--color-text); margin: 8px 0 0; max-height: 240px; overflow-y: auto; }
.cse__eff-empty { font-size: 12px; color: var(--color-text-light); margin: 8px 0 0; }
.cse__actions { margin-top: 14px; display: flex; align-items: center; gap: 10px; }
.cse__saved { color: var(--color-success); font-size: 12px; font-weight: 600; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--sm { padding: 4px 10px; font-size: 12px; }
.btn:disabled { opacity: 0.5; cursor: default; }
.btn--primary { background: var(--color-accent); color: #fff; }
.btn--ghost { background: var(--color-bg-tertiary); color: var(--color-text); border: 1px solid var(--color-border); }
.btn--danger { background: var(--status-red-bg); color: var(--status-red-fg); }
.error-msg { color: var(--color-danger); font-size: 12px; margin-top: 6px; }
</style>
