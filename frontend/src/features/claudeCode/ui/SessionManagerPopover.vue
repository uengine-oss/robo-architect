<template>
  <div class="smp-backdrop" @keydown.esc.window="$emit('close')">
    <div class="smp" role="dialog" aria-label="Claude Code 세션 매니저">
      <header class="smp__head">
        <div class="smp__title">
          Claude Code 세션
          <span class="smp__count" :class="{ 'smp__count--full': count >= max }">{{ count }} / {{ max }}</span>
        </div>
        <div class="smp__head-actions">
          <button class="smp__icon-btn" title="새로고침" :disabled="loading" @click="refresh">⟳</button>
          <button class="smp__icon-btn" title="닫기" @click="$emit('close')">×</button>
        </div>
      </header>

      <p class="smp__hint">
        백엔드가 살아있다고 보고하는 모든 <code>claude</code> PTY 프로세스입니다. 탭에서 안 보여도
        여기서 정리할 수 있습니다. ({{ ttlMinutes }}분 이상 분리되면 자동 정리)
      </p>

      <div v-if="loading && !sessions.length" class="smp__loading">불러오는 중…</div>
      <div v-else-if="!sessions.length" class="smp__empty">실행 중인 세션이 없습니다.</div>

      <ul v-else class="smp__list">
        <li v-for="s in sessions" :key="s.sessionId" class="smp__row">
          <span class="smp__dot" :class="s.attached ? 'is-attached' : 'is-detached'"
                :title="s.attached ? '화면에 연결됨' : '분리됨(보이지 않음)'"></span>
          <div class="smp__row-main">
            <div class="smp__row-id" :title="s.sessionId">{{ s.sessionId }}</div>
            <div class="smp__row-meta">
              <span class="smp__pid">PID {{ s.pid }}</span>
              <span v-if="s.cwd" class="smp__cwd" :title="s.cwd">{{ basename(s.cwd) }}</span>
              <span v-if="!s.attached && s.idleSeconds != null" class="smp__idle">분리 {{ fmtIdle(s.idleSeconds) }}</span>
              <span v-else class="smp__attached-tag">연결됨</span>
            </div>
          </div>
          <button class="smp__kill" title="이 세션 종료" :disabled="busyId === s.sessionId"
                  @click="kill(s.sessionId)">종료</button>
        </li>
      </ul>

      <footer v-if="detachedCount" class="smp__foot">
        <button class="smp__reap" :disabled="loading" @click="reap">
          분리된 세션 {{ detachedCount }}개 정리
        </button>
      </footer>

      <p v-if="error" class="smp__error">{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { fetchTerminalSessions, closeTerminalSession, reapDetachedSessions } from '../workspace.api'

const emit = defineEmits(['close', 'changed'])

const sessions = ref([])
const count = ref(0)
const max = ref(16)
const ttlSeconds = ref(1800)
const loading = ref(false)
const error = ref('')
const busyId = ref(null)
let timer = null

const ttlMinutes = computed(() => Math.round(ttlSeconds.value / 60))
const detachedCount = computed(() => sessions.value.filter((s) => !s.attached).length)

function basename(p) {
  if (!p) return ''
  const parts = String(p).replace(/\/+$/, '').split('/')
  return parts[parts.length - 1] || p
}
function fmtIdle(sec) {
  if (sec < 60) return `${sec}초`
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m}분`
  return `${Math.floor(m / 60)}시간`
}

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const data = await fetchTerminalSessions()
    sessions.value = data.sessions || []
    count.value = data.count ?? sessions.value.length
    max.value = data.max ?? max.value
    ttlSeconds.value = data.ttlSeconds ?? ttlSeconds.value
  } catch (e) {
    error.value = e?.message || '세션 목록을 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}

async function kill(sessionId) {
  busyId.value = sessionId
  error.value = ''
  try {
    await closeTerminalSession(sessionId)
    emit('changed', sessionId)
    await refresh()
  } catch (e) {
    error.value = e?.message || '세션 종료 실패'
  } finally {
    busyId.value = null
  }
}

async function reap() {
  loading.value = true
  error.value = ''
  try {
    const res = await reapDetachedSessions()
    if (res?.killed?.length) emit('changed', res.killed)
    await refresh()
  } catch (e) {
    error.value = e?.message || '정리 실패'
    loading.value = false
  }
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 5000)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.smp-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.35); z-index: 2000; display: flex; align-items: flex-start; justify-content: center; padding-top: 12vh; }
.smp { width: 440px; max-width: 92vw; max-height: 70vh; display: flex; flex-direction: column; background: var(--color-bg, #1e1e1e); color: var(--color-text, #e5e7eb); border: 1px solid var(--color-border, #333); border-radius: 8px; box-shadow: 0 12px 40px rgba(0,0,0,0.5); overflow: hidden; }
.smp__head { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid var(--color-border, #333); }
.smp__title { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.smp__count { font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 9999px; background: var(--status-neutral-bg, #334155); color: var(--status-neutral-fg, #cbd5e1); }
.smp__count--full { background: var(--status-red-bg, #7f1d1d); color: var(--status-red-fg, #fecaca); }
.smp__head-actions { display: flex; gap: 4px; }
.smp__icon-btn { background: none; border: none; color: var(--color-text-light, #94a3b8); font-size: 16px; cursor: pointer; padding: 2px 6px; border-radius: 4px; }
.smp__icon-btn:hover:not(:disabled) { background: var(--color-bg-tertiary, #334155); }
.smp__hint { margin: 0; padding: 10px 14px; font-size: 11px; line-height: 1.5; color: var(--color-text-light, #94a3b8); }
.smp__hint code { background: var(--color-bg-tertiary, #334155); padding: 0 4px; border-radius: 3px; }
.smp__loading, .smp__empty { padding: 18px 14px; font-size: 13px; color: var(--color-text-light, #94a3b8); font-style: italic; }
.smp__list { list-style: none; margin: 0; padding: 0 6px 6px; overflow-y: auto; }
.smp__row { display: flex; align-items: center; gap: 10px; padding: 8px 8px; border-radius: 6px; }
.smp__row:hover { background: var(--color-bg-secondary, #262626); }
.smp__dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.smp__dot.is-attached { background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,0.18); }
.smp__dot.is-detached { background: #f59e0b; }
.smp__row-main { flex: 1; min-width: 0; }
.smp__row-id { font-family: monospace; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.smp__row-meta { display: flex; gap: 8px; margin-top: 2px; font-size: 10px; color: var(--color-text-light, #94a3b8); flex-wrap: wrap; }
.smp__pid { font-family: monospace; }
.smp__cwd { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.smp__idle { color: #f59e0b; }
.smp__attached-tag { color: #22c55e; }
.smp__kill { background: none; border: 1px solid var(--color-border, #444); color: var(--color-danger, #f87171); font-size: 11px; padding: 3px 9px; border-radius: 4px; cursor: pointer; white-space: nowrap; flex-shrink: 0; }
.smp__kill:hover:not(:disabled) { background: var(--status-red-bg, #7f1d1d); border-color: transparent; }
.smp__kill:disabled { opacity: 0.5; cursor: default; }
.smp__foot { padding: 10px 14px; border-top: 1px solid var(--color-border, #333); }
.smp__reap { width: 100%; background: var(--color-bg-tertiary, #334155); border: none; color: var(--color-text, #e5e7eb); font-size: 12px; padding: 8px; border-radius: 5px; cursor: pointer; }
.smp__reap:hover:not(:disabled) { background: var(--status-amber-bg, #78350f); }
.smp__error { margin: 0; padding: 8px 14px; font-size: 12px; color: var(--color-danger, #f87171); }
</style>
