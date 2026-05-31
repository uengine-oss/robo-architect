<script setup>
import { onMounted, ref, nextTick } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * Conversational (chat) edit panel (035).
 *
 * Per requirement item (Epic/Feature/User Story): the user types NL feedback,
 * an LLM streams its reasoning and proposes a one-shot edit (summary +
 * rationale + field diff + conflicts); the user confirms to apply. Every
 * applied decision is saved to the collaborative History shown below.
 */
const props = defineProps({
  scope: { type: String, required: true }, // 'epic' | 'feature' | 'user-story'
  itemId: { type: String, required: true },
  current: { type: Object, default: () => ({}) }, // editable field values
  baseUpdatedAt: { type: String, default: null },
})
const emit = defineEmits(['applied'])

const store = useRequirementsStore()

const feedback = ref('')
const messages = ref([]) // { role, content, reasoning?, proposal?, applied?, error? }
const streaming = ref(false)
const history = ref([])
const threadEl = ref(null)

const FIELD_LABEL = {
  name: '이름', description: '설명', role: '역할', action: '행동', benefit: '효용',
  priority: '우선순위', status: '상태', acceptanceCriteria: '인수조건',
  edgeCases: 'Edge Cases', assumptions: '가정',
}

onMounted(loadHistory)

async function loadHistory() {
  try {
    history.value = await store.fetchItemHistory(props.scope, props.itemId)
  } catch {
    /* history is best-effort */
  }
}

function fmtVal(v) {
  if (Array.isArray(v)) return v.length ? v.map((x) => `• ${x}`).join('\n') : '(없음)'
  return v === '' || v == null ? '(없음)' : String(v)
}

/** Fields in the proposal that differ from the current values. */
function diffOf(fields) {
  const out = []
  for (const k of Object.keys(fields || {})) {
    const before = props.current[k]
    const after = fields[k]
    const same = Array.isArray(after)
      ? JSON.stringify(before || []) === JSON.stringify(after || [])
      : (before ?? '') === (after ?? '')
    if (!same) out.push({ field: k, label: FIELD_LABEL[k] || k, before, after })
  }
  return out
}

async function scrollDown() {
  await nextTick()
  if (threadEl.value) threadEl.value.scrollTop = threadEl.value.scrollHeight
}

function send() {
  const text = feedback.value.trim()
  if (!text || streaming.value) return
  feedback.value = ''
  const hist = messages.value
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => ({ role: m.role, content: m.content || m.proposal?.summary || '' }))
  messages.value.push({ role: 'user', content: text })
  const aiMsg = ref({ role: 'assistant', content: '', reasoning: [], proposal: null })
  messages.value.push(aiMsg.value)
  streaming.value = true
  scrollDown()

  const url = store.chatEditStreamUrl(props.scope, props.itemId, text, hist)
  const es = new EventSource(url)
  es.addEventListener('progress', (e) => {
    let ev
    try {
      ev = JSON.parse(e.data)
    } catch {
      return
    }
    if (ev.phase === 'reasoning' || ev.phase === 'start') {
      aiMsg.value.reasoning.push(ev.message)
      scrollDown()
    } else if (ev.phase === 'complete') {
      aiMsg.value.proposal = ev.proposal || null
      if (!ev.proposal) aiMsg.value.content = ev.message
      streaming.value = false
      es.close()
      scrollDown()
    }
  })
  es.onerror = () => {
    streaming.value = false
    aiMsg.value.error = '스트림 연결이 끊어졌습니다.'
    es.close()
  }
}

async function applyProposal(msg) {
  const p = msg.proposal
  try {
    const res = await store.chatEditApply(props.scope, props.itemId, {
      fields: p.fields,
      feedback: messages.value.findLast?.((m) => m.role === 'user')?.content || '',
      rationale: p.rationale,
      summary: p.summary,
      baseUpdatedAt: props.baseUpdatedAt,
    })
    msg.applied = res.changed ? 'applied' : 'nochange'
    await loadHistory()
    emit('applied', res)
  } catch (e) {
    msg.error = String(e.message || e)
  }
}
function rejectProposal(msg) {
  msg.applied = 'rejected'
}
</script>

<template>
  <div class="chat-edit">
    <div ref="threadEl" class="ce-thread">
      <p v-if="!messages.length" class="ce-hint">
        자연어로 수정 요청을 입력하세요. 예: “benefit을 더 구체적으로 바꾸고, 인수조건 2개를
        추가해줘.” AI가 제안하면 검토 후 적용합니다.
      </p>

      <template v-for="(m, i) in messages" :key="i">
        <!-- user feedback -->
        <div v-if="m.role === 'user'" class="ce-msg ce-msg--user">{{ m.content }}</div>

        <!-- assistant turn -->
        <div v-else class="ce-msg ce-msg--ai">
          <details v-if="m.reasoning && m.reasoning.length" class="ce-reasoning">
            <summary>🤖 추론 과정 ({{ m.reasoning.length }})</summary>
            <div v-for="(r, j) in m.reasoning" :key="j" class="ce-reason-line">{{ r }}</div>
          </details>

          <div v-if="m.proposal" class="ce-proposal">
            <div class="ce-prop-summary">✨ {{ m.proposal.summary || '제안' }}</div>
            <div v-if="m.proposal.rationale" class="ce-prop-rationale">{{ m.proposal.rationale }}</div>

            <div v-if="(m.proposal.conflicts || []).length" class="ce-conflicts">
              <strong>⚠ 충돌/중복 경고</strong>
              <ul><li v-for="(c, k) in m.proposal.conflicts" :key="k">{{ c }}</li></ul>
            </div>

            <div class="ce-diff">
              <div v-for="d in diffOf(m.proposal.fields)" :key="d.field" class="ce-diff-row">
                <div class="ce-diff-field">{{ d.label }}</div>
                <div class="ce-diff-vals">
                  <pre class="ce-before">{{ fmtVal(d.before) }}</pre>
                  <span class="ce-arrow">→</span>
                  <pre class="ce-after">{{ fmtVal(d.after) }}</pre>
                </div>
              </div>
              <div v-if="!diffOf(m.proposal.fields).length" class="ce-nodiff">변경 사항 없음</div>
            </div>

            <div v-if="!m.applied" class="ce-actions">
              <button class="ce-btn ce-btn--apply" @click="applyProposal(m)">✓ 적용</button>
              <button class="ce-btn" @click="rejectProposal(m)">거부</button>
            </div>
            <div v-else class="ce-applied" :class="m.applied">
              <span v-if="m.applied === 'applied'">✅ 적용됨 — 이력에 기록되었습니다</span>
              <span v-else-if="m.applied === 'nochange'">변경 사항이 없어 적용하지 않았습니다</span>
              <span v-else>거부됨</span>
            </div>
          </div>

          <div v-else-if="m.content" class="ce-plain">{{ m.content }}</div>
          <div v-if="m.error" class="ce-error">{{ m.error }}</div>
        </div>
      </template>

      <div v-if="streaming" class="ce-typing">AI가 작성 중…</div>
    </div>

    <div class="ce-input">
      <textarea
        v-model="feedback"
        class="ce-textarea"
        rows="2"
        placeholder="수정 요청을 자연어로 입력 (Enter 전송 / Shift+Enter 줄바꿈)"
        :disabled="streaming"
        @keydown.enter.exact.prevent="send"
      ></textarea>
      <button class="ce-send" :disabled="streaming || !feedback.trim()" @click="send">전송</button>
    </div>

    <!-- collaborative decision history -->
    <div class="ce-history">
      <div class="ce-history__head">🕘 결정 이력 (협업)</div>
      <div v-if="!history.length" class="ce-hint">아직 편집 이력이 없습니다.</div>
      <ul v-else class="ce-history__list">
        <li v-for="h in history" :key="h.id" class="ce-hist-item">
          <div class="ce-hist-meta">
            <span class="ce-hist-who">{{ h.userName }}</span>
            <span v-if="h.source" class="ce-hist-src" :class="h.source">{{ h.source }}</span>
            <span class="ce-hist-when">{{ (h.timestamp || '').replace('T', ' ').slice(0, 16) }}</span>
          </div>
          <div v-if="h.feedback" class="ce-hist-feedback">💬 {{ h.feedback }}</div>
          <div v-if="h.rationale" class="ce-hist-rationale">{{ h.rationale }}</div>
          <div class="ce-hist-changes">
            <span v-for="(v, f) in h.changes" :key="f" class="ce-hist-chip">{{ FIELD_LABEL[f] || f }}</span>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.chat-edit { display: flex; flex-direction: column; height: 100%; min-height: 0; }
.ce-thread { flex: 1; overflow-y: auto; padding: 10px; display: flex; flex-direction: column; gap: 10px; min-height: 160px; }
.ce-hint { font-size: 0.78rem; color: var(--color-text-light); font-style: italic; margin: 0; }
.ce-msg { max-width: 92%; font-size: 0.82rem; line-height: 1.45; }
.ce-msg--user { align-self: flex-end; background: var(--color-accent, #228be6); color: #fff; padding: 7px 11px; border-radius: 12px 12px 2px 12px; white-space: pre-wrap; }
.ce-msg--ai { align-self: flex-start; width: 100%; }
.ce-reasoning { font-size: 0.74rem; color: var(--color-text-light); margin-bottom: 6px; }
.ce-reasoning summary { cursor: pointer; }
.ce-reason-line { padding: 2px 0 2px 10px; border-left: 2px solid var(--color-border); margin-top: 3px; white-space: pre-wrap; }
.ce-proposal { border: 1px solid var(--color-border); border-radius: 10px; padding: 10px 12px; background: var(--color-bg-tertiary); }
.ce-prop-summary { font-weight: 700; font-size: 0.86rem; }
.ce-prop-rationale { font-size: 0.78rem; color: var(--color-text-light); margin: 4px 0 8px; white-space: pre-wrap; }
.ce-conflicts { font-size: 0.76rem; color: #b35900; background: rgba(255, 196, 0, 0.12); border-radius: 6px; padding: 6px 8px; margin-bottom: 8px; }
.ce-conflicts ul { margin: 4px 0 0; padding-left: 18px; }
.ce-diff { display: flex; flex-direction: column; gap: 6px; }
.ce-diff-row { display: flex; flex-direction: column; gap: 2px; }
.ce-diff-field { font-size: 0.7rem; font-weight: 700; color: var(--color-text-light); text-transform: uppercase; }
.ce-diff-vals { display: grid; grid-template-columns: 1fr auto 1fr; gap: 6px; align-items: start; }
.ce-before, .ce-after { margin: 0; font-size: 0.78rem; white-space: pre-wrap; word-break: break-word; padding: 4px 6px; border-radius: 5px; font-family: inherit; }
.ce-before { background: rgba(224, 49, 49, 0.1); text-decoration: line-through; color: var(--color-text-light); }
.ce-after { background: rgba(64, 192, 87, 0.14); }
.ce-arrow { align-self: center; color: var(--color-text-light); }
.ce-nodiff { font-size: 0.78rem; color: var(--color-text-light); font-style: italic; }
.ce-actions { display: flex; gap: 6px; margin-top: 10px; }
.ce-btn { border: 1px solid var(--color-border); background: var(--color-bg); color: var(--color-text); border-radius: 6px; padding: 4px 12px; font-size: 0.78rem; cursor: pointer; }
.ce-btn--apply { border-color: #40c057; background: #40c057; color: #fff; }
.ce-applied { margin-top: 8px; font-size: 0.78rem; color: #40c057; }
.ce-applied.rejected { color: var(--color-text-light); }
.ce-plain { font-size: 0.82rem; white-space: pre-wrap; }
.ce-error { font-size: 0.76rem; color: #e03131; margin-top: 4px; }
.ce-typing { font-size: 0.74rem; color: var(--color-text-light); font-style: italic; }
.ce-input { display: flex; gap: 6px; padding: 8px; border-top: 1px solid var(--color-border); }
.ce-textarea { flex: 1; resize: none; border: 1px solid var(--color-border); border-radius: 8px; padding: 6px 8px; font-size: 0.82rem; font-family: inherit; background: var(--color-bg); color: var(--color-text); }
.ce-send { border: none; background: var(--color-accent, #228be6); color: #fff; border-radius: 8px; padding: 0 16px; font-size: 0.82rem; cursor: pointer; }
.ce-send:disabled { opacity: 0.5; cursor: default; }
.ce-history { border-top: 1px solid var(--color-border); padding: 8px 10px; max-height: 30%; overflow-y: auto; }
.ce-history__head { font-size: 0.72rem; font-weight: 700; color: var(--color-text-light); text-transform: uppercase; margin-bottom: 6px; }
.ce-history__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.ce-hist-item { border-left: 2px solid var(--color-border); padding-left: 8px; }
.ce-hist-meta { display: flex; align-items: center; gap: 6px; font-size: 0.72rem; }
.ce-hist-who { font-weight: 700; }
.ce-hist-src { font-size: 0.6rem; padding: 0 4px; border-radius: 3px; background: var(--color-bg-tertiary); color: var(--color-text-light); text-transform: uppercase; }
.ce-hist-src.chat { background: rgba(34, 139, 230, 0.18); color: #228be6; }
.ce-hist-when { color: var(--color-text-light); margin-left: auto; }
.ce-hist-feedback { font-size: 0.76rem; margin-top: 2px; }
.ce-hist-rationale { font-size: 0.74rem; color: var(--color-text-light); margin-top: 1px; }
.ce-hist-changes { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.ce-hist-chip { font-size: 0.64rem; padding: 1px 5px; border-radius: 3px; background: var(--color-bg-tertiary); }
</style>
