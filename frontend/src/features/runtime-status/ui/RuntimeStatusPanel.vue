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

const props = defineProps({
  /** 배너 안에 들어갈 때는 제목을 숨긴다 — 배너가 이미 같은 말을 했다. */
  embedded: { type: Boolean, default: false },
})

const runtime = useRuntimeStore()
const busyService = ref(null)
const actionError = ref(null)

/** 어느 서비스의 로그를 펼쳐 놨나. 한 번에 하나만 — 둘을 펼치면 화면이 로그로 덮인다. */
const openLogsFor = ref(null)
const logs = ref(null)
const logsLoading = ref(false)
const logsError = ref(null)
/** 전문을 펼쳤나. 처음에는 **눈에 걸릴 줄만** 보여준다. */
const showAllLines = ref(false)

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

/** 폴더를 여는 길은 남겨 둔다 — 전문을 봐야 할 때가 있고, **파일이 원본**이다. */
async function openLogFolder(serviceId) {
  try {
    await runtime.openDiagnostics(serviceId)
  } catch (e) {
    actionError.value = e?.message || String(e)
  }
}

/**
 * 그 서비스의 로그를 **그 자리에서** 읽는다.
 *
 * 왜 이 버튼이 필요한가: 패널은 이미 "pdf2bpmn 실패 — 컨테이너/프로세스가 실행 중이
 * 아닙니다" 까지 말한다. 그런데 **왜 그렇게 됐는지**는 그 문장에 없다. 2026-10-07 에
 * 실제로 그랬다 — 답은 컨테이너 로그의 "Shutting down" 두 줄이었고, 그걸 보려면
 * 사람이 `docker logs` 를 쳐야 했다. 받는 사람은 그걸 못 한다.
 */
async function toggleLogs(serviceId) {
  if (openLogsFor.value === serviceId) {
    openLogsFor.value = null
    return
  }
  openLogsFor.value = serviceId
  logs.value = null
  logsError.value = null
  showAllLines.value = false
  logsLoading.value = true
  try {
    const result = await runtime.fetchServiceLogs(serviceId)
    if (result && result.ok === false) logsError.value = result.error || '로그를 읽지 못했습니다.'
    // IPC 는 `{ ok, data }` 로 오고, 브라우저 모드에서는 `{ ok: false }` 다.
    else logs.value = result?.data ?? result
  } catch (e) {
    logsError.value = e?.message || String(e)
  } finally {
    logsLoading.value = false
  }
}

/** 처음에는 **눈에 걸릴 줄**만. 없으면 마지막 몇 줄로 떨어진다 — 빈 칸을 주지 않는다. */
const shownLines = computed(() => {
  if (!logs.value) return []
  if (showAllLines.value) return logs.value.lines
  if (logs.value.highlights?.length) return logs.value.highlights
  return logs.value.lines.slice(-8)
})

/**
 * 고른 줄이 없으면 **그렇다고 말한다.**
 *
 * 2026-10-08 에 사용자가 degraded 상태에서 열어 보고 평범한 `healthz 200` 줄들을
 * 받았다. 그 줄들이 조용히 떨어진 마지막 몇 줄이었는데, **원인처럼 읽힌다.**
 * 그리고 실제로 원인은 로그에 없다 — pdf2bpmn 의 401 은 프로브가 **컨테이너 밖에서**
 * 재서 안 것이고, 그래서 맨 위의 판정 이유가 유일한 근거다. 그 사실을 적어 준다.
 */
const fallbackNote = computed(() => {
  if (!logs.value || showAllLines.value) return null
  if (logs.value.highlights?.length) return null
  if (!logs.value.lines.length) return null
  return '로그에서 눈에 걸린 줄이 없습니다 — 마지막 줄들을 보여줍니다. 원인은 위의 판정 이유에 있을 수 있습니다.'
})

const SOURCE_TEXT = {
  container: '컨테이너 로그',
  backend: '백엔드(호스트 프로세스) 로그',
  external: '이 PC 가 띄운 서비스가 아닙니다',
  unavailable: '로그를 읽지 못했습니다',
}
</script>

<template>
  <section class="rts">
    <header v-if="!props.embedded || runtime.releaseId" class="rts__head">
      <h3 v-if="!props.embedded" class="rts__title">실행 상태</h3>
      <span v-if="runtime.releaseId" class="rts__release">{{ runtime.releaseId }}</span>
    </header>

    <!-- **아직 못 받은 것과 "서비스가 없다" 는 다른 사실이다.** -->
    <p v-if="!runtime.supported" class="rts__note">
      이 창은 브라우저에서 열려 있어 실행 상태를 감독하지 않습니다.
    </p>
    <p v-else-if="!runtime.loaded" class="rts__note">실행 상태를 확인하고 있습니다…</p>

    <template v-else>
      <!--
        컨테이너 실행 환경 자체가 없을 때는 서비스 목록보다 이것이 먼저다 (T030).

        한 줄로는 모자랐다. 받는 사람은 도커를 모르고 물어볼 사람이 없으니,
        **무엇을 해야 하는지 · 얼마나 걸리는지 · 그다음에 뭘 해야 하는지**가 있어야
        한다. 마지막 줄이 핵이다 — 앱이 스스로 이어서 올리므로 **아무것도 안 해도
        된다**. 그 사실을 안 적으면 사용자가 앱을 끄고 다시 켠다.
      -->
      <div v-if="runtime.dockerAvailable === false" class="rts__docker">
        <p class="rts__dockerTitle">컨테이너 실행 환경(Docker)이 응답하지 않습니다</p>
        <p class="rts__dockerWhy">
          이 앱은 서비스 여러 개를 컨테이너로 띄웁니다. 그 실행 환경이 꺼져 있으면
          설계·분석·코드 생성이 모두 멈춥니다 — <b>앱이 고장 난 것은 아닙니다.</b>
        </p>
        <ol class="rts__dockerSteps">
          <li><b>Docker Desktop</b> 을 실행합니다(시작 메뉴에서 "Docker Desktop").</li>
          <li>고래 아이콘이 <b>초록색</b>이 될 때까지 기다립니다. 보통 30초쯤 걸립니다.</li>
          <li>
            그러면 <b>이 앱이 스스로 이어서 올립니다</b> — 다시 켜지 않아도 됩니다.
            이 목록이 저절로 바뀝니다.
          </li>
        </ol>
        <p class="rts__dockerFoot">
          5초마다 다시 확인하고 있습니다. 10분이 지나도 이 안내가 남아 있으면
          설치 담당자에게 전해 주세요.
        </p>
      </div>
      <!-- **아직 못 쟨 것**(`null`)에는 아무 안내도 띄우지 않는다 — 모르는 것을
           "도커가 없다" 로 바꿔 말하면 멀쩡한 PC 에 그 안내가 뜬다. -->
      <p v-else-if="runtime.dockerAvailable === null" class="rts__note">
        컨테이너 실행 환경을 확인하고 있습니다…
      </p>

      <ul class="rts__list">
        <template v-for="s in sorted" :key="s.id">
        <li class="rts__row" :class="`rts__row--${s.state}`">
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
            <button
              class="rts__btn"
              :class="{ 'rts__btn--on': openLogsFor === s.id }"
              @click="toggleLogs(s.id)"
            >{{ openLogsFor === s.id ? '로그 접기' : '로그 보기' }}</button>
            <button class="rts__btn rts__btn--quiet" @click="openLogFolder(s.id)">폴더 열기</button>
          </span>
        </li>
        <!-- 로그는 그 서비스 **바로 아래**에 펼친다 — 어느 서비스의 것인지 섞이지 않게. -->
        <li v-if="openLogsFor === s.id" class="rts__logs">
          <!-- 판정 이유가 **1차 근거**다. 로그보다 먼저 읽혀야 한다. -->
          <p v-if="s.stateReason" class="rts__logsWhy">{{ s.stateReason }}</p>
          <p v-if="logsLoading" class="rts__note">로그를 읽고 있습니다…</p>
          <p v-else-if="logsError" class="rts__note rts__note--bad">{{ logsError }}</p>
          <template v-else-if="logs">
            <p class="rts__logsHead">
              <span>{{ SOURCE_TEXT[logs.source] || logs.source }}</span>
              <span v-if="logs.containerName" class="rts__logsName">{{ logs.containerName }}</span>
              <button
                v-if="logs.lines.length > shownLines.length || showAllLines"
                class="rts__btn rts__btn--quiet"
                @click="showAllLines = !showAllLines"
              >{{ showAllLines ? `눈에 걸린 줄만` : `전문 ${logs.lines.length}줄` }}</button>
            </p>
            <p v-if="logs.note" class="rts__note">{{ logs.note }}</p>
            <p v-if="fallbackNote" class="rts__note">{{ fallbackNote }}</p>
            <pre v-if="shownLines.length" class="rts__logsBody">{{ shownLines.join('\n') }}</pre>
            <p class="rts__logsFoot">비밀 값은 가려서 보여 줍니다. 전문은 "폴더 열기" 의 파일에 있습니다.</p>
          </template>
        </li>
        </template>
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
.rts__btn--on { border-color: #58a; color: #24557e; }
.rts__docker {
  margin: 6px 0 10px;
  padding: 10px 12px;
  border: 1px solid #f5c6c2;
  border-radius: 4px;
  background: #fdecea;
  color: #7f231c;
}
.rts__dockerTitle { margin: 0 0 4px; font-weight: 700; }
.rts__dockerWhy { margin: 0 0 6px; }
.rts__dockerSteps { margin: 0 0 6px; padding-left: 20px; }
.rts__dockerSteps li { margin: 2px 0; }
.rts__dockerFoot { margin: 0; font-size: 11px; opacity: 0.8; }
.rts__logs { padding: 8px 0 10px 16px; border-bottom: 1px solid #eee; background: #fafafa; }
.rts__logsWhy { margin: 0 0 6px; font-weight: 600; }
.rts__logsHead { display: flex; align-items: center; gap: 8px; margin: 0 0 4px; font-size: 11px; opacity: 0.8; }
.rts__logsName { font-family: ui-monospace, monospace; opacity: 0.7; }
.rts__logsBody {
  margin: 0;
  padding: 8px 10px;
  max-height: 260px;
  overflow: auto;
  background: #fff;
  border: 1px solid #e7e7e7;
  border-radius: 4px;
  font-family: ui-monospace, monospace;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}
.rts__logsFoot { margin: 6px 0 0; font-size: 11px; opacity: 0.6; }
.rts__caps { margin-top: 10px; }
.rts__capsTitle { margin: 0 0 4px; font-size: 12px; }
.rts__cap { margin: 2px 0; }
.rts__capWhy { margin-left: 6px; opacity: 0.85; }
.rts__caps--ok { opacity: 0.75; }
</style>
