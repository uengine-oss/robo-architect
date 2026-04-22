<script setup>
import { computed, ref } from 'vue'
import { useBpmnStore } from '@/features/canvas/bpmn.store'

const store = useBpmnStore()
const busy = ref(false)
const error = ref(null)

const item = computed(() => store.reviewModalItem)
const isOpen = computed(() => !!item.value)

const task = computed(() => {
  if (!item.value) return null
  return store.hybridTasks.find(t => t.id === item.value.task_id) || null
})
const rule = computed(() => {
  if (!item.value) return null
  return store.hybridRules.find(r => r.id === item.value.rule_id) || null
})

async function approve() {
  busy.value = true; error.value = null
  const r = await store.acceptReview(item.value)
  busy.value = false
  if (!r.ok) { error.value = r.error || '승인 실패'; return }
  store.closeReviewModal()
}
async function reject() {
  busy.value = true; error.value = null
  const r = await store.rejectReview(item.value)
  busy.value = false
  if (!r.ok) { error.value = r.error || '거부 실패'; return }
  store.closeReviewModal()
}
function close() {
  if (busy.value) return
  store.closeReviewModal()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="hrm-fade">
      <div v-if="isOpen" class="hrm-overlay" @click.self="close">
        <div class="hrm-modal" role="dialog" aria-modal="true">
          <header class="hrm-header">
            <div class="hrm-header__title">
              <span class="hrm-badge">Review</span>
              <span class="hrm-header__text">매핑 승인 여부 결정</span>
            </div>
            <button class="hrm-close" @click="close" :disabled="busy" title="닫기">✕</button>
          </header>

          <div class="hrm-body">
            <!-- Score / method -->
            <section class="hrm-section hrm-meta">
              <div class="hrm-meta__item">
                <div class="hrm-label">유사도</div>
                <div class="hrm-meta__value">{{ (item.score * 100).toFixed(0) }}%</div>
              </div>
              <div class="hrm-meta__item">
                <div class="hrm-label">매칭 방식</div>
                <div class="hrm-meta__value">{{ item.method }}</div>
              </div>
            </section>

            <!-- Task -->
            <section class="hrm-section">
              <div class="hrm-label">BPM Task</div>
              <div class="hrm-card">
                <div class="hrm-card__title">{{ task?.name || item.task_id }}</div>
                <p v-if="task?.description" class="hrm-card__desc">{{ task.description }}</p>
                <p v-else class="hrm-empty">설명 없음</p>
              </div>
            </section>

            <!-- Rule -->
            <section class="hrm-section">
              <div class="hrm-label">Business Rule (GWT)</div>
              <div class="hrm-card hrm-card--rule">
                <header v-if="rule?.source_function" class="hrm-card__head">
                  <code class="hrm-fn">{{ rule.source_function }}</code>
                  <span v-if="rule.source_module" class="hrm-mod">{{ rule.source_module }}</span>
                </header>
                <dl v-if="rule" class="hrm-gwt">
                  <div v-if="rule.given" class="hrm-gwt__row">
                    <dt>GIVEN</dt><dd>{{ rule.given }}</dd>
                  </div>
                  <div v-if="rule.when" class="hrm-gwt__row">
                    <dt>WHEN</dt><dd>{{ rule.when }}</dd>
                  </div>
                  <div v-if="rule.then" class="hrm-gwt__row">
                    <dt>THEN</dt><dd>{{ rule.then }}</dd>
                  </div>
                </dl>
                <p v-else class="hrm-empty">Rule 정보를 찾을 수 없음 ({{ item.rule_id }})</p>
              </div>
            </section>

            <p v-if="error" class="hrm-error">{{ error }}</p>
          </div>

          <footer class="hrm-footer">
            <button class="hrm-btn hrm-btn--reject" @click="reject" :disabled="busy">
              거부
            </button>
            <button class="hrm-btn hrm-btn--primary" @click="approve" :disabled="busy">
              승인
            </button>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.hrm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}
.hrm-modal {
  width: min(620px, 100%);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-elevated, #1b1f2a);
  border: 1px solid var(--color-border, rgba(255,255,255,0.08));
  border-radius: 8px;
  box-shadow: 0 18px 48px rgba(0,0,0,0.45);
  overflow: hidden;
}
.hrm-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
  background: linear-gradient(180deg, rgba(245,180,65,0.12), rgba(245,180,65,0.04));
}
.hrm-header__title {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}
.hrm-badge {
  font-size: 0.62rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(245,180,65,0.22);
  color: #f5b441;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}
.hrm-header__text {
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--color-text-bright);
}
.hrm-close {
  background: transparent;
  border: none;
  color: var(--color-text-dim);
  cursor: pointer;
  font-size: 1rem;
  padding: 4px 8px;
  border-radius: 4px;
}
.hrm-close:hover { background: rgba(255,255,255,0.08); color: var(--color-text-bright); }
.hrm-close:disabled { opacity: 0.5; cursor: default; }

.hrm-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.hrm-section { display: flex; flex-direction: column; gap: 6px; }
.hrm-label {
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--color-text-dim);
}
.hrm-empty {
  margin: 0;
  font-size: 0.75rem;
  color: var(--color-text-dim);
  font-style: italic;
}

.hrm-meta { flex-direction: row; gap: 24px; padding: 8px 10px; background: rgba(255,255,255,0.03); border-radius: 6px; }
.hrm-meta__item { display: flex; flex-direction: column; gap: 2px; }
.hrm-meta__value { font-size: 0.95rem; font-weight: 700; color: var(--color-text-bright); }

.hrm-card {
  padding: 10px 12px;
  background: rgba(92,124,250,0.08);
  border-left: 3px solid #5c7cfa;
  border-radius: 4px;
}
.hrm-card--rule {
  background: rgba(245,180,65,0.06);
  border-left-color: #f5b441;
}
.hrm-card__title { font-size: 0.86rem; font-weight: 600; color: var(--color-text-bright); }
.hrm-card__desc { margin: 6px 0 0; font-size: 0.78rem; line-height: 1.55; color: var(--color-text); }

.hrm-card__head { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px dashed rgba(255,255,255,0.1); flex-wrap: wrap; }
.hrm-fn { font-family: 'SF Mono', Menlo, monospace; font-size: 0.76rem; color: var(--color-text-bright); font-weight: 600; }
.hrm-mod { font-family: 'SF Mono', Menlo, monospace; font-size: 0.6rem; color: var(--color-text-dim); }

.hrm-gwt { margin: 0; display: flex; flex-direction: column; gap: 4px; }
.hrm-gwt__row { display: grid; grid-template-columns: 58px 1fr; gap: 10px; }
.hrm-gwt__row dt { font-weight: 700; font-size: 0.62rem; letter-spacing: 0.08em; color: #f5b441; padding-top: 2px; }
.hrm-gwt__row dd { margin: 0; font-size: 0.78rem; line-height: 1.55; color: var(--color-text); word-break: break-word; }

.hrm-error {
  margin: 0;
  padding: 8px 10px;
  background: rgba(255,90,90,0.12);
  border-left: 3px solid #ff5a5a;
  border-radius: 4px;
  font-size: 0.74rem;
  color: #ff9a9a;
}

.hrm-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  background: rgba(0,0,0,0.15);
}
.hrm-btn {
  padding: 8px 18px;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  border: 1px solid var(--color-border);
  background: rgba(255,255,255,0.04);
  color: var(--color-text);
  cursor: pointer;
}
.hrm-btn:disabled { opacity: 0.5; cursor: default; }
.hrm-btn:hover:not(:disabled) { background: rgba(255,255,255,0.08); }
.hrm-btn--reject { border-color: rgba(255,120,120,0.35); color: #ff9a9a; }
.hrm-btn--reject:hover:not(:disabled) { background: rgba(255,120,120,0.12); }
.hrm-btn--primary { background: #5c7cfa; color: #fff; border-color: #5c7cfa; }
.hrm-btn--primary:hover:not(:disabled) { background: #6f8dff; }

.hrm-fade-enter-active, .hrm-fade-leave-active { transition: opacity 0.18s ease; }
.hrm-fade-enter-from, .hrm-fade-leave-to { opacity: 0; }
</style>
