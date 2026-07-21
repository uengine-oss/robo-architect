<template>
  <!-- evlink — 요소별 레거시 근거 꼬리표(공용 트리거).
       linked  = 상시 컬러 태그. 클릭하면 우측 고정 근거 인스펙터 패널이 열린다
                 (LegacyEvidencePanel — 단일 인스턴스, 다른 요소 클릭 시 내용 교체).
       new     = 기본 점선 마크(조용), 근거 검증 모드에서만 텍스트 칩
       unknown = 요소 단위 표시 없음(제안 상단 배너가 담당), 검증 모드에서만 칩 -->
  <button
    v-if="basis.state === 'linked'"
    class="ltag ltag--linked"
    :class="{ 'ltag--active': isSelected }"
    :title="t('proposals.legacyTag.linkedTitle', { n: basis.refs.length })"
    :aria-pressed="isSelected"
    @click.stop="openEvidence && openEvidence(element)"
    @mouseenter="previewEvidence && previewEvidence(element)"
    @mouseleave="previewEvidence && previewEvidence(null)"
  >
    <svg class="ltag__icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d="M10.6 13.4a1 1 0 0 0 1.4 1.4l4-4a3 3 0 0 0-4.2-4.2l-2 2a1 1 0 1 0 1.4 1.4l2-2a1 1 0 0 1 1.4 1.4z"/>
      <path d="M13.4 10.6a1 1 0 0 0-1.4-1.4l-4 4a3 3 0 0 0 4.2 4.2l2-2a1 1 0 1 0-1.4-1.4l-2 2a1 1 0 0 1-1.4-1.4z"/>
    </svg>{{ basis.refs.length }}
  </button>

  <template v-else-if="basis.state === 'new'">
    <span v-if="evidenceMode" class="ltag ltag--new" :title="t('proposals.legacyTag.newTitle')">
      {{ t('proposals.legacyTag.new') }}
    </span>
    <span v-else class="ltag-dot" :title="t('proposals.legacyTag.newTitle')" />
  </template>

  <span
    v-else-if="evidenceMode"
    class="ltag ltag--unknown"
    :title="t('proposals.legacyTag.unknownTitle')"
  >{{ t('proposals.legacyTag.unknown') }}</span>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { elementLegacyBasis } from '../legacy-reference'
import { useI18n } from '../../../app/i18n'

const props = defineProps({
  /** strategicDiff/tacticalDiff 의 설계 요소 하나. legacyRefs 소유자. */
  element: { type: Object, required: true },
})

const { t } = useI18n()

// ProposalDetail 이 provide: 근거 패널 열기(클릭=핀), hover 미리보기, 현재 선택, 검증 모드.
const openEvidence = inject('evlinkOpenEvidence', null)
const previewEvidence = inject('evlinkPreviewEvidence', null)
const selection = inject('evlinkEvidenceSelection', ref(null))
const evidenceMode = inject('evlinkEvidenceMode', ref(false))

const basis = computed(() => elementLegacyBasis(props.element))
const isSelected = computed(() => selection.value === props.element)
</script>

<style scoped>
.ltag {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 10px; font-weight: 700; line-height: 1.5;
  border-radius: 3px; padding: 1px 6px; white-space: nowrap;
}
.ltag__icon { width: 11px; height: 11px; fill: currentColor; }
.ltag--linked {
  background: rgba(125, 139, 245, 0.12); border: 1px solid rgba(125, 139, 245, 0.45);
  color: #7d8bf5; cursor: pointer;
}
.ltag--linked:hover, .ltag--active { background: rgba(125, 139, 245, 0.24); }
.ltag--active { border-color: #7d8bf5; }
.ltag--new {
  background: transparent; border: 1px dashed var(--color-border);
  color: var(--color-text-light);
}
.ltag--unknown {
  background: transparent; border: 1px dotted var(--color-border);
  color: var(--color-text-light); opacity: 0.65;
}
/* 절제형: 근거 없는 신규 요소는 점선 링만 — 소음 없이 정직성 유지 */
.ltag-dot {
  width: 9px; height: 9px; flex-shrink: 0; align-self: center;
  border: 1.5px dashed color-mix(in srgb, var(--color-text-light) 55%, transparent);
  border-radius: 50%;
}
</style>
