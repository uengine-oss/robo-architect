<template>
  <!-- evlink — 근거 인스펙터 패널(단일 인스턴스). 어떤 탭에서든 ⚭ 태그를 클릭하면
       항상 화면 오른쪽 같은 자리에 그 요소의 근거가 열린다. 다른 요소 클릭 시 내용만
       교체되므로 팝오버 중첩·가림·위치 점프가 없다(피로도 최소화). -->
  <aside class="evpanel" :class="{ 'evpanel--preview': previewing }" @click.stop>
    <header class="evpanel__head">
      <div class="evpanel__heading">
        <div class="evpanel__eyebrow">
          {{ t('proposals.legacyTag.popTitle', { n: enriched.length }) }}
          <span v-if="previewing" class="evpanel__preview-badge">{{ t('proposals.legacyTag.previewing') }}</span>
        </div>
        <div class="evpanel__title">
          <span v-if="elementKind" class="evpanel__kind">{{ elementKind }}</span>
          {{ elementTitle }}
        </div>
      </div>
      <button class="evpanel__close" aria-label="close" @click="$emit('close')">×</button>
    </header>

    <div class="evpanel__body">
      <article v-for="ref in enriched" :key="ref.nodeId" class="evcard">
        <header class="evcard__head">
          <span class="evcard__dot" :class="{ 'evcard__dot--content': ref.contentKind }" />
          <div class="evcard__names">
            <div class="evcard__logical">{{ ref.displayName }}</div>
            <div class="evcard__physical">
              <code>{{ ref.physicalName }}</code>
              <span v-if="ref.labelText" class="evcard__label">{{ ref.labelText }}</span>
              <span v-if="ref.role && !ref.contentKind" class="evcard__role">{{ roleLabel(ref.role) }}</span>
            </div>
          </div>
          <span class="evcard__state"
                :class="{ 'evcard__state--searched': !(ref.item?.inspected || ref.contentKind) }">
            {{ ref.contentKind ? t('proposals.legacyTag.graphVerified')
              : ref.item?.inspected ? t('proposals.legacyTag.inspected')
              : t('proposals.legacyTag.searchedOnly') }}
          </span>
        </header>

        <!-- RULE 승격 — 규칙 문장이 본문 -->
        <blockquote v-if="ref.statementText" class="evcard__evidence evcard__evidence--rule">
          {{ ref.statementText }}
        </blockquote>
        <blockquote v-else-if="ref.evidence" class="evcard__evidence">{{ ref.evidence }}</blockquote>

        <!-- EXAMPLE/RULE 사례 — given/when/then -->
        <div v-for="(gwt, i) in ref.gwtRows" :key="i" class="evcard__gwt">
          <div v-if="gwt.given" class="evcard__gwt-row"><b class="evcard__gwt-k evcard__gwt-k--g">GIVEN</b>{{ gwt.given }}</div>
          <div v-if="gwt.when" class="evcard__gwt-row"><b class="evcard__gwt-k evcard__gwt-k--w">WHEN</b>{{ gwt.when }}</div>
          <div v-if="gwt.then" class="evcard__gwt-row"><b class="evcard__gwt-k evcard__gwt-k--t">THEN</b>{{ gwt.then }}</div>
        </div>

        <div v-if="ref.field" class="evcard__field">field · {{ ref.field }}</div>

        <!-- 원문 코드 — provenance 에 저장된 실제 코드(생성 시 검토분) -->
        <details v-if="ref.codeLines" class="evcard__code" open>
          <summary>
            <code class="evcard__loc">{{ shortSourcePath(ref.source.file_path) }} : {{ ref.source.start_line }}~{{ ref.source.end_line }}</code>
            <span class="evcard__code-hint">{{ t('proposals.legacyTag.viewSource') }}</span>
          </summary>
          <pre class="evcard__pre"><span
            v-for="line in ref.codeLines" :key="line.no" class="evcard__line"
          ><span class="evcard__lineno">{{ line.no }}</span>{{ line.text }}
</span></pre>
        </details>
        <div v-else-if="ref.source" class="evcard__loc-only">
          <code class="evcard__loc">{{ shortSourcePath(ref.source.file_path) }} : {{ ref.source.start_line }}~{{ ref.source.end_line }}</code>
        </div>

        <!-- TABLE 근거 — 실제 컬럼 목록 -->
        <div v-if="ref.columns.length" class="evcard__cols">
          <span v-for="column in ref.columns" :key="column.name" class="evcard__col">
            {{ column.name }}<i v-if="column.logicalName"> · {{ column.logicalName }}</i>
          </span>
        </div>

        <p v-if="ref.item?.summary" class="evcard__summary">{{ ref.item.summary }}</p>

        <!-- 역방향 서사 — 이 레거시 근거가 설계의 몇 곳을 지탱하는가 -->
        <div v-if="ref.citedBy.length > 1" class="evcard__citedby">
          <span class="evcard__citedby-label">
            {{ t('proposals.legacyTag.citedBy', { n: ref.citedBy.length }) }}
          </span>
          <button
            v-for="(user, i) in ref.citedBy" :key="i"
            class="evcard__citedby-chip"
            :class="{ 'evcard__citedby-chip--self': user.element === element }"
            @click="user.element !== element && openEvidence && openEvidence(user.element)"
          >{{ user.title }}</button>
        </div>
      </article>
    </div>
  </aside>
</template>

<script setup>
import { computed, inject, onMounted, onBeforeUnmount } from 'vue'
import { elementLegacyBasis, shortSourcePath } from '../legacy-reference'
import { useI18n } from '../../../app/i18n'

const props = defineProps({
  /** 근거를 보여줄 설계 요소(legacyRefs 소유자). */
  element: { type: Object, required: true },
  /** hover 미리보기 상태(핀 아님) — 헤더에 표시만 다르게. */
  previewing: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])
const { t } = useI18n()

const provenance = inject('evlinkLegacyProvenance', computed(() => new Map()))
const citedBy = inject('evlinkCitedBy', computed(() => new Map()))
const openEvidence = inject('evlinkOpenEvidence', null)

const elementTitle = computed(() =>
  props.element?.nodeTitle || props.element?.entityTitle || props.element?.tempId || '')
const elementKind = computed(() =>
  props.element?.nodeLabel || props.element?.entityType || '')

const ROLE_LABELS = { 'derived-from': '유래', refines: '정제', reads: '읽음', writes: '씀' }
function roleLabel(role) { return ROLE_LABELS[role] || role }

const KIND_NAMES = { rule: '업무 규칙', example: '업무 사례' }

const enriched = computed(() => elementLegacyBasis(props.element).refs.map((ref) => {
  const item = provenance.value.get(ref.nodeId)
  const parentItem = ref.parentId ? provenance.value.get(ref.parentId) : null
  const source = item?.source?.available ? item.source : null
  const codeText = source?.code_text
  const contentKind = ref.role === 'rule' || ref.role === 'example' ? ref.role : null
  return {
    ...ref,
    item,
    parentItem,
    source,
    contentKind,
    // 내용 승격 ref(rule/example)는 provenance 에 없다 — ref 자신의 데이터로 그린다.
    displayName: contentKind
      ? KIND_NAMES[contentKind]
      : (item?.logicalName || item?.name || ref.nodeId.split(/[.:]/).pop()),
    physicalName: contentKind
      ? (parentItem?.name || (ref.parentId || '').split(':').pop())
      : (item?.name || ref.nodeId.split(':').pop()),
    labelText: item?.label || (contentKind ? contentKind.toUpperCase()
      : (ref.nodeId.startsWith('db:') ? 'TABLE' : '')),
    statementText: contentKind === 'rule' ? (ref.statement || '') : '',
    gwtRows: (ref.examples || []).filter((e) => e && (e.given || e.when || e.then)),
    columns: (item?.columns || []).slice(0, 24),
    citedBy: citedBy.value.get(ref.nodeId) || [],
    codeLines: codeText
      ? codeText.split('\n').map((text, i) => ({ no: (source.start_line || 1) + i, text }))
      : null,
  }
}))

function onKeydown(event) { if (event.key === 'Escape') emit('close') }
onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.evpanel {
  position: fixed; top: 60px; right: 12px; bottom: 12px; z-index: 1200;
  display: flex; flex-direction: column; width: 470px; max-width: calc(100vw - 24px);
  background: var(--color-bg-secondary, #20242f);
  border: 1px solid var(--color-border, #3a4468); border-radius: 10px;
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.45);
}
.evpanel__head {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 11px 14px 9px; border-bottom: 1px solid var(--color-border);
}
.evpanel__heading { flex: 1; min-width: 0; }
.evpanel--preview { border-style: dashed; }
.evpanel__eyebrow {
  display: flex; align-items: baseline; gap: 6px;
  font-size: 10px; font-weight: 700; letter-spacing: 0.06em; color: #7d8bf5;
}
.evpanel__preview-badge {
  font-weight: 600; letter-spacing: 0; color: var(--color-text-light);
  border: 1px dashed var(--color-border); border-radius: 3px; padding: 0 4px;
}
.evpanel__title {
  margin-top: 2px; font-size: 13px; font-weight: 700; color: var(--color-text);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.evpanel__kind {
  font-size: 9px; font-weight: 600; color: var(--color-text-light);
  border: 1px solid var(--color-border); border-radius: 3px; padding: 0 4px;
  vertical-align: 1px; margin-right: 3px;
}
.evpanel__close {
  border: none; background: none; cursor: pointer; padding: 0 3px;
  color: var(--color-text-light); font-size: 17px; line-height: 1;
}
.evpanel__close:hover { color: var(--color-text); }
.evpanel__body { flex: 1; overflow-y: auto; padding: 0 14px 12px; }

/* ── Evidence Card ── */
.evcard { padding: 11px 0 10px; border-bottom: 1px solid var(--color-border); }
.evcard:last-child { border-bottom: none; }
.evcard__head { display: flex; align-items: flex-start; gap: 8px; }
.evcard__dot {
  flex-shrink: 0; width: 7px; height: 7px; margin-top: 5px;
  background: #7d8bf5; border-radius: 50%;
}
.evcard__names { flex: 1; min-width: 0; }
.evcard__logical { font-size: 13px; font-weight: 700; color: var(--color-text); line-height: 1.35; }
.evcard__physical { display: flex; align-items: baseline; gap: 6px; margin-top: 2px; flex-wrap: wrap; }
.evcard__physical > code { font-family: Consolas, monospace; font-size: 11px; color: #aab4f0; }
.evcard__label { font-size: 9px; color: var(--color-text-light); border: 1px solid var(--color-border); border-radius: 3px; padding: 0 4px; }
.evcard__role { font-size: 9px; font-weight: 700; color: #3ecf8e; border: 1px solid rgba(62, 207, 142, 0.4); border-radius: 3px; padding: 0 4px; }
.evcard__state { flex-shrink: 0; font-size: 9px; color: #3ecf8e; margin-top: 3px; }
.evcard__state--searched { color: var(--color-text-light); }

.evcard__dot--content { background: #3ecf8e; }
.evcard__evidence {
  margin: 8px 0 0 15px; padding: 5px 10px; font-size: 12px; line-height: 1.5;
  color: var(--color-text); border-left: 2px solid #7d8bf5;
  background: rgba(125, 139, 245, 0.06); border-radius: 0 5px 5px 0;
}
.evcard__evidence--rule { border-left-color: #3ecf8e; background: rgba(62, 207, 142, 0.07); }
.evcard__gwt { margin: 6px 0 0 15px; display: flex; flex-direction: column; gap: 2px; }
.evcard__gwt-row { display: flex; gap: 7px; font-size: 11px; color: var(--color-text); align-items: baseline; }
.evcard__gwt-k { flex-shrink: 0; width: 40px; font-size: 9px; font-weight: 800; }
.evcard__gwt-k--g { color: #1098ad; }
.evcard__gwt-k--w { color: #f59f00; }
.evcard__gwt-k--t { color: #3ecf8e; }
.evcard__field { margin: 4px 0 0 15px; font-size: 10px; color: var(--color-text-light); }

.evcard__code { margin: 8px 0 0 15px; }
.evcard__code > summary {
  display: flex; align-items: baseline; gap: 8px; cursor: pointer; user-select: none;
  list-style: none;
}
.evcard__code > summary::-webkit-details-marker { display: none; }
.evcard__loc {
  font-family: Consolas, monospace; font-size: 10.5px; color: #7d8bf5;
  background: rgba(125, 139, 245, 0.08); border-radius: 3px; padding: 1px 6px;
}
.evcard__code-hint { font-size: 10px; color: var(--color-text-light); }
.evcard__code[open] .evcard__code-hint { display: none; }
.evcard__pre {
  margin: 6px 0 0; padding: 8px 0; max-height: 240px; overflow: auto;
  background: #14171f; border: 1px solid var(--color-border); border-radius: 6px;
  font-family: Consolas, monospace; font-size: 10.5px; line-height: 1.55;
  color: #c7cdde; white-space: pre; tab-size: 4;
}
.evcard__line { display: block; padding-right: 10px; }
.evcard__lineno {
  display: inline-block; width: 44px; padding-right: 10px; text-align: right;
  color: #4d556e; user-select: none;
}
.evcard__loc-only { margin: 7px 0 0 15px; }

.evcard__cols { display: flex; flex-wrap: wrap; gap: 4px; margin: 8px 0 0 15px; }
.evcard__col {
  font-family: Consolas, monospace; font-size: 10px; color: var(--color-text);
  background: var(--color-bg-tertiary); border: 1px solid var(--color-border);
  border-radius: 3px; padding: 1px 6px;
}
.evcard__col i { font-style: normal; color: var(--color-text-light); }

.evcard__summary { margin: 7px 0 0 15px; font-size: 11px; line-height: 1.5; color: var(--color-text-light); }

.evcard__citedby { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px; margin: 8px 0 0 15px; }
.evcard__citedby-label { font-size: 10px; color: #7d8bf5; margin-right: 2px; }
.evcard__citedby-chip {
  font-size: 10px; color: var(--color-text); cursor: pointer;
  background: var(--color-bg-tertiary); border: 1px solid var(--color-border);
  border-radius: 9999px; padding: 1px 8px;
}
.evcard__citedby-chip:hover { border-color: #7d8bf5; }
.evcard__citedby-chip--self {
  cursor: default; color: var(--color-text-light);
  border-style: dashed;
}
</style>
