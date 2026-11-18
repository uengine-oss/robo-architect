<template>
  <!-- B-3 ⑪ ① Intent 탭의 인수조건이 **검증에 쓰인다**는 것을 한 줄로 보여 준다.
       탭 구조와 떨어진 작은 컴포넌트다 — ProposalDetail 에는 한 줄만 끼운다. -->
  <div v-if="count > 0" class="gwt-usage" :title="t('proposals.gwtUsage.title')">
    <span class="gwt-usage__badge">✓ {{ t('proposals.gwtUsage.badge', { n: count }) }}</span>
    <span v-if="summary" class="gwt-usage__results">
      {{ t('proposals.gwtUsage.results', summary) }}
    </span>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useProposalsStore } from '../proposals.store'
import { useI18n } from '../../../app/i18n'
import { countIntentCriteria, summarizeStrategicResults } from '../gwtUsage'

const props = defineProps({ proposal: { type: Object, required: true } })
const store = useProposalsStore()
const { t } = useI18n()

const count = computed(() => countIntentCriteria(props.proposal?.strategicDiff))
const summary = computed(() => summarizeStrategicResults(store.testResults, props.proposal?.id))

// 검증을 거친 Proposal 이면 결과를 한 번 불러 집계를 붙인다(이미 이 Proposal 것이면 그대로).
const VALIDATED = ['TESTING', 'PENDING_ACCEPTANCE', 'ACCEPTED', 'MERGE_FAILED']
onMounted(() => {
  const p = props.proposal
  if (!p?.id || !VALIDATED.includes(p.status) || count.value === 0) return
  if (store.testResults?.proposalId === p.id) return
  if (store.validationStream?.active) return
  store.fetchTestResults(p.id)
})
</script>

<style scoped>
.gwt-usage { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: 0 0 10px; font-size: 12px; }
.gwt-usage__badge { font-weight: 600; padding: 2px 8px; border-radius: 10px; background: var(--status-green-bg); color: var(--status-green-fg); }
.gwt-usage__results { color: var(--color-text-light); }
</style>
