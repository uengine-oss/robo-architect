<template>
  <div class="cviz">
    <p class="cviz__hint">컨텍스트 간 메시지 흐름. 색=종류(이벤트/명령/질의). 아래에서 각 연동의 종류·동기 여부를 조정하세요.</p>

    <!-- BC 컨텍스트 맵 -->
    <svg class="cviz__map" :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="xMidYMid meet">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
          <path d="M0,0 L7,3 L0,6 Z" fill="currentColor" />
        </marker>
      </defs>
      <g v-for="(it, i) in interactions" :key="'e'+i" :class="`cviz__edge is-${(it.kind||'EVENT').toLowerCase()}`">
        <line :x1="nodePos(it.from).x" :y1="nodePos(it.from).y" :x2="nodePos(it.to).x" :y2="nodePos(it.to).y"
              marker-end="url(#arrow)" :stroke-dasharray="it.kind === 'EVENT' ? '5 4' : '0'" />
        <text :x="(nodePos(it.from).x + nodePos(it.to).x)/2" :y="(nodePos(it.from).y + nodePos(it.to).y)/2 - 3"
              class="cviz__edge-label">{{ it.message }}</text>
      </g>
      <g v-for="(n, i) in nodes" :key="'n'+i">
        <circle :cx="nodePos(n).x" :cy="nodePos(n).y" r="26" class="cviz__node" />
        <text :x="nodePos(n).x" :y="nodePos(n).y + 4" text-anchor="middle" class="cviz__node-label">{{ n }}</text>
      </g>
    </svg>

    <!-- 결합 경고 -->
    <ul v-if="model.couplingWarnings?.length" class="cviz__warn">
      <li v-for="(w, i) in model.couplingWarnings" :key="i">⚠️ {{ w }}</li>
    </ul>

    <!-- 연동 편집 -->
    <table class="cviz__table">
      <thead><tr><th>From → To</th><th>메시지</th><th>종류</th><th>동기</th></tr></thead>
      <tbody>
        <tr v-for="(it, i) in interactions" :key="i">
          <td>{{ it.from }} → {{ it.to }}</td>
          <td><input class="cviz__in" v-model="it.message" /></td>
          <td>
            <select v-model="it.kind" class="cviz__sel">
              <option value="EVENT">Event (pub/sub)</option>
              <option value="COMMAND">Command</option>
              <option value="QUERY">Query</option>
            </select>
          </td>
          <td><input type="checkbox" v-model="it.sync" /></td>
        </tr>
      </tbody>
    </table>

    <div class="cviz__channel">
      <label>메시징 채널</label>
      <input class="cviz__in" :value="model.messagingChannel || 'Kafka'" @input="model.messagingChannel = $event.target.value" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const model = defineModel({ type: Object, required: true })
const W = 480, H = 280

const interactions = computed(() => model.value.interactions || (model.value.interactions = []))
const nodes = computed(() => {
  const set = []
  for (const it of interactions.value) {
    if (it.from && !set.includes(it.from)) set.push(it.from)
    if (it.to && !set.includes(it.to)) set.push(it.to)
  }
  return set
})

function nodePos(name) {
  const idx = nodes.value.indexOf(name)
  const n = Math.max(1, nodes.value.length)
  const angle = (idx / n) * 2 * Math.PI - Math.PI / 2
  const cx = W / 2, cy = H / 2, r = Math.min(W, H) / 2 - 40
  return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
}
</script>

<style scoped>
.cviz__hint { font-size: 11px; color: var(--color-text-light); margin: 0 0 8px; }
.cviz__map { width: 100%; max-height: 300px; border: 1px solid var(--color-border); border-radius: 8px; background: var(--color-bg-secondary); margin-bottom: 10px; }
.cviz__node { fill: var(--color-bg-tertiary); stroke: var(--color-border); }
.cviz__node-label { font-size: 11px; fill: var(--color-text); }
.cviz__edge.is-event { color: #22c55e; stroke: #22c55e; }
.cviz__edge.is-command { color: var(--color-accent); stroke: var(--color-accent); }
.cviz__edge.is-query { color: #f59e0b; stroke: #f59e0b; }
.cviz__edge line { stroke-width: 1.5; }
.cviz__edge-label { font-size: 9px; fill: var(--color-text-light); text-anchor: middle; }
.cviz__warn { margin: 0 0 10px; padding-left: 18px; font-size: 12px; color: var(--color-danger); }
.cviz__table { width: 100%; border-collapse: collapse; font-size: 12px; }
.cviz__table th, .cviz__table td { text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--color-border); }
.cviz__in, .cviz__sel { width: 100%; font-size: 11px; padding: 2px 6px; border: 1px solid var(--color-border); border-radius: 4px; background: var(--color-bg-secondary); color: var(--color-text); box-sizing: border-box; }
.cviz__channel { margin-top: 10px; display: flex; align-items: center; gap: 8px; }
.cviz__channel label { font-size: 11px; color: var(--color-text-light); }
.cviz__channel .cviz__in { max-width: 200px; }
</style>
