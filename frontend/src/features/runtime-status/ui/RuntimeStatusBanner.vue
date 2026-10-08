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
import { screenTells } from '../messages.js'
import RuntimeStatusPanel from './RuntimeStatusPanel.vue'

const runtime = useRuntimeStore()
const open = ref(false)

/**
 * 판정은 `../messages.js` 가 한다 — 템플릿에 흩어 두면 **검사를 걸 자리가 없다**
 * (T031 이 요구하는 "모든 경우에 이름·기능·할 일" 을 세려면 순수 함수여야 한다).
 * 배너는 그 결과를 **한 줄로** 그릴 뿐이다.
 */
const told = computed(() =>
  screenTells({
    services: runtime.services,
    capabilities: runtime.capabilities,
    dockerAvailable: runtime.dockerAvailable,
    graphGuard: runtime.graphGuard,
  }),
)

/** 띄울 이유가 있는가. **멀쩡하면 아무것도 안 띄운다.** */
const show = computed(() => {
  if (!runtime.supported || !runtime.loaded) return false
  return told.value.noticed
})

const tone = computed(() => (told.value.tone === 'bad' ? 'bad' : 'warn'))
const summary = computed(() => told.value.headline)
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
    <!-- 배너가 이미 "실행 상태" 라고 말했다. 패널이 또 말하면 같은 제목이 두 번이다. -->
    <RuntimeStatusPanel :embedded="true" />
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
