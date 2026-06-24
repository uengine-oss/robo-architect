<template>
  <div class="stage-ro-wrap">
    <!-- 카드 시각화 ↔ Markdown 보기 토글(읽기전용 재열람) -->
    <div class="stage-ro-seg">
      <button class="stage-ro-seg-btn" :class="{ 'is-on': viewPref.mode === 'card' }" @click="viewPref.mode = 'card'">카드</button>
      <button class="stage-ro-seg-btn" :class="{ 'is-on': viewPref.mode === 'markdown' }" @click="viewPref.mode = 'markdown'">Markdown</button>
    </div>
    <fieldset v-if="viewPref.mode === 'card'" disabled class="stage-ro">
      <component :is="viz" :modelValue="snapshot" @update:modelValue="noop" />
    </fieldset>
    <StageMarkdownView v-else :stage="stage" :artifact="snapshot" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import DiscoverViz from './DiscoverViz.vue'
import DecomposeViz from './DecomposeViz.vue'
import StrategizeViz from './StrategizeViz.vue'
import ConnectViz from './ConnectViz.vue'
import DefineViz from './DefineViz.vue'
import TacticalViz from './TacticalViz.vue'
import StageMarkdownView from './StageMarkdownView.vue'
import { stageViewPref } from './stageMarkdown'

const props = defineProps({
  stage: { type: String, required: true },
  artifact: { type: Object, default: () => ({}) },
})

const viewPref = stageViewPref
const VIZ = { DISCOVER: DiscoverViz, DECOMPOSE: DecomposeViz, STRATEGIZE: StrategizeViz, CONNECT: ConnectViz, DEFINE: DefineViz, TACTICAL: TacticalViz }
const viz = computed(() => VIZ[props.stage])
// 원본 보호용 스냅샷(읽기 전용 표시는 모델을 건드리지 않게 복제).
const snapshot = computed(() => { try { return JSON.parse(JSON.stringify(props.artifact || {})) } catch { return {} } })
function noop() {}
</script>

<style scoped>
.stage-ro-wrap { min-width: 0; }
.stage-ro-seg { display: inline-flex; border: 1px solid var(--color-border); border-radius: 5px; overflow: hidden; margin-bottom: 8px; }
.stage-ro-seg-btn { padding: 2px 9px; font-size: 11px; background: transparent; color: var(--color-text-light); border: none; cursor: pointer; }
.stage-ro-seg-btn.is-on { background: var(--color-accent); color: #fff; }
.stage-ro { border: none; padding: 0; margin: 0; min-width: 0; pointer-events: none; opacity: 0.94; }
</style>
