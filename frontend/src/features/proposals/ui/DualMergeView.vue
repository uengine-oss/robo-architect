<template>
  <div class="dual-merge">
    <!-- 구현 완료 후 PO 최종 결정 (TESTING / PENDING_ACCEPTANCE) -->
    <div v-if="canDecide" class="pending-acceptance">
      <h4>PO 최종 결정</h4>

      <!-- 검증 미완료(TESTING) — 검증을 거치지 않고도 Accept/Destroy 가능하나 안내한다. -->
      <div v-if="proposal?.status === 'TESTING'" class="not-validated-note">
        <span class="info-icon">ℹ</span>
        아직 검증이 완료되지 않았습니다. <strong>'검증'</strong> 탭에서 검증을 먼저 실행할 수 있으며,
        구현이 완료되었다면 검증 없이도 아래에서 Accept/Destroy를 결정할 수 있습니다.
      </div>

      <div v-if="hasFailures" class="failure-warning">
        <span class="warning-icon">⚠</span>
        <strong>{{ testFailed }}개의 테스트가 실패했습니다.</strong>
        <p>Accept를 진행하려면 아래 확인란에 체크하세요.</p>
        <label class="force-check">
          <input type="checkbox" v-model="forceAccept" />
          실패 항목을 인지하고 Accept를 진행합니다
        </label>
      </div>

      <div class="merge-actions">
        <button
          @click="accept"
          :disabled="acceptDisabled || accepting"
          class="btn btn--accept"
        >
          {{ accepting ? 'Accept 처리 중...' : '✓ Accept (Dual Merge)' }}
        </button>
        <button
          @click="showDestroyConfirm = true"
          class="btn btn--destroy"
        >✗ Destroy</button>
      </div>
    </div>

    <!-- MERGE_FAILED 상태 -->
    <div v-if="proposal?.status === 'MERGE_FAILED'" class="merge-failed">
      <h4 class="merge-failed__title">⚠ Dual Merge 실패</h4>
      <p class="merge-failed__detail">{{ lastFailureDetail }}</p>
      <button @click="retryMerge" :disabled="retrying" class="btn btn--retry">
        {{ retrying ? '재시도 중...' : 'Dual Merge 재시도' }}
      </button>
    </div>

    <!-- ACCEPTED 상태 -->
    <div v-if="proposal?.status === 'ACCEPTED'" class="accepted">
      <div class="accepted__icon">✓</div>
      <p>Dual Merge 완료 — {{ formatDate(proposal.acceptedAt) }}</p>
      <p class="accepted__note">코드와 그래프 DB가 동기화되었습니다.</p>
      <button @click="showRevokeConfirm = true" class="btn btn--revoke">↩ 수거 (되돌리기)</button>
    </div>

    <!-- DESTROYED 상태 -->
    <div v-if="proposal?.status === 'DESTROYED'" class="destroyed">
      <p>이 Proposal은 폐기되었습니다 — {{ formatDate(proposal.destroyedAt) }}</p>
    </div>

    <!-- Destroy 확인 다이얼로그 -->
    <div v-if="showDestroyConfirm" class="overlay">
      <div class="dialog">
        <h4>Proposal 폐기 확인</h4>
        <p>폐기된 Proposal의 Diff 이력은 보관됩니다.</p>
        <textarea v-model="destroyReason" placeholder="폐기 사유 (선택)" rows="3" class="dialog__textarea" />
        <div class="dialog__actions">
          <button @click="showDestroyConfirm = false" class="btn btn--secondary">취소</button>
          <button @click="destroy" :disabled="destroying" class="btn btn--destroy">
            {{ destroying ? '폐기 중...' : '폐기 확정' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 수거(Revoke) 확인 다이얼로그 -->
    <div v-if="showRevokeConfirm" class="overlay">
      <div class="dialog">
        <h4>↩ Proposal 수거 (되돌리기)</h4>
        <p>Accept로 반영된 변경을 되돌립니다. 생성된 UserStory·Aggregate 등은 삭제되고, 수정분은 원래 값으로 복원됩니다. 상태는 다시 <strong>PENDING_ACCEPTANCE</strong>로 돌아가 재Accept할 수 있습니다.</p>
        <div class="revoke-scope">
          <label class="revoke-radio">
            <input type="radio" value="graph" v-model="revokeScope" />
            <span><strong>그래프만 되돌리기</strong> — Neo4j 변경만 복원. 코드는 main에 그대로 둠(별도 처리).</span>
          </label>
          <label class="revoke-radio">
            <input type="radio" value="code" v-model="revokeScope" />
            <span><strong>그래프 + 코드 되돌리기</strong> — 그래프 복원에 더해 Accept 머지 커밋을 <code>git revert</code>.</span>
          </label>
        </div>
        <div class="dialog__actions">
          <button @click="showRevokeConfirm = false" class="btn btn--secondary">취소</button>
          <button @click="revoke" :disabled="revoking" class="btn btn--revoke">
            {{ revoking ? '수거 중...' : '수거 확정' }}
          </button>
        </div>
      </div>
    </div>

    <p v-if="actionError" class="error-msg">{{ actionError }}</p>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useProposalsStore } from '../proposals.store'

const props = defineProps({ proposal: { type: Object, required: true } })
const store = useProposalsStore()

const forceAccept = ref(false)
const showDestroyConfirm = ref(false)
const destroyReason = ref('')
const accepting = ref(false)
const destroying = ref(false)
const retrying = ref(false)
const actionError = ref('')
const showRevokeConfirm = ref(false)
const revoking = ref(false)
const revokeScope = ref('graph')

// 구현 완료 후(TESTING) 또는 검증 후(PENDING_ACCEPTANCE)면 PO가 Accept/Destroy 결정 가능.
// 검증을 통과·완료하지 않아도 구현이 완료되었으면 결정 단계로 넘어올 수 있어야 한다.
const canDecide = computed(() =>
  ['TESTING', 'PENDING_ACCEPTANCE'].includes(props.proposal?.status)
)

const hasFailures = computed(() => {
  const tr = store.testResults
  return tr && tr.failed > 0
})
const testFailed = computed(() => store.testResults?.failed || 0)

// 기본 PO 정책: 자기 승인 허용. Accept는 실패 항목 미인지/처리 중일 때만 비활성.
const acceptDisabled = computed(() =>
  (hasFailures.value && !forceAccept.value) || accepting.value
)

const lastFailureDetail = computed(() => {
  const history = props.proposal?.statusHistory || []
  const last = [...history].reverse().find(h => h.to_status === 'MERGE_FAILED')
  return last?.comment || 'Dual Merge 실패. 로그를 확인하세요.'
})

async function accept() {
  accepting.value = true
  actionError.value = ''
  try {
    await store.acceptProposal(props.proposal.id, {
      forceAcceptWithFailures: hasFailures.value && forceAccept.value,
    })
  } catch (e) {
    actionError.value = e.message
  } finally {
    accepting.value = false
  }
}

async function destroy() {
  destroying.value = true
  actionError.value = ''
  try {
    await store.destroyProposal(props.proposal.id, { reason: destroyReason.value })
    showDestroyConfirm.value = false
  } catch (e) {
    actionError.value = e.message
  } finally {
    destroying.value = false
  }
}

async function revoke() {
  revoking.value = true
  actionError.value = ''
  try {
    await store.revokeProposal(props.proposal.id, { revertCode: revokeScope.value === 'code' })
    showRevokeConfirm.value = false
  } catch (e) {
    actionError.value = e.message
  } finally {
    revoking.value = false
  }
}

async function retryMerge() {
  retrying.value = true
  actionError.value = ''
  try {
    await store.retryMerge(props.proposal.id)
  } catch (e) {
    actionError.value = e.message
  } finally {
    retrying.value = false
  }
}

function formatDate(dt) {
  if (!dt) return ''
  return new Date(dt).toLocaleString('ko-KR')
}
</script>

<style scoped>
.dual-merge { font-size: 13px; }
.pending-acceptance h4 { margin: 0 0 12px; font-size: 15px; font-weight: 600; color: var(--color-text-bright); }
.not-validated-note { background: var(--status-blue-bg); border: 1px solid color-mix(in srgb, var(--status-blue-fg) 25%, transparent); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; color: var(--color-text); font-size: 12px; line-height: 1.6; }
.not-validated-note .info-icon { margin-right: 4px; color: var(--status-blue-fg); font-weight: 700; }
.failure-warning { background: var(--status-amber-bg); border: 1px solid var(--status-amber-bg); border-radius: 8px; padding: 12px; margin-bottom: 12px; color: var(--status-amber-fg); }
.warning-icon { margin-right: 4px; }
.force-check { display: flex; align-items: center; gap: 6px; margin-top: 8px; cursor: pointer; }
.merge-actions { display: flex; gap: 10px; }
.btn { padding: 8px 18px; border-radius: 6px; border: none; cursor: pointer; font-size: 13px; font-weight: 500; }
.btn--accept { background: var(--color-success); color: #fff; }
.btn--accept:disabled { opacity: 0.5; cursor: default; }
.btn--destroy { background: var(--color-danger); color: #fff; }
.btn--retry { background: var(--color-warning); color: #fff; }
.btn--secondary { background: var(--color-bg-tertiary); color: var(--color-text); }
.btn--revoke { background: var(--color-bg-tertiary); color: var(--color-danger); border: 1px solid var(--color-danger); margin-top: 14px; }
.btn--revoke:disabled { opacity: 0.5; cursor: default; }
.revoke-scope { display: flex; flex-direction: column; gap: 10px; margin: 12px 0; }
.revoke-radio { display: flex; gap: 8px; align-items: flex-start; font-size: 12px; color: var(--color-text); cursor: pointer; line-height: 1.5; }
.revoke-radio input { margin-top: 2px; }
.revoke-radio code { font-family: monospace; background: var(--color-bg-tertiary); padding: 0 4px; border-radius: 3px; }
.merge-failed { background: var(--status-red-bg); border: 1px solid var(--status-red-bg); border-radius: 8px; padding: 16px; }
.merge-failed__title { margin: 0 0 8px; color: var(--status-red-fg); font-size: 15px; }
.merge-failed__detail { color: var(--color-text-light); font-size: 12px; margin-bottom: 12px; }
.accepted { text-align: center; padding: 24px; }
.accepted__icon { font-size: 36px; color: var(--color-success); margin-bottom: 8px; }
.accepted__note { color: var(--color-text-light); font-size: 12px; }
.destroyed { color: var(--color-text-light); padding: 16px; font-style: italic; }
.overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center; z-index: 9999; }
.dialog { background: var(--color-bg-secondary); border: 1px solid var(--color-border); border-radius: 10px; padding: 24px; min-width: 360px; box-shadow: var(--shadow-lg); }
.dialog h4 { margin: 0 0 8px; font-size: 16px; color: var(--color-text-bright); }
.dialog__textarea { width: 100%; resize: vertical; padding: 8px; border: 1px solid var(--color-border); border-radius: 4px; font-size: 13px; margin-top: 8px; background: var(--color-bg); color: var(--color-text); }
.dialog__actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 12px; }
.error-msg { color: var(--color-danger); font-size: 12px; margin-top: 8px; }
</style>
