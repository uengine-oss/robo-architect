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
 *
 * UI mirrors the Design tab's chat (modelModifier/ui/ChatPanel.vue) — same
 * header, message bubbles, entity chip, and input/send styling — so the two
 * chat surfaces feel like one consistent component.
 */
const props = defineProps({
  scope: { type: String, required: true }, // 'epic' | 'feature' | 'user-story'
  itemId: { type: String, required: true },
  itemName: { type: String, default: '' },
  current: { type: Object, default: () => ({}) }, // editable field values
  baseUpdatedAt: { type: String, default: null },
})
const emit = defineEmits(['applied'])

const store = useRequirementsStore()

const inputText = ref('')
const messages = ref([]) // { role, content, reasoning?, proposal?, applied?, error? }
const streaming = ref(false)
const history = ref([])
const messagesContainer = ref(null)

const FIELD_LABEL = {
  name: '이름', description: '설명', role: '역할', action: '행동', benefit: '효용',
  priority: '우선순위', status: '상태', acceptanceCriteria: '인수조건',
  edgeCases: 'Edge Cases', assumptions: '가정',
}
const SCOPE_META = {
  epic: { label: 'EPIC', color: '#5c7cfa' },
  feature: { label: 'FEAT', color: '#9c36b5' },
  'user-story': { label: 'US', color: '#40c057' },
}

// A history entry comes from a descendant item (e.g. a Feature view showing a
// child US's edit) when its owning item differs from the panel's item.
function fromChild(h) {
  return h.itemId && h.itemId !== props.itemId
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
    if (!(k in FIELD_LABEL)) continue
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
  if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
}

function send() {
  const text = inputText.value.trim()
  if (!text || streaming.value) return
  inputText.value = ''
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

function handleKeyDown(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}

async function applyProposal(msg) {
  const p = msg.proposal
  const lastUser = [...messages.value].reverse().find((m) => m.role === 'user')
  try {
    const res = await store.chatEditApply(props.scope, props.itemId, {
      fields: p.fields,
      feedback: lastUser?.content || '',
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
function clearMessages() {
  messages.value = []
}
function when(iso) {
  return (iso || '').replace('T', ' ').slice(0, 16)
}
</script>

<template>
  <div class="chat-panel">
    <div class="chat-panel__header">
      <div class="chat-panel__title">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <span>Chat</span>
      </div>
      <div class="chat-panel__header-actions">
        <button v-if="messages.length" class="chat-panel__clear-btn" title="대화 비우기" @click="clearMessages">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      </div>
    </div>

    <div ref="messagesContainer" class="chat-panel__messages">
      <div v-if="!messages.length" class="chat-empty">
        <div class="chat-empty__icon">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </div>
        <div class="chat-empty__text">
          수정 요청을 자연어로 입력하세요
        </div>
        <div class="chat-empty__hint">
          예: "benefit을 더 구체적으로 바꾸고 인수조건 2개를 추가해줘" — AI가 제안하면 검토 후 적용합니다
        </div>
      </div>

      <div v-else class="chat-messages">
        <div v-for="(m, i) in messages" :key="i" :class="['chat-message', `chat-message--${m.role}`, { 'chat-message--error': m.error }]">
          <!-- user feedback -->
          <div v-if="m.role === 'user'" class="chat-message__content">{{ m.content }}</div>

          <!-- assistant turn -->
          <div v-else class="chat-message__content">
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

              <div v-if="!m.applied" class="chat-drafts__footer ce-actions">
                <button class="ce-btn" @click="rejectProposal(m)">거부</button>
                <button class="chat-drafts__apply" @click="applyProposal(m)">✓ 적용</button>
              </div>
              <div v-else class="ce-applied" :class="m.applied">
                <span v-if="m.applied === 'applied'">✅ 적용됨 — 이력에 기록되었습니다</span>
                <span v-else-if="m.applied === 'nochange'">변경 사항이 없어 적용하지 않았습니다</span>
                <span v-else>거부됨</span>
              </div>
            </div>

            <div v-else-if="m.content">{{ m.content }}</div>
            <div v-if="m.error" class="ce-error">{{ m.error }}</div>
          </div>
        </div>

        <div v-if="streaming" class="chat-processing">
          <div class="chat-processing__indicator">
            <span class="chat-processing__dot"></span>
            <span class="chat-processing__dot"></span>
            <span class="chat-processing__dot"></span>
          </div>
          <div class="chat-processing__thought">AI가 작성 중…</div>
        </div>
      </div>
    </div>

    <div class="chat-panel__input-area">
      <div class="chat-input__chips">
        <span class="chat-chip" :style="{ borderColor: (SCOPE_META[scope] || {}).color }">
          <span class="chat-chip__icon" :style="{ background: (SCOPE_META[scope] || {}).color }">
            {{ (SCOPE_META[scope] || {}).label }}
          </span>
          <span class="chat-chip__name">{{ itemName || '편집 대상' }}</span>
        </span>
      </div>

      <div class="chat-input__wrapper">
        <textarea
          v-model="inputText"
          class="chat-input__textarea"
          placeholder="수정 요청을 입력하세요..."
          :disabled="streaming"
          rows="1"
          @keydown="handleKeyDown"
        ></textarea>
        <button class="chat-input__send" :disabled="!inputText.trim() || streaming" @click="send">
          <svg v-if="!streaming" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="animate-spin">
            <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12"></circle>
          </svg>
        </button>
      </div>
    </div>

    <!-- collaborative decision history -->
    <div class="ce-history">
      <div class="ce-history__head">
        🕘 결정 이력 (협업)
        <span v-if="scope !== 'user-story'" class="ce-history__sub">— 하위 항목 수정 포함</span>
      </div>
      <div v-if="!history.length" class="ce-history__empty">아직 편집 이력이 없습니다.</div>
      <ul v-else class="ce-history__list">
        <li v-for="h in history" :key="h.id" class="ce-hist-item" :class="{ 'is-child': fromChild(h) }">
          <div v-if="fromChild(h)" class="ce-hist-from">
            <span class="ce-hist-from-badge" :style="{ background: (SCOPE_META[h.itemScope] || {}).color }">
              {{ (SCOPE_META[h.itemScope] || {}).label || '항목' }}
            </span>
            <span class="ce-hist-from-name">{{ h.itemName }}</span>
          </div>
          <div class="ce-hist-meta">
            <span class="ce-hist-who">{{ h.userName }}</span>
            <span v-if="h.source" class="ce-hist-src" :class="h.source">{{ h.source }}</span>
            <span class="ce-hist-when">{{ when(h.timestamp) }}</span>
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
/* ── shared shell (mirrors modelModifier/ui/ChatPanel.vue) ───────────── */
.chat-panel { display: flex; flex-direction: column; height: 100%; min-height: 0; background: var(--color-bg-secondary); }
.chat-panel__header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border); background: var(--color-bg-tertiary); flex-shrink: 0;
}
.chat-panel__title { display: flex; align-items: center; gap: var(--spacing-sm); font-size: 0.875rem; font-weight: 600; color: var(--color-text-bright); }
.chat-panel__header-actions { display: flex; align-items: center; gap: 4px; }
.chat-panel__clear-btn { background: none; border: none; color: var(--color-text-light); cursor: pointer; padding: 4px; border-radius: var(--radius-sm); display: flex; align-items: center; }
.chat-panel__clear-btn:hover { background: var(--color-bg); color: var(--color-text); }
.chat-panel__messages { flex: 1; overflow-y: auto; padding: var(--spacing-md); min-height: 140px; }
.chat-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; color: var(--color-text-light); }
.chat-empty__icon { margin-bottom: var(--spacing-md); }
.chat-empty__text { font-size: 0.875rem; line-height: 1.5; margin-bottom: var(--spacing-sm); }
.chat-empty__hint { font-size: 0.75rem; opacity: 0.7; max-width: 260px; }
.chat-messages { display: flex; flex-direction: column; gap: var(--spacing-md); }
.chat-message { padding: var(--spacing-sm) var(--spacing-md); border-radius: var(--radius-md); animation: slideIn 0.2s ease; }
@keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
.chat-message--user { background: var(--color-bg-tertiary); border: 1px solid var(--color-border); align-self: flex-end; max-width: 90%; }
.chat-message--assistant { background: linear-gradient(135deg, rgba(34, 139, 230, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%); border: 1px solid rgba(34, 139, 230, 0.2); }
.chat-message--error { background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3); }
.chat-message__content { font-size: 0.84rem; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }

.chat-processing { padding: var(--spacing-md); text-align: center; }
.chat-processing__indicator { display: flex; justify-content: center; gap: 4px; margin-bottom: var(--spacing-sm); }
.chat-processing__dot { width: 8px; height: 8px; background: var(--color-accent); border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }
.chat-processing__dot:nth-child(1) { animation-delay: -0.32s; }
.chat-processing__dot:nth-child(2) { animation-delay: -0.16s; }
@keyframes bounce { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
.chat-processing__thought { font-size: 0.75rem; color: var(--color-text-light); }

.chat-panel__input-area { padding: var(--spacing-sm) var(--spacing-md); border-top: 1px solid var(--color-border); background: var(--color-bg); flex-shrink: 0; }
.chat-input__chips { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: var(--spacing-sm); }
.chat-chip { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px 2px 2px; background: var(--color-bg-tertiary); border: 1px solid; border-radius: 16px; font-size: 0.75rem; color: var(--color-text); }
.chat-chip__icon { min-width: 18px; height: 18px; padding: 0 4px; display: flex; align-items: center; justify-content: center; border-radius: 9px; font-size: 0.54rem; font-weight: 700; color: #fff; }
.chat-chip__name { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chat-input__wrapper { display: flex; align-items: flex-end; gap: var(--spacing-sm); background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: var(--spacing-xs); transition: border-color 0.15s ease; }
.chat-input__wrapper:focus-within { border-color: var(--color-accent); }
.chat-input__textarea { flex: 1; background: transparent; border: none; color: var(--color-text); font-family: inherit; font-size: 0.875rem; resize: none; padding: var(--spacing-xs); min-height: 36px; max-height: 120px; }
.chat-input__textarea:focus { outline: none; }
.chat-input__textarea::placeholder { color: var(--color-text-light); }
.chat-input__textarea:disabled { opacity: 0.5; cursor: not-allowed; }
.chat-input__send { width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: var(--color-accent); border: none; border-radius: var(--radius-sm); color: #fff; cursor: pointer; transition: all 0.15s ease; flex-shrink: 0; }
.chat-input__send:hover:not(:disabled) { background: #1c7ed6; transform: scale(1.05); }
.chat-input__send:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
.animate-spin { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* ── proposal card + diff (feature-specific) ────────────────────────── */
.ce-reasoning { font-size: 0.74rem; color: var(--color-text-light); margin-bottom: 6px; }
.ce-reasoning summary { cursor: pointer; }
.ce-reason-line { padding: 2px 0 2px 10px; border-left: 2px solid var(--color-border); margin-top: 3px; white-space: pre-wrap; }
.ce-proposal { border: 1px solid var(--color-border); border-radius: 10px; padding: 10px 12px; background: rgba(0, 0, 0, 0.18); margin-top: 4px; }
.ce-prop-summary { font-weight: 700; font-size: 0.86rem; }
.ce-prop-rationale { font-size: 0.78rem; color: var(--color-text-light); margin: 4px 0 8px; }
.ce-conflicts { font-size: 0.76rem; color: #ffb84d; background: rgba(255, 196, 0, 0.12); border-radius: 6px; padding: 6px 8px; margin-bottom: 8px; }
.ce-conflicts ul { margin: 4px 0 0; padding-left: 18px; }
.ce-diff { display: flex; flex-direction: column; gap: 6px; }
.ce-diff-row { display: flex; flex-direction: column; gap: 2px; }
.ce-diff-field { font-size: 0.7rem; font-weight: 700; color: var(--color-text-light); text-transform: uppercase; }
.ce-diff-vals { display: grid; grid-template-columns: 1fr auto 1fr; gap: 6px; align-items: start; }
.ce-before, .ce-after { margin: 0; font-size: 0.76rem; white-space: pre-wrap; word-break: break-word; padding: 4px 6px; border-radius: 5px; font-family: inherit; }
.ce-before { background: rgba(224, 49, 49, 0.14); text-decoration: line-through; color: var(--color-text-light); }
.ce-after { background: rgba(64, 192, 87, 0.16); }
.ce-arrow { align-self: center; color: var(--color-text-light); }
.ce-nodiff { font-size: 0.78rem; color: var(--color-text-light); font-style: italic; }
.chat-drafts__footer.ce-actions { display: flex; justify-content: flex-end; gap: 6px; margin-top: 10px; }
.chat-drafts__apply { background: var(--color-accent); border: none; color: #fff; padding: 5px 12px; border-radius: 8px; font-size: 0.78rem; cursor: pointer; }
.ce-btn { border: 1px solid var(--color-border); background: var(--color-bg); color: var(--color-text); border-radius: 8px; padding: 5px 12px; font-size: 0.78rem; cursor: pointer; }
.ce-applied { margin-top: 8px; font-size: 0.78rem; color: #40c057; }
.ce-applied.rejected { color: var(--color-text-light); }
.ce-error { font-size: 0.76rem; color: #ff6b6b; margin-top: 4px; }

/* ── collaborative history ──────────────────────────────────────────── */
.ce-history { border-top: 1px solid var(--color-border); padding: 8px 12px; max-height: 30%; overflow-y: auto; flex-shrink: 0; background: var(--color-bg-secondary); }
.ce-history__head { font-size: 0.72rem; font-weight: 700; color: var(--color-text-light); text-transform: uppercase; margin-bottom: 6px; }
.ce-history__empty { font-size: 0.76rem; color: var(--color-text-light); font-style: italic; }
.ce-history__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.ce-hist-item { border-left: 2px solid var(--color-border); padding-left: 8px; }
.ce-hist-item.is-child { border-left-color: var(--color-accent, #228be6); }
.ce-history__sub { font-weight: 400; text-transform: none; opacity: 0.7; margin-left: 4px; }
.ce-hist-from { display: flex; align-items: center; gap: 5px; margin-bottom: 2px; }
.ce-hist-from-badge { font-size: 0.56rem; font-weight: 700; color: #fff; padding: 0 5px; border-radius: 3px; }
.ce-hist-from-name { font-size: 0.72rem; color: var(--color-text-light); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ce-hist-meta { display: flex; align-items: center; gap: 6px; font-size: 0.72rem; }
.ce-hist-who { font-weight: 700; }
.ce-hist-src { font-size: 0.6rem; padding: 0 4px; border-radius: 3px; background: var(--color-bg-tertiary); color: var(--color-text-light); text-transform: uppercase; }
.ce-hist-src.chat { background: rgba(34, 139, 230, 0.18); color: #74c0fc; }
.ce-hist-when { color: var(--color-text-light); margin-left: auto; }
.ce-hist-feedback { font-size: 0.76rem; margin-top: 2px; }
.ce-hist-rationale { font-size: 0.74rem; color: var(--color-text-light); margin-top: 1px; }
.ce-hist-changes { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 4px; }
.ce-hist-chip { font-size: 0.64rem; padding: 1px 5px; border-radius: 3px; background: var(--color-bg-tertiary); }
</style>
