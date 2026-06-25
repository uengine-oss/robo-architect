<template>
  <div class="stage-plan">
    <h4>{{ t('proposals.staged.stagePlanTitle') }}</h4>
    <p v-if="plan?.classifiedReach" class="stage-plan__reach">{{ plan.classifiedReach }}</p>
    <ul class="stage-plan__list">
      <li v-for="item in localStages" :key="item.stage" class="stage-plan__item">
        <label class="stage-plan__toggle">
          <input
            type="checkbox"
            :checked="!item.skipped"
            :disabled="item.stage === 'DISCOVER'"
            @change="item.skipped = !$event.target.checked"
          />
          <span class="stage-plan__name">{{ item.stage }}</span>
        </label>
        <span :class="['stage-plan__badge', item.skipped ? 'is-skip' : 'is-run']">
          {{ item.skipped ? t('proposals.staged.skip') : t('proposals.staged.apply') }}
        </span>
        <span class="stage-plan__reason">{{ item.reason }}</span>
      </li>
    </ul>
    <div class="stage-plan__actions">
      <button class="btn btn--primary" @click="confirm">{{ t('proposals.staged.confirmPlan') }}</button>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useI18n } from '../../../app/i18n'

const props = defineProps({ plan: { type: Object, default: null } })
const emit = defineEmits(['confirm'])
const { t } = useI18n()

const localStages = ref([])
watch(() => props.plan, (p) => {
  localStages.value = (p?.stages || []).map(s => ({
    stage: s.stage,
    skipped: s.stage === 'DISCOVER' ? false : !!(s.skipped ?? s.recommendSkip),
    reason: s.reason || '',
  }))
}, { immediate: true })

function confirm() {
  emit('confirm', localStages.value.map(s => ({ stage: s.stage, skipped: s.skipped })))
}
</script>

<style scoped>
.stage-plan { padding: 12px; }
.stage-plan h4 { margin: 0 0 8px; font-size: 14px; color: var(--color-text-bright); }
.stage-plan__reach { font-size: 12px; color: var(--color-text-light); margin: 0 0 8px; font-style: italic; }
.stage-plan__list { list-style: none; padding: 0; margin: 0; }
.stage-plan__item { display: grid; grid-template-columns: 160px 60px 1fr; align-items: center; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--color-border); }
.stage-plan__toggle { display: flex; align-items: center; gap: 6px; cursor: pointer; }
.stage-plan__name { font-size: 13px; font-weight: 600; color: var(--color-text); }
.stage-plan__badge { font-size: 10px; padding: 1px 6px; border-radius: 8px; text-align: center; }
.stage-plan__badge.is-run { background: var(--status-blue-bg); color: var(--status-blue-fg); }
.stage-plan__badge.is-skip { background: var(--color-bg-tertiary); color: var(--color-text-light); }
.stage-plan__reason { font-size: 11px; color: var(--color-text-light); }
.stage-plan__actions { margin-top: 12px; text-align: right; }
.btn { padding: 6px 14px; border-radius: 4px; border: none; cursor: pointer; font-size: 13px; }
.btn--primary { background: var(--color-accent); color: #fff; }
</style>
