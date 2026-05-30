<script setup>
/**
 * DDD 적합성·정합성 검증 결과 (034 US6).
 * 부적합 유형(잘못된 BC 배치 / 과대 입도 / 기존 스펙 충돌)과 교정안을 보여 준다.
 * 교정안은 비차단 — 안내·경고일 뿐 강제하지 않는다.
 */
defineProps({
  // ValidateResponse: { ok, findings, source }
  result: { type: Object, required: true },
  scopeName: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const KIND_LABEL = {
  wrong_bc: '잘못된 BC 배치',
  oversized_feature: '과도한 입도(분할 권장)',
  spec_conflict: '기존 요구사항과 충돌',
}
const ACTION_LABEL = {
  replace_bc: '다른 BC로 재배치',
  split: '더 작은 단위로 분할',
  merge: '기존 항목과 병합',
  differentiate: '차이를 명확히 구분',
  none: '',
}
</script>

<template>
  <div class="dialog-backdrop" @click.self="emit('close')">
    <div class="dialog">
      <div class="dialog__head">
        <h3>DDD 적합성 검증 — {{ scopeName }}</h3>
        <button class="dialog__close" @click="emit('close')">×</button>
      </div>
      <div class="dialog__body">
        <div v-if="result.ok || !result.findings.length" class="ok-box">
          ✅ 적합합니다. DDD 배치·입도·정합성 관점에서 발견된 문제가 없습니다.
        </div>

        <template v-else>
          <p class="dialog__hint">
            아래는 권장 사항입니다. 적용 여부는 사용자가 결정하며, 무시하고 진행할 수도 있습니다.
          </p>
          <div
            v-for="(f, i) in result.findings"
            :key="i"
            class="finding"
            :class="f.severity"
          >
            <div class="finding__head">
              <span class="finding__kind">{{ KIND_LABEL[f.kind] || f.kind }}</span>
              <span class="finding__sev">{{ f.severity === 'warning' ? '경고' : '정보' }}</span>
            </div>
            <p class="finding__msg">{{ f.message }}</p>
            <div v-if="f.suggestion && f.suggestion.action !== 'none'" class="finding__sugg">
              <strong>교정안:</strong>
              {{ ACTION_LABEL[f.suggestion.action] || f.suggestion.action }}
              <span v-if="f.suggestion.details"> — {{ f.suggestion.details }}</span>
            </div>
            <div v-if="f.affected && f.affected.length" class="finding__affected">
              관련: {{ f.affected.join(', ') }}
            </div>
          </div>
        </template>

        <div class="dialog__actions">
          <button class="btn btn--primary" @click="emit('close')">확인</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-backdrop {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.dialog {
  width: 560px; max-height: 84vh; background: var(--color-bg-secondary);
  border-radius: 10px; display: flex; flex-direction: column; overflow: hidden;
}
.dialog__head {
  display: flex; align-items: center; padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.dialog__head h3 { margin: 0; font-size: 0.95rem; }
.dialog__close {
  margin-left: auto; border: none; background: transparent; font-size: 1.2rem;
  cursor: pointer; color: var(--color-text-light);
}
.dialog__body { padding: 14px 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }
.dialog__hint { font-size: 0.78rem; color: var(--color-text-light); margin: 0; }
.ok-box {
  background: rgba(64, 192, 87, 0.12); border: 1px solid rgba(64, 192, 87, 0.4);
  color: var(--color-text); padding: 12px 14px; border-radius: 8px; font-size: 0.84rem;
}
.finding {
  border: 1px solid var(--color-border); border-left: 4px solid #fab005;
  border-radius: 8px; padding: 10px 12px;
}
.finding.warning { border-left-color: #fab005; }
.finding.info { border-left-color: #4dabf7; }
.finding__head { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.finding__kind { font-weight: 700; font-size: 0.82rem; }
.finding__sev {
  font-size: 0.62rem; padding: 1px 6px; border-radius: 4px;
  background: rgba(250, 176, 5, 0.2); color: #8a6500;
}
.finding__msg { margin: 4px 0; font-size: 0.82rem; }
.finding__sugg { font-size: 0.78rem; color: var(--color-text); background: var(--color-bg-tertiary); padding: 6px 8px; border-radius: 6px; }
.finding__affected { font-size: 0.72rem; color: var(--color-text-light); margin-top: 4px; }
.dialog__actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
.btn { padding: 6px 14px; border: 1px solid var(--color-border); border-radius: 6px; cursor: pointer; font-size: 0.78rem; background: var(--color-bg-tertiary); color: var(--color-text); }
.btn--primary { background: var(--color-accent); color: #fff; border-color: transparent; }
</style>
