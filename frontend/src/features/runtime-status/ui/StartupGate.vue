<script setup>
/**
 * 기동 중에 **어느 단계인지**를 말하는 화면 (spec 058 T027 · US1).
 *
 * ## 무엇을 가르나
 *
 * 기동에 수 분이 걸리는 것은 정상이다(2GB 이미지 적재 · 컨테이너 10개 · 백엔드).
 * 문제는 그 동안 화면이 **아무 말도 안 했다**는 것이다. 그러면 사람은
 * **"오래 걸리는 중"과 "멎었다"를 구별할 수 없다.**
 *
 * 그래서 이 화면은 둘을 가른다 —
 *
 * ```
 * 준비 중인 서비스 이름        지금 무엇을 기다리는가
 * **마지막 진전 시각**        90초 넘게 아무것도 안 바뀌면 그 사실을 말한다
 * 그래도 들어가기             무한 대기 금지. 막다른 화면을 주지 않는다
 * ```
 *
 * ## 막지 않는다 — 가린다
 *
 * 이 화면은 **쓸 수 있는 기능이 하나도 없을 때만** 뜬다. 하나라도 열려 있으면
 * 배너로 내려간다(`RuntimeStatusBanner`). 멀쩡한 기능까지 막아 두면, 고장 하나가
 * 앱 전체를 세우는 **지금과 똑같은 일**이 된다.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRuntimeStore } from '../runtime.store.js'
import RuntimeStatusPanel from './RuntimeStatusPanel.vue'

const runtime = useRuntimeStore()
const now = ref(Date.now())
const dismissed = ref(false)
const detail = ref(false)
let timer = null

onMounted(() => { timer = setInterval(() => { now.value = Date.now() }, 1000) })
onUnmounted(() => { if (timer) clearInterval(timer) })

const waiting = computed(() =>
  runtime.services.filter((s) => s.state === 'starting' || s.state === 'pending'),
)

/** 쓸 수 있는 기능이 **하나도 없을 때만** 가린다. */
const nothingUsable = computed(() =>
  runtime.capabilities.length > 0 && runtime.capabilities.every((c) => c.state !== 'available'),
)

const show = computed(() => {
  if (dismissed.value) return false
  if (!runtime.supported || !runtime.loaded) return false
  return runtime.starting && nothingUsable.value
})

const stalled = computed(() => runtime.stalled(now.value))

const sinceProgress = computed(() => {
  if (!runtime.lastProgressAt) return null
  return Math.max(0, Math.round((now.value - runtime.lastProgressAt) / 1000))
})
</script>

<template>
  <div v-if="show" class="sgate">
    <div class="sgate__box">
      <h2 class="sgate__title">준비하고 있습니다</h2>
      <p class="sgate__line">
        서비스 {{ runtime.services.length }}개 중
        <b>{{ runtime.services.filter((s) => s.state === 'ready').length }}개</b> 가 준비됐습니다.
      </p>
      <p v-if="waiting.length" class="sgate__waiting">
        기다리는 중 — {{ waiting.map((s) => s.id).join(' · ') }}
      </p>
      <p v-if="sinceProgress !== null" class="sgate__progress" :class="{ 'sgate__progress--stalled': stalled }">
        <template v-if="stalled">
          <b>{{ sinceProgress }}초 동안 아무것도 바뀌지 않았습니다.</b>
          멎었을 수 있습니다 — 아래에서 무엇을 기다리는지 보고, 필요하면 기록을 여세요.
        </template>
        <template v-else>마지막 진전 {{ sinceProgress }}초 전</template>
      </p>

      <div class="sgate__acts">
        <button class="sgate__btn" @click="detail = !detail">
          {{ detail ? '접기' : '무엇을 기다리는지 보기' }}
        </button>
        <!-- **무한 대기 금지.** 들어가 봐야 아는 것도 있다. -->
        <button class="sgate__btn sgate__btn--quiet" @click="dismissed = true">그래도 들어가기</button>
      </div>

      <div v-if="detail" class="sgate__detail">
        <RuntimeStatusPanel />
      </div>
    </div>
  </div>
</template>

<style scoped>
.sgate {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(20, 22, 26, 0.72);
}
.sgate__box {
  width: min(680px, 92vw);
  max-height: 86vh;
  overflow: auto;
  background: #fff;
  border-radius: 10px;
  padding: 22px 24px;
  box-shadow: 0 18px 50px rgba(0, 0, 0, 0.35);
  color: #222;
}
.sgate__title { margin: 0 0 10px; font-size: 18px; }
.sgate__line { margin: 0 0 6px; font-size: 13px; }
.sgate__waiting { margin: 0 0 6px; font-size: 12px; opacity: 0.8; font-family: ui-monospace, monospace; }
.sgate__progress { margin: 0 0 12px; font-size: 12px; opacity: 0.8; }
.sgate__progress--stalled { opacity: 1; color: #7f231c; }
.sgate__acts { display: flex; gap: 8px; }
.sgate__btn {
  padding: 6px 12px;
  border: 1px solid #ccc;
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
}
.sgate__btn--quiet { opacity: 0.75; }
.sgate__detail { margin-top: 12px; border-top: 1px solid #eee; }
</style>
