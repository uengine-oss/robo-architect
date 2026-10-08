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

/**
 * 조사를 **받침으로 고른다.** `을(를)` 은 읽는 사람에게 기계가 쓴 문장으로 보인다 —
 * 이 배너는 고장 났을 때 보는 자리라, 거기서까지 어색하면 신뢰를 깎는다.
 */
function hasFinalConsonant(word) {
  const last = (word || '').trim().slice(-1)
  if (!last) return null
  const code = last.charCodeAt(0)
  if (code < 0xac00 || code > 0xd7a3) return null // 영문·숫자 끝 — 가릴 수 없다
  return (code - 0xac00) % 28 !== 0
}

const withObjectParticle = (word) => `${word}${hasFinalConsonant(word) === false ? '를' : '을'}`
const withSubjectParticle = (word) => `${word}${hasFinalConsonant(word) === false ? '가' : '이'}`

/** 한 줄 요약. **무엇이 안 되는지**를 기능 이름으로, **왜**를 서비스 이름으로 말한다. */
const summary = computed(() => {
  // 배너는 한 줄이다 — 그래서 **할 일 하나**만 적고 자세한 것은 "자세히" 로 넘긴다.
  if (runtime.dockerAvailable === false) {
    return 'Docker Desktop 이 꺼져 있어 서비스를 띄울 수 없습니다 — 실행하면 앱이 스스로 이어서 올립니다.'
  }
  const stuck = [...broken.value, ...degraded.value]
  // 이름을 한 번에 말해 주면 **자세히를 누르지 않고도** 무엇을 고쳐야 하는지 안다.
  const who = stuck.map((s) => s.displayName || s.id).join(' · ')
  const names = runtime.capabilities
    .filter((c) => c.state === 'unavailable')
    .map((c) => c.displayName)
  if (names.length > 0) {
    return `지금 ${withObjectParticle(names.join(' · '))} 쓸 수 없습니다 — ${withSubjectParticle(who)} 준비되지 않았습니다.`
  }
  return `${withSubjectParticle(who)} 준비되지 않았습니다 — 쓰는 기능에 따라 영향이 없을 수도 있습니다.`
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
