<script setup>
import { computed } from 'vue'

/**
 * Clarity Radar (spec 030 — visualization).
 * Pure SVG radar chart over the 10 SpecKit `clarify` ambiguity categories.
 * Each axis = one category; the polygon area = current clarity ratio
 * (1.0 = no in-scope requirement is flagged for that category).
 *
 * Zero dependencies — no chart library needed.
 */
const props = defineProps({
  /** ClarityScoresResponse from GET /clarification/clarity */
  scores: { type: Object, default: null },
  size: { type: Number, default: 380 },
})

// Human-friendly Korean labels for the 10 enum values.
const LABELS = {
  functional_scope: '기능 범위',
  domain_data_model: '도메인 모델',
  interaction_flow: 'UX 흐름',
  non_functional: '비기능',
  integration_dependencies: '외부 연동',
  edge_cases: '엣지 케이스',
  constraints_tradeoffs: '제약·트레이드오프',
  terminology: '용어 일관성',
  completion_signals: '완료 신호',
  misc_placeholders: '미해결/플레이스홀더',
}

// SKILL.md step-8 coverage statuses → radar dot color.
// Same palette the report-summary coverage table uses.
const STATUS_COLOR = {
  clear: '#40c057',        // 초록 — 충분
  resolved: '#228be6',     // 파랑 — 이번 세션에서 해결
  deferred: '#fab005',     // 황색 — cap에 밀려 보류
  outstanding: '#e03131',  // 적색 — 미해결
}
const STATUS_LABEL = {
  clear: 'Clear',
  resolved: 'Resolved',
  deferred: 'Deferred',
  outstanding: 'Outstanding',
}
function dotColor(row) {
  if (row.status) return STATUS_COLOR[row.status] || '#868e96'
  // No scan yet for this scope — fall back to flag-based shade.
  return (row.flaggedCount ?? 0) > 0 ? '#fab005' : '#40c057'
}
function rowTitle(row) {
  const pct = Math.round((row.score ?? 0) * 100)
  const status = row.status ? `상태: ${STATUS_LABEL[row.status] || row.status}` : '상태: 미스캔'
  return `${row.category} — ${pct}% · ${status} · flagged ${row.flaggedCount} · resolved ${row.resolvedCount}`
}

const cx = computed(() => props.size / 2)
const cy = computed(() => props.size / 2 + 6) // slight nudge so labels fit
const radius = computed(() => props.size * 0.35)

const axes = computed(() => {
  const rows = props.scores?.scores || []
  const n = rows.length || 10
  return rows.map((row, i) => {
    const theta = -Math.PI / 2 + (2 * Math.PI * i) / n
    const r = radius.value
    const lx = cx.value + Math.cos(theta) * r
    const ly = cy.value + Math.sin(theta) * r
    // Label sits a bit further out than the axis tick.
    const labelR = r + 18
    const labelX = cx.value + Math.cos(theta) * labelR
    const labelY = cy.value + Math.sin(theta) * labelR
    return {
      ...row,
      theta,
      tickX: lx,
      tickY: ly,
      labelX,
      labelY,
      label: LABELS[row.category] || row.category,
      anchor:
        Math.abs(Math.cos(theta)) < 0.2 ? 'middle' : Math.cos(theta) > 0 ? 'start' : 'end',
      baseline:
        Math.abs(Math.sin(theta)) < 0.2 ? 'middle' : Math.sin(theta) > 0 ? 'hanging' : 'auto',
    }
  })
})

// Polygon path connecting data points (clarity score 0..1).
const polygonPoints = computed(() => {
  return axes.value
    .map((a) => {
      const r = radius.value * (a.score ?? 0)
      const x = cx.value + Math.cos(a.theta) * r
      const y = cy.value + Math.sin(a.theta) * r
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

// Concentric grid rings at 0.25, 0.5, 0.75, 1.0.
const ringRadii = computed(() => [0.25, 0.5, 0.75, 1.0].map((p) => radius.value * p))

const overallPct = computed(() =>
  Math.round((props.scores?.overallScore ?? 0) * 100),
)
const total = computed(() => props.scores?.totalUserStories ?? 0)
const flagged = computed(() => props.scores?.flaggedUserStories ?? 0)
</script>

<template>
  <div class="clarity-radar">
    <div class="cr-header">
      <div class="cr-title">명확화 현황 <span class="cr-scope">({{ scores?.scope?.scopeName || '—' }})</span></div>
      <div class="cr-summary">
        <span class="cr-pct" :class="{
          'cr-pct--high': overallPct >= 80,
          'cr-pct--mid': overallPct >= 50 && overallPct < 80,
          'cr-pct--low': overallPct < 50,
        }">{{ overallPct }}%</span>
        <span class="cr-counts">{{ flagged }}건 모호 / {{ total }}건 전체</span>
      </div>
    </div>

    <svg :width="size" :height="size + 12" class="cr-svg" :viewBox="`0 0 ${size} ${size + 12}`">
      <!-- Grid rings -->
      <circle
        v-for="(r, i) in ringRadii"
        :key="`ring-${i}`"
        :cx="cx" :cy="cy" :r="r"
        fill="none" stroke="rgba(150, 150, 150, 0.18)" stroke-width="1"
      />
      <!-- Axes + labels -->
      <g v-for="(a, i) in axes" :key="`axis-${i}`">
        <line :x1="cx" :y1="cy" :x2="a.tickX" :y2="a.tickY" stroke="rgba(150,150,150,0.25)" stroke-width="1" />
        <text
          :x="a.labelX"
          :y="a.labelY"
          :text-anchor="a.anchor"
          :dominant-baseline="a.baseline"
          class="cr-axis-label"
        >{{ a.label }}<title>{{ rowTitle(a) }}</title></text>
      </g>
      <!-- Data polygon -->
      <polygon
        :points="polygonPoints"
        fill="rgba(34, 139, 230, 0.22)"
        stroke="#228be6" stroke-width="1.5" stroke-linejoin="round"
      />
      <!-- Data point dots — colored by SKILL.md coverage status -->
      <circle
        v-for="(a, i) in axes" :key="`dot-${i}`"
        :cx="cx + Math.cos(a.theta) * radius * (a.score ?? 0)"
        :cy="cy + Math.sin(a.theta) * radius * (a.score ?? 0)"
        r="4"
        :fill="dotColor(a)"
        stroke="#fff" stroke-width="1.5"
      ><title>{{ rowTitle(a) }}</title></circle>
      <!-- Center label -->
      <text :x="cx" :y="cy + 4" text-anchor="middle" class="cr-center">{{ overallPct }}%</text>
    </svg>

    <div class="cr-legend" title="SpecKit clarify 스킬의 4-상태 coverage 모델">
      <span><span class="cr-dot" style="background:#40c057"></span> Clear (충분)</span>
      <span><span class="cr-dot" style="background:#228be6"></span> Resolved (이번 세션)</span>
      <span><span class="cr-dot" style="background:#fab005"></span> Deferred (보류)</span>
      <span><span class="cr-dot" style="background:#e03131"></span> Outstanding (미해결)</span>
    </div>
  </div>
</template>

<style scoped>
.clarity-radar {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 12px;
  border: 1px solid var(--color-border, #e5e5e5); border-radius: 8px;
  background: var(--color-bg-secondary, #fff);
  max-width: 520px;
}
.cr-header { width: 100%; display: flex; justify-content: space-between; align-items: baseline; }
.cr-title { font-weight: 700; font-size: 0.85rem; }
.cr-scope { color: var(--color-text-light, #888); font-weight: 400; font-size: 0.78rem; }
.cr-summary { display: flex; align-items: baseline; gap: 8px; }
.cr-pct { font-weight: 800; font-size: 1.0rem; }
.cr-pct--high { color: #2f9e44; }
.cr-pct--mid { color: #b87b00; }
.cr-pct--low { color: #c92a2a; }
.cr-counts { font-size: 0.72rem; color: var(--color-text-light, #888); }
.cr-svg { display: block; max-width: 100%; }
.cr-axis-label {
  font-size: 10px; fill: var(--color-text, #333); font-weight: 500;
  cursor: help;
}
.cr-center {
  font-size: 14px; font-weight: 800; fill: var(--color-text-light, #888);
}
.cr-legend {
  display: flex; flex-wrap: wrap; gap: 10px; font-size: 0.68rem;
  color: var(--color-text-light, #888); margin-top: 4px;
  justify-content: center;
}
.cr-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 4px; vertical-align: middle; }
</style>
