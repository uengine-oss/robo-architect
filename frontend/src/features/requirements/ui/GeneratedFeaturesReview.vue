<script setup>
import { ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * Epic → Feature(spec.md) 자동 생성 — 제안 검토 (034).
 * 각 Feature는 하나의 spec.md: User Story들 + edge cases + 가정. 체크한 Feature만
 * (그 하위 US와 함께) 등록된다(HITL).
 */
const props = defineProps({
  // GenerateFeaturesResponse: { boundedContextId, features: [...] }
  result: { type: Object, required: true },
  scopeName: { type: String, default: '' },
})
const emit = defineEmits(['close', 'confirmed'])

const store = useRequirementsStore()
const rows = ref(
  (props.result.features || []).map((f) => ({
    selected: true,
    name: f.name || '',
    description: f.description || '',
    edgeCases: f.edgeCases || [],
    assumptions: f.assumptions || [],
    conflicts: f.conflicts || [],
    userStories: f.userStories || [],
    expanded: false,
  })),
)
const busy = ref(false)
const errorMsg = ref('')

async function confirm() {
  const chosen = rows.value.filter((r) => r.selected && r.name.trim())
  if (!chosen.length) {
    emit('close')
    return
  }
  busy.value = true
  errorMsg.value = ''
  try {
    const data = await store.confirmFeatures({
      boundedContextId: props.result.boundedContextId,
      features: chosen.map((r) => ({
        name: r.name,
        description: r.description,
        edgeCases: r.edgeCases,
        assumptions: r.assumptions,
        conflicts: r.conflicts,
        userStories: r.userStories,
      })),
    })
    emit('confirmed', data)
    emit('close')
  } catch (e) {
    errorMsg.value = String(e.message || e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="dialog-backdrop" @click.self="emit('close')">
    <div class="dialog">
      <div class="dialog__head">
        <h3>Feature 자동 생성 — 제안 검토</h3>
        <button class="dialog__close" @click="emit('close')">×</button>
      </div>
      <div class="dialog__body">
        <p class="dialog__hint">
          <strong>{{ scopeName }}</strong> 를 Feature 단위(각 = 하나의 spec.md)로 나눴습니다.
          각 Feature는 User Story·edge cases·가정을 포함합니다. 체크한 Feature만 등록됩니다.
        </p>
        <p v-if="errorMsg" class="dialog__error">{{ errorMsg }}</p>
        <p v-if="!rows.length" class="dialog__empty">제안된 Feature가 없습니다.</p>

        <div v-for="(r, i) in rows" :key="i" class="feat" :class="{ off: !r.selected }">
          <div class="feat__head">
            <input type="checkbox" v-model="r.selected" />
            <input class="feat__name" v-model="r.name" />
            <span class="feat__badge">US {{ r.userStories.length }}</span>
            <button class="feat__toggle" @click="r.expanded = !r.expanded">
              {{ r.expanded ? '▾' : '▸' }} 상세
            </button>
          </div>
          <input class="feat__desc" v-model="r.description" placeholder="설명" />

          <div v-if="r.expanded" class="feat__detail">
            <div class="sec">
              <div class="sec__label">User Stories</div>
              <ul>
                <li v-for="(us, j) in r.userStories" :key="j">
                  {{ us.role }}: {{ us.action }}
                  <ul v-if="(us.acceptanceCriteria || []).length" class="ac">
                    <li v-for="(ac, k) in us.acceptanceCriteria" :key="k">{{ ac }}</li>
                  </ul>
                </li>
              </ul>
            </div>
            <div class="sec" v-if="r.conflicts.length">
              <div class="sec__label sec__label--warn">⚠ 기존 요구사항과 충돌</div>
              <ul><li v-for="(c, j) in r.conflicts" :key="j">{{ c }}</li></ul>
            </div>
            <div class="sec" v-if="r.edgeCases.length">
              <div class="sec__label">Edge Cases</div>
              <ul><li v-for="(e, j) in r.edgeCases" :key="j">{{ e }}</li></ul>
            </div>
            <div class="sec" v-if="r.assumptions.length">
              <div class="sec__label">가정 (Assumptions)</div>
              <ul><li v-for="(a, j) in r.assumptions" :key="j">{{ a }}</li></ul>
            </div>
          </div>
        </div>

        <div class="dialog__actions">
          <button class="btn" @click="emit('close')">취소</button>
          <button class="btn btn--primary" :disabled="busy" @click="confirm">
            {{ busy ? '등록 중...' : '선택 Feature 등록' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.dialog { width: 660px; max-height: 86vh; background: var(--color-bg-secondary); border-radius: 10px; display: flex; flex-direction: column; overflow: hidden; }
.dialog__head { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--color-border); }
.dialog__head h3 { margin: 0; font-size: 0.95rem; }
.dialog__close { margin-left: auto; border: none; background: transparent; font-size: 1.2rem; cursor: pointer; color: var(--color-text-light); }
.dialog__body { padding: 14px 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.dialog__hint { font-size: 0.78rem; color: var(--color-text-light); margin: 0; }
.dialog__error { color: #e03131; font-size: 0.78rem; margin: 0; }
.dialog__empty { font-size: 0.8rem; color: var(--color-text-light); font-style: italic; }
.feat { border: 1px solid var(--color-border); border-radius: 8px; padding: 10px; display: flex; flex-direction: column; gap: 6px; }
.feat.off { opacity: 0.45; }
.feat__head { display: flex; align-items: center; gap: 8px; }
.feat__name { flex: 1; padding: 5px 8px; font-size: 0.84rem; font-weight: 600; background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 6px; color: var(--color-text); }
.feat__badge { font-size: 0.66rem; padding: 1px 6px; border-radius: 4px; background: rgba(64,192,87,.2); color: #40c057; }
.feat__toggle { border: none; background: transparent; color: var(--color-text-light); font-size: 0.72rem; cursor: pointer; }
.feat__desc { padding: 5px 8px; font-size: 0.78rem; background: var(--color-bg-tertiary); border: 1px solid var(--color-border); border-radius: 6px; color: var(--color-text); }
.feat__detail { padding: 4px 2px 0; display: flex; flex-direction: column; gap: 8px; }
.sec__label { font-size: 0.68rem; font-weight: 700; color: var(--color-text-light); text-transform: uppercase; margin-bottom: 2px; }
.sec ul { margin: 0; padding-left: 16px; font-size: 0.78rem; color: var(--color-text); }
.sec li { margin: 1px 0; }
.sec ul.ac { padding-left: 14px; margin: 2px 0 4px; }
.sec ul.ac li { font-size: 0.72rem; color: var(--color-text-light); }
.sec__label--warn { color: #e8590c; }
.dialog__actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
.btn { padding: 6px 14px; border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer; font-size: 0.78rem; background: var(--color-bg-tertiary); color: var(--color-text); }
.btn--primary { background: var(--color-accent); color: #fff; border-color: transparent; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
