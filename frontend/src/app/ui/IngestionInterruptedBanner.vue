<script setup>
/**
 * 적재가 **중단된 채 끝났다**는 사실을 사람에게 말하는 자리.
 *
 * **왜 있어야 하나.** 적재는 지우기로 시작하고 수 분이 걸린다. 그 사이에 앱이
 * 강제 종료되면 남는 것은 **설계가 지워진 프로젝트**인데, 화면에는 아무 말도 없었다 —
 * SSE 는 끊긴 자리에서 끝나고 다시 접속해도 조용하다. 다음에 그 프로젝트를 여는
 * 사람은 "원래 비어 있었나" 와 "지워졌나" 를 구별할 수 없다.
 *
 * 그래서 백엔드가 **지우기 전에** 한 줄 적어 두고(`ingestion/runs.py`), 박동이
 * 끊긴 것을 중단으로 읽는다. 여기는 그 사실을 보여 주고 **사람이 닫을 때까지**
 * 남기는 자리다. 기록은 Postgres 에 있으므로 창을 닫아도, 다른 PC 에서 열어도,
 * 앱을 다시 깔아도 보인다 — 중앙 DB 에서는 **남의 PC 가 죽은 것을 소유자가 본다.**
 *
 * 띄우는 것은 **중단만**이다. 오류와 취소는 그 자리에서 화면이 이미 말했다.
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useDataRefresh } from '@/app/lifecycle/dataLifecycle.js'

const runs = ref([])
const busy = ref(false)

/** 가장 최근 중단 하나만 말한다. 여러 건이 쌓여도 사람이 할 일은 하나다. */
const latest = computed(() => runs.value[runs.value.length - 1] || null)
const more = computed(() => Math.max(0, runs.value.length - 1))

async function load() {
  try {
    const r = await fetch('/api/ingest/runs')
    if (!r.ok) { runs.value = []; return }
    runs.value = (await r.json()).interrupted || []
  } catch {
    // 못 물어본 것은 "중단이 없다" 가 아니다 — 다만 띄울 근거도 없다.
    runs.value = []
  }
}

async function ack() {
  const run = latest.value
  if (!run || busy.value) return
  busy.value = true
  try {
    await fetch(`/api/ingest/runs/${encodeURIComponent(run.runId)}/ack`, { method: 'POST' })
  } finally {
    busy.value = false
    await load()
  }
}

/** 적재가 완료되거나 초기화되면 다시 묻는다 — 내 적재가 앞의 경고를 덮을 수 있다. */
useDataRefresh(load)

// 돌아왔을 때 다시 묻는다. 주기 폴링을 두지 않는 이유는 이 사실이 **드물고**,
// 사람이 창을 볼 때만 뜻이 있기 때문이다.
function onVisible() {
  if (document.visibilityState === 'visible') load()
}
onMounted(() => {
  load()
  document.addEventListener('visibilitychange', onVisible)
})
onUnmounted(() => document.removeEventListener('visibilitychange', onVisible))

function when(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

/** 무엇이 없어졌는지. 많으면 큰 것 셋만 보이고 나머지는 수로 접는다. */
const wiped = computed(() => {
  const counts = (latest.value && latest.value.wiped) || {}
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1])
  const head = rows.slice(0, 3).map(([k, v]) => `${k} ${v}`).join(' · ')
  const rest = rows.length - 3
  return rest > 0 ? `${head} 외 ${rest}종` : head
})

const hasSnapshot = computed(
  () => !!(latest.value && (latest.value.snapshots || []).length),
)
const who = computed(() => {
  const r = latest.value
  if (!r) return ''
  const name = r.displayName || r.uid || ''
  return r.host ? `${name} (${r.host})` : name
})
</script>

<template>
  <div v-if="latest" class="iwarn">
    <span class="iwarn__tag">적재가 중단됐습니다</span>
    <span class="iwarn__who">
      {{ who }} · {{ when(latest.startedAt) }} 시작 — 끝나지 않았습니다
    </span>
    <span v-if="latest.wipedTotal" class="iwarn__lost">
      적재를 시작할 때 이전 설계를 지웠습니다: {{ wiped }}
    </span>
    <span v-else class="iwarn__lost">지워진 설계는 없습니다(첫 적재).</span>
    <span v-if="latest.wipedTotal" class="iwarn__keep" :class="{ 'iwarn__keep--none': !hasSnapshot }">
      {{ hasSnapshot
        ? '지난 판은 보관돼 있습니다 — 내보내기 화면의 ‘지난 판’'
        : '보관된 판이 없습니다 — 되찾을 수 없습니다' }}
    </span>
    <span class="iwarn__how">문서를 다시 적재해 주세요.</span>
    <span v-if="more" class="iwarn__more">그 밖에 {{ more }}건 더</span>
    <button class="iwarn__ack" :disabled="busy" @click="ack">확인했습니다</button>
  </div>
</template>

<style scoped>
.iwarn {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: #fdecea;
  border-bottom: 1px solid #f5c6c2;
  color: #7f231c;
  font-size: 12px;
}
.iwarn__tag { font-weight: 700; }
.iwarn__who { font-weight: 600; }
.iwarn__lost, .iwarn__keep, .iwarn__how, .iwarn__more { opacity: 0.85; }
/* 되찾을 길이 없다는 말은 흐리게 두지 않는다. */
.iwarn__keep--none { opacity: 1; font-weight: 600; }
.iwarn__ack {
  margin-left: auto;
  padding: 2px 10px;
  border: 1px solid #d99;
  border-radius: 4px;
  background: #fff;
  color: #7f231c;
  font-size: 12px;
  cursor: pointer;
}
.iwarn__ack:disabled { opacity: 0.6; cursor: default; }
</style>
