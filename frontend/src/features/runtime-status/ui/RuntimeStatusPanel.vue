<script setup>
/**
 * 지금 **무엇이 준비됐고 무엇이 안 됐는지** 보여 주는 자리 (spec 058 T028 · US1).
 *
 * ## 왜 필요한가
 *
 * 이것이 없으면 모든 고장이 **"앱이 안 켜진다" 한 문장**으로 합쳐진다. 실제로 그랬다 —
 *
 * ```
 * 백엔드가 이유를 대고 멈춰도   화면에는 가장 먼저 실패한 API 호출이 보였다
 *                           ("Failed to fetch contexts (HTTP 503)")
 * pdf2bpmn 이 자격 문제로 502  compose 는 healthy · /healthz 는 200 — 겉으로 멀쩡하다.
 *                           사용자는 BPMN 생성을 누르고 나서야 실패를 본다
 * analyzer 가 죽으면          "코드 분석을 못 쓴다" 를 아무도 말해 주지 않았다
 * ```
 *
 * 2026-10-07 에 감독을 배선하자(058 T018) 1분 만에 **두 서비스가 잘못 적혀 있던 것**이
 * 드러났다. 그런데 그건 로그를 뒤져서 안 것이고, **사용자에게는 여전히 안 보였다.**
 * 이 화면이 그 간격을 메운다.
 *
 * ## 세 가지를 지킨다
 *
 * ```
 * ① 이름을 댄다        서비스 이름 · 상태 · **왜 그런지**(메인이 판정한 이유 그대로)
 * ② 기능으로 옮긴다     "analyzer 실패" → **"레거시 코드 탐색을 못 씁니다"**
 *                     나머지 기능은 그대로 쓸 수 있다고도 말한다
 * ③ 할 일을 준다       다시 시도 · 로그 열기. 막다른 화면을 주지 않는다
 * ```
 *
 * 판정은 여기서 하지 않는다 — 메인(`supervisor.decideState`)이 하고 스토어가 들고
 * 있는 것을 그대로 그린다. 화면이 다시 계산하면 같은 사실이 두 곳에 생겨 어긋난다.
 */
import { computed, ref } from 'vue'
import { useRuntimeStore } from '../runtime.store.js'

const runtime = useRuntimeStore()
const busyService = ref(null)
const actionError = ref(null)

const STATE_TEXT = {
  ready: '준비됨',
  starting: '준비 중',
  degraded: '일부만 됨',
  failed: '실패',
  stopped: '내려감',
  pending: '확인 전',
}

/**
 * 이름은 **메인이 준다**(`runtime-state.DISPLAY_NAMES`). 여기에 또 적어 두면 같은
 * 사실이 두 곳에 생기고, 한쪽만 고친 날 화면과 로그가 다른 이름을 말한다.
 * 못 받았을 때만 id 로 떨어진다.
 */
const label = (service) => service.displayName || service.id

/** 문제 있는 것을 위로. 사람이 **먼저 봐야 할 것**이 먼저 와야 한다. */
const ORDER = { failed: 0, stopped: 1, degraded: 2, starting: 3, pending: 4, ready: 5 }
const sorted = computed(() =>
  [...runtime.services].sort(
    (a, b) => (ORDER[a.state] ?? 9) - (ORDER[b.state] ?? 9) || label(a).localeCompare(label(b)),
  ),
)

const blocked = computed(() => runtime.capabilities.filter((c) => c.state !== 'available'))
const usable = computed(() => runtime.capabilities.filter((c) => c.state === 'available'))

async function retry(serviceId) {
  if (busyService.value) return
  busyService.value = serviceId
  actionError.value = null
  try {
    const result = await runtime.retryService(serviceId)
    if (result && result.ok === false) actionError.value = result.error || '다시 시도하지 못했습니다.'
  } catch (e) {
    actionError.value = e?.message || String(e)
  } finally {
    busyService.value = null
  }
}

async function diagnostics(serviceId) {
  try {
    await runtime.openDiagnostics(serviceId)
  } catch (e) {
    actionError.value = e?.message || String(e)
  }
}
</script>

<template>
  <section class="rts">
    <header class="rts__head">
      <h3 class="rts__title">실행 상태</h3>
      <span v-if="runtime.releaseId" class="rts__release">{{ runtime.releaseId }}</span>
    </header>

    <!-- **아직 못 받은 것과 "서비스가 없다" 는 다른 사실이다.** -->
    <p v-if="!runtime.supported" class="rts__note">
      이 창은 브라우저에서 열려 있어 실행 상태를 감독하지 않습니다.
    </p>
    <p v-else-if="!runtime.loaded" class="rts__note">실행 상태를 확인하고 있습니다…</p>

    <template v-else>
      <!-- 컨테이너 실행 환경 자체가 없을 때는 서비스 목록보다 이것이 먼저다. -->
      <p v-if="runtime.dockerAvailable === false" class="rts__note rts__note--bad">
        컨테이너 실행 환경(Docker)이 응답하지 않습니다. Docker Desktop 을 실행한 뒤
        다시 시도하세요 — 앱이 알아서 기다렸다가 이어서 올립니다.
      </p>

      <ul class="rts__list">
        <li v-for="s in sorted" :key="s.id" class="rts__row" :class="`rts__row--${s.state}`">
          <span class="rts__dot" :class="`rts__dot--${s.state}`" aria-hidden="true"></span>
          <span class="rts__name">{{ label(s) }}</span>
          <span class="rts__id">{{ s.id }}</span>
          <span class="rts__state">{{ STATE_TEXT[s.state] || s.state }}</span>
          <span v-if="s.owner === 'external'" class="rts__owner">밖에서 돎</span>
          <span class="rts__reason">{{ s.stateReason || '' }}</span>
          <span class="rts__acts">
            <button
              v-if="s.state === 'failed' || s.state === 'stopped' || s.state === 'degraded'"
              class="rts__btn"
              :disabled="busyService === s.id"
              @click="retry(s.id)"
            >{{ busyService === s.id ? '다시 시도 중…' : '다시 시도' }}</button>
            <button class="rts__btn rts__btn--quiet" @click="diagnostics(s.id)">기록 보기</button>
          </span>
        </li>
      </ul>

      <!-- **서비스 이름만으로는 사람이 자기가 무엇을 못 하는지 모른다.** -->
      <div v-if="blocked.length" class="rts__caps rts__caps--blocked">
        <h4 class="rts__capsTitle">지금 못 쓰는 기능</h4>
        <p v-for="c in blocked" :key="c.id" class="rts__cap">
          <b>{{ c.displayName }}</b>
          <span class="rts__capWhy">{{ c.blockedReason || '필요한 서비스가 아직 준비되지 않았습니다.' }}</span>
        </p>
      </div>
      <p v-if="usable.length" class="rts__caps rts__caps--ok">
        쓸 수 있는 기능 — {{ usable.map((c) => c.displayName).join(' · ') }}
      </p>

      <!-- 분석이 설계를 지우는 구성은 기동 때 잠긴다. 그 사실을 여기서도 말한다. -->
      <p v-if="runtime.graphGuard && runtime.graphGuard.separated === false" class="rts__note rts__note--bad">
        설계와 분석이 같은 저장소를 가리키고 있어 <b>레거시 코드 탐색을 잠갔습니다</b> —
        분석은 대상 저장소를 비우고 다시 쓰기 때문입니다.
      </p>

      <p v-if="actionError" class="rts__note rts__note--bad">{{ actionError }}</p>
    </template>
  </section>
</template>

<style scoped>
.rts { padding: 12px 14px; font-size: 12px; color: #222; }
.rts__head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; }
.rts__title { margin: 0; font-size: 13px; font-weight: 700; }
.rts__release { font-size: 11px; opacity: 0.6; font-family: ui-monospace, monospace; }
.rts__note { margin: 6px 0; opacity: 0.85; }
.rts__note--bad { color: #7f231c; background: #fdecea; border: 1px solid #f5c6c2; border-radius: 4px; padding: 6px 8px; opacity: 1; }
.rts__list { list-style: none; margin: 0; padding: 0; }
.rts__row { display: flex; align-items: center; gap: 8px; padding: 4px 0; border-bottom: 1px solid #eee; }
.rts__dot { width: 8px; height: 8px; border-radius: 50%; background: #bbb; flex: none; }
.rts__dot--ready { background: #2e9e5b; }
.rts__dot--degraded { background: #e0a21a; }
.rts__dot--failed, .rts__dot--stopped { background: #d14; }
.rts__dot--starting, .rts__dot--pending { background: #58a; }
.rts__name { font-weight: 600; }
.rts__id { font-family: ui-monospace, monospace; font-size: 11px; opacity: 0.5; }
.rts__state { font-size: 11px; opacity: 0.8; }
.rts__owner { font-size: 11px; opacity: 0.6; border: 1px solid #ddd; border-radius: 3px; padding: 0 4px; }
.rts__reason { flex: 1 1 auto; opacity: 0.8; }
.rts__acts { display: flex; gap: 6px; flex: none; }
.rts__btn { padding: 2px 8px; border: 1px solid #ccc; border-radius: 4px; background: #fff; font-size: 11px; cursor: pointer; }
.rts__btn:disabled { opacity: 0.6; cursor: default; }
.rts__btn--quiet { border-color: #e3e3e3; opacity: 0.8; }
.rts__caps { margin-top: 10px; }
.rts__capsTitle { margin: 0 0 4px; font-size: 12px; }
.rts__cap { margin: 2px 0; }
.rts__capWhy { margin-left: 6px; opacity: 0.85; }
.rts__caps--ok { opacity: 0.75; }
</style>
