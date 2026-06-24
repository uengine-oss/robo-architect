<template>
  <div class="sviz">
    <p class="sviz__hint">서브도메인을 드래그해 배치하거나 분류를 직접 고르세요. 우상단=Core(차별점), 좌하단=Generic.</p>

    <!-- 2×2 Core Domain Chart -->
    <div class="sviz__chart" ref="chartEl">
      <div class="sviz__axis-y">전략적 중요도 →</div>
      <div class="sviz__axis-x">차별성(Differentiation) →</div>
      <div class="sviz__quad sviz__quad--tl">전략적 Supporting</div>
      <div class="sviz__quad sviz__quad--tr">Core</div>
      <div class="sviz__quad sviz__quad--bl">Generic</div>
      <div class="sviz__quad sviz__quad--br">전술적 Supporting</div>
      <div
        v-for="(c, i) in items"
        :key="c.subDomain || i"
        class="sviz__chip"
        :class="`is-${(c.kind || 'SUPPORTING').toLowerCase()}`"
        :style="chipStyle(c)"
        @pointerdown="startDrag(i, $event)"
        :title="c.rationale || ''"
      >{{ c.subDomain }}</div>
    </div>

    <!-- 분류 리스트 + 라디오 -->
    <table class="sviz__table">
      <thead><tr><th>서브도메인</th><th>분류</th><th>근거 / build-vs-buy</th></tr></thead>
      <tbody>
        <tr v-for="(c, i) in items" :key="i">
          <td>{{ c.subDomain }}</td>
          <td>
            <label v-for="k in KINDS" :key="k" class="sviz__radio">
              <input type="radio" :name="`k${i}`" :value="k" :checked="c.kind === k" @change="setKind(i, k)" /> {{ k[0] }}
            </label>
          </td>
          <td>
            <input class="sviz__rat" v-model="c.rationale" placeholder="근거" />
            <input v-if="c.kind === 'GENERIC'" class="sviz__rat" v-model="c.buildVsBuy" placeholder="외부 솔루션 후보" />
          </td>
        </tr>
      </tbody>
    </table>

    <!-- 차별성 피드백(루트 메모리 시드) -->
    <div class="sviz__diff">
      <label>이 변경의 핵심 차별성(있으면) — 프로젝트 전략 메모리에 기록</label>
      <input class="sviz__rat" :value="model.differentiation?.differentiator || ''" @input="setDifferentiator($event.target.value)" placeholder="예: 추천 정확도" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const model = defineModel({ type: Object, required: true })
const KINDS = ['CORE', 'SUPPORTING', 'GENERIC']
const chartEl = ref(null)
// 칩 위치(UI 전용, 비영속). kind 로부터 초기화.
const pos = ref({})

const items = computed(() => model.value.classifications || (model.value.classifications = []))

function basePos(kind) {
  if (kind === 'CORE') return { x: 0.75, y: 0.78 }
  if (kind === 'GENERIC') return { x: 0.22, y: 0.22 }
  return { x: 0.5, y: 0.55 }
}
function chipStyle(c) {
  const p = pos.value[c.subDomain] || (pos.value[c.subDomain] = basePos(c.kind))
  return { left: `${p.x * 100}%`, bottom: `${p.y * 100}%` }
}
function kindFromPos(x, y) {
  if (x > 0.5 && y > 0.5) return 'CORE'
  if (x <= 0.5 && y <= 0.5) return 'GENERIC'
  return 'SUPPORTING'
}

let dragIdx = -1
function startDrag(i, e) {
  dragIdx = i
  window.addEventListener('pointermove', onMove)
  window.addEventListener('pointerup', endDrag)
}
function onMove(e) {
  if (dragIdx < 0 || !chartEl.value) return
  const r = chartEl.value.getBoundingClientRect()
  const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))
  const y = Math.min(1, Math.max(0, 1 - (e.clientY - r.top) / r.height))
  const c = items.value[dragIdx]
  pos.value[c.subDomain] = { x, y }
  c.kind = kindFromPos(x, y)
}
function endDrag() {
  dragIdx = -1
  window.removeEventListener('pointermove', onMove)
  window.removeEventListener('pointerup', endDrag)
}

function setKind(i, k) {
  const c = items.value[i]
  c.kind = k
  pos.value[c.subDomain] = basePos(k)
}
function setDifferentiator(v) {
  if (!model.value.differentiation) model.value.differentiation = {}
  model.value.differentiation.differentiator = v
}
</script>

<style scoped>
.sviz__hint { font-size: 11px; color: var(--color-text-light); margin: 0 0 8px; }
.sviz__chart { position: relative; width: 100%; aspect-ratio: 1.6/1; max-height: 320px; border: 1px solid var(--color-border); border-radius: 8px; background:
  linear-gradient(to right, transparent 49.7%, var(--color-border) 49.7%, var(--color-border) 50.3%, transparent 50.3%),
  linear-gradient(to bottom, transparent 49.7%, var(--color-border) 49.7%, var(--color-border) 50.3%, transparent 50.3%);
  overflow: hidden; margin-bottom: 10px; }
.sviz__quad { position: absolute; font-size: 10px; color: var(--color-text-light); padding: 4px 6px; pointer-events: none; }
.sviz__quad--tl { top: 0; left: 0; }
.sviz__quad--tr { top: 0; right: 0; color: var(--color-accent); font-weight: 600; }
.sviz__quad--bl { bottom: 16px; left: 0; }
.sviz__quad--br { bottom: 16px; right: 0; }
.sviz__axis-x { position: absolute; bottom: 1px; left: 50%; transform: translateX(-50%); font-size: 9px; color: var(--color-text-light); }
.sviz__axis-y { position: absolute; top: 50%; left: 2px; transform: rotate(-90deg) translateX(50%); transform-origin: left; font-size: 9px; color: var(--color-text-light); }
.sviz__chip { position: absolute; transform: translate(-50%, 50%); padding: 3px 8px; border-radius: 12px; font-size: 11px; cursor: grab; user-select: none; white-space: nowrap; border: 1px solid; }
.sviz__chip.is-core { background: var(--status-blue-bg); color: var(--status-blue-fg); border-color: var(--color-accent); }
.sviz__chip.is-supporting { background: var(--color-bg-tertiary); color: var(--color-text); border-color: var(--color-border); }
.sviz__chip.is-generic { background: transparent; color: var(--color-text-light); border-color: var(--color-border); }
.sviz__table { width: 100%; border-collapse: collapse; font-size: 12px; }
.sviz__table th, .sviz__table td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--color-border); vertical-align: top; }
.sviz__radio { margin-right: 8px; font-size: 11px; }
.sviz__rat { width: 100%; font-size: 11px; padding: 2px 6px; margin: 1px 0; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-bg-secondary); color: var(--color-text); box-sizing: border-box; }
.sviz__diff { margin-top: 10px; }
.sviz__diff label { font-size: 11px; color: var(--color-text-light); display: block; margin-bottom: 3px; }
</style>
