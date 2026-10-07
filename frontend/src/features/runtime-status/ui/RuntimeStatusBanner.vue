<script setup>
/**
 * 실행 상태를 **한 줄로** 말하고, 누르면 자세히 보여 주는 자리 (spec 058 US1).
 *
 * ## 왜 배너인가
 *
 * 상태 화면을 탭 하나로 두면 **아무도 안 본다.** 고장은 사용자가 다른 일을 하는
 * 중에 나고, 그때 보이는 것은 "왜 안 되지" 하는 그 화면이다. 그래서 문제가 있을
 * 때만 작업 화면 위에 한 줄로 뜬다.
 *
 * ## 멀쩡하면 아무것도 안 띄운다
 *
 * 전부 `ready` 면 이 배너는 **없다.** 늘 떠 있는 초록 띠는 며칠이면 안 보이게 되고,
 * 정작 빨갛게 바뀐 날에도 안 보인다.
 */
import { computed, ref } from 'vue'
import { useRuntimeStore } from '../runtime.store.js'
import RuntimeStatusPanel from './RuntimeStatusPanel.vue'

const runtime = useRuntimeStore()
const open = ref(false)

const broken = computed(() => runtime.broken)
const degraded = computed(() => runtime.degraded)

/** 띄울 이유가 있는가. **멀쩡하면 아무것도 안 띄운다.** */
const show = computed(() => {
  if (!runtime.supported || !runtime.loaded) return false
  return broken.value.length > 0 || degraded.value.length > 0 || runtime.dockerAvailable === false
})

const tone = computed(() => (broken.value.length > 0 || runtime.dockerAvailable === false ? 'bad' : 'warn'))

/** 한 줄 요약. **무엇이 안 되는지**를 기능 이름으로 먼저 말한다. */
const summary = computed(() => {
  if (runtime.dockerAvailable === false) return '컨테이너 실행 환경(Docker)이 응답하지 않습니다.'
  const blockedCaps = runtime.capabilities.filter((c) => c.state === 'unavailable')
  const names = blockedCaps.map((c) => c.displayName)
  const services = [...broken.value, ...degraded.value].length
  if (names.length > 0) {
    return `${names.join(' · ')} 을(를) 지금 쓸 수 없습니다 — 서비스 ${services}개가 준비되지 않았습니다.`
  }
  return `서비스 ${services}개가 준비되지 않았습니다 — 쓰는 기능에 따라 영향이 없을 수도 있습니다.`
})
</script>

<template>
  <div v-if="show" class="rbn" :class="`rbn--${tone}`">
    <span class="rbn__tag">실행 상태</span>
    <span class="rbn__text">{{ summary }}</span>
    <button class="rbn__more" @click="open = !open">
      {{ open ? '접기' : '자세히' }}
    </button>
  </div>
  <div v-if="show && open" class="rbn__drawer">
    <RuntimeStatusPanel />
  </div>
</template>

<style scoped>
.rbn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  font-size: 12px;
  border-bottom: 1px solid transparent;
}
.rbn--bad { background: #fdecea; border-bottom-color: #f5c6c2; color: #7f231c; }
.rbn--warn { background: #fff6e0; border-bottom-color: #f2dca8; color: #7a5a12; }
.rbn__tag { font-weight: 700; }
.rbn__text { flex: 1 1 auto; }
.rbn__more {
  padding: 2px 10px;
  border: 1px solid currentColor;
  border-radius: 4px;
  background: #fff;
  color: inherit;
  font-size: 12px;
  cursor: pointer;
  opacity: 0.9;
}
.rbn__drawer { border-bottom: 1px solid #eee; background: #fafafa; }
</style>
