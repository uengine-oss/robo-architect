<script setup>
/**
 * AnalysisPanel.vue — "Analysis" 탭
 *
 * robo-analyzer-frontend 를 Module Federation 으로 불러와 이 패널 안에서
 * "격리 실행"한다. analyzer 는 자기 Pinia·Router 를 가진 독립 앱으로
 * hostEl 안에서만 동작하므로 robo-architect 와 충돌하지 않는다.
 *   - remote 가 노출한 mount(el) 를 호출 → 마운트
 *   - 반환된 unmount 를 보관 → 패널 파기 시 해제
 * remote 는 build 후 serve 되어야 한다(5001 포트). 미기동 시 에러 안내.
 *
 * 마운트 인자는 마운트 시점에 한 번 읽힌다. 탭 컨테이너가 <KeepAlive> 라
 * 이 패널은 한 번 열리면 파기되지 않으므로, 그대로 두면 onMounted 가 다시
 * 돌지 않는다 — Code 탭에서 프로젝트 루트를 바꿔도 Analyzer 는 예전 경로를
 * 계속 들고 있고, 화면의 경로는 표시 전용이라 고칠 수단도 없다. 앱을
 * 새로고침해야만 반영되는데 그걸 알 방법이 없다. 그래서 활성화될 때마다
 * 루트를 다시 읽고, 달라졌을 때만 remote 를 다시 마운트한다.
 */
import { ref, computed, inject, watch, onMounted, onBeforeUnmount, onActivated } from 'vue'
import { useProjectsStore } from '@/features/projects/projects.store.js'
import { useAuthStore } from '@/features/auth/auth.store.js'
import { useSessionStore } from '@/features/desktop-launcher/stores/session-store.js'

const ROOT_KEY = 'claude_code_workspace_root'

const hostEl = ref(null)
const loadError = ref('')
const isLoading = ref(true)
let unmountRemote = null
// 지금 마운트된 remote 가 받은 루트. 재마운트 여부는 이 값과의 비교로만 정한다.
let mountedRoot
// 같은 이유로 분석 graph 도 기억한다. 프로젝트를 바꾸면 앱이 통째로 새로고침되지만,
// 짝만 고치는 길(선택기의 `분석 짝`)은 새로고침 없이 값이 바뀐다.
let mountedDatabase

const projectsStore = useProjectsStore()
const auth = useAuthStore()
const session = useSessionStore()

/**
 * 프로젝트가 정해지지 않았으면 분석기를 띄우지 않는다.
 *
 * **설계와 달리 분석은 우리 백엔드를 지나지 않는다.** 별도 서비스라 403 이
 * 걸리지 않고, 대상 graph 를 안 넘기면 자기 `.env` 의 공용 graph 로 간다.
 * 그리고 분석은 시작할 때 **대상 graph 를 통째로 비운다** — 프로젝트 없이 한 번
 * 돌리면 공용 graph 에 쌓이고, 그 graph 를 짝으로 쓰는 프로젝트가 있으면 그
 * 결과가 사라진다. 오류는 안 난다.
 *
 * 연결 바인딩이 꺼진 구성(Electron 런처)은 프로젝트 개념 자체가 없으므로
 * 지금까지처럼 그냥 띄운다.
 */
const bound = computed(() => !!(auth.provider || {}).bindConnection)
const blocked = ref(false)
/** 프로젝트는 골랐는데 분석 짝이 없는 경우. 할 일이 다르므로 갈라서 안내한다. */
const noPair = computed(() => blocked.value && !!auth.projectGraph)

/** 이 프로젝트의 분석 graph. 목록이 아직 없으면 한 번 읽어 온다. */
async function loadAnalyzerGraph() {
  if (!projectsStore.projects.length) {
    try { await projectsStore.load() } catch { /* 목록이 없어도 분석기는 떠야 한다 */ }
  }
  return projectsStore.currentAnalyzerGraph || undefined
}

function readAnalyzerGraph() {
  return projectsStore.currentAnalyzerGraph || undefined
}

// App 이 provide 하는 메인 세션 workdir. Code 탭에서 폴더를 바꾸면
// syncMainRoot 가 이 ref 와 localStorage 를 함께 갱신한다. ref 를 감시하면
// 탭을 오가지 않아도 즉시 알 수 있어서, 이쪽이 1차 출처다.
const appWorkdir = inject('claudeCodeWorkdir', null)

// localStorage 는 폴백이자 두 번째 출처다. 런처(Electron)와 PRD 생성 모달은
// 이 키만 쓰고 ref 는 건드리지 않는다.
function readRoot() {
  // **브라우저에서는 경로 모드를 쓰지 않는다.**
  //
  // `projectRoot` 를 넘기면 분석기가 "로컬 폴더 분석"으로 열리고, 없으면
  // "파일을 올려 분석"으로 열린다. 그런데 그 값의 출처가 이 브라우저의
  // localStorage 라, 같은 서버에 붙어도 **창마다 화면이 다르다** — 한쪽은
  // 폴더를 고르라 하고 다른 쪽은 드래그하라 한다. 실제로 그렇게 갈렸다.
  //
  // 게다가 사내망 서버에 올린 Architect 에서 "로컬 폴더"는 사용자 PC 가
  // 아니라 **서버의 폴더**다. 경로 모드가 말이 되는 것은 런처(Electron)가
  // 그 PC 에서 직접 고른 경우뿐이다.
  if (!session.isDesktop) return undefined
  const fromRef = appWorkdir?.value
  if (fromRef) return fromRef
  try { return localStorage.getItem(ROOT_KEY) || undefined } catch { return undefined }
}

async function mountRemote() {
  isLoading.value = true
  loadError.value = ''
  try {
    // 이 프로젝트의 분석 graph. 분석은 **대상 graph 를 통째로 비우고** 시작하므로,
    // 이 값이 없으면 분석기가 자기 env 에 고정된 graph 하나를 비운다 — 다른
    // 프로젝트에서 분석을 한 번 돌리면 여기 결과가 사라진다. 오류는 안 난다.
    //
    // **내려받기 전에 막는다.** 받아 놓고 마운트만 안 하면, 다음에 이 코드를
    // 고치는 사람이 "이미 있으니 띄우자"로 되돌리기 쉽다.
    const neo4jDatabase = await loadAnalyzerGraph()
    if (bound.value && !neo4jDatabase) {
      blocked.value = true
      return
    }
    blocked.value = false

    // remote-app 의 공개 API 는 federation 규약상 default 로 노출된다.
    const remote = await import(/* @vite-ignore */ 'robo-analyzer-frontend/remote-app')

    // projectRoot: Electron 데스크톱이 고른 로컬 폴더(Code 탭과 동일 키) → analyzer 가 업로드 없이
    //              그 경로를 직접 분석(경로 모드). 없으면(브라우저) analyzer 는 업로드 모드로 동작.
    const projectRoot = readRoot()

    // neo4j: 런처에서 고른 활성 Neo4j 연결(키체인 비번 포함)을 mount 직전 1회 조회 →
    //        analyzer 가 X-Neo4j-* 헤더로 백엔드(analyzer/catalog)에 override. 데스크톱 외(브라우저)
    //        에선 bridge 부재 → undefined → 백엔드 env(ROBO_NEO4J_*) 폴백. 비번은 헤더로만 흘리고 저장 X.
    let neo4j
    try {
      const r = await window.desktop?.connections?.resolveActiveForBackend?.()
      if (r?.ok && r.data) neo4j = r.data
    } catch { neo4j = undefined }

    // embedded: architect 탭 안에 끼워지므로 analyzer 자체 상단바를 숨긴다.
    // onProjectRootChange: analyzer 화면에서 폴더를 바꾸면 host 가 저장한다.
    // 저장하지 않으면 다음 마운트에 예전 값으로 조용히 돌아간다. Code 탭·런처와
    // 같은 키를 쓰므로 화면 간에 어긋나지도 않는다.
    unmountRemote = remote.default.mount(hostEl.value, {
      embedded: true,
      projectRoot,
      neo4j,
      neo4jDatabase,
      onProjectRootChange: persistRoot,
    })
    mountedRoot = projectRoot
    mountedDatabase = neo4jDatabase
  } catch (err) {
    loadError.value = err?.message || String(err)
  } finally {
    isLoading.value = false
  }
}

// analyzer 가 고른 폴더를 host 의 두 출처에 함께 쓴다. mountedRoot 도 같이
// 올려 둔다 — 안 그러면 watch/onActivated 가 "바뀌었다"고 보고 방금 마운트한
// remote 를 곧바로 다시 마운트한다.
function persistRoot(path) {
  if (!path) return
  try { localStorage.setItem(ROOT_KEY, path) } catch { /* 저장 실패해도 이번 세션은 진행 */ }
  if (appWorkdir) appWorkdir.value = path
  mountedRoot = path
}

function teardown() {
  try { unmountRemote?.() } catch { /* 이미 해제됨 */ }
  unmountRemote = null
  // remote 가 자기 DOM 을 남기고 가더라도 다음 마운트가 그 위에 겹치지 않게.
  // 이 컨테이너는 remote 전용이라 비워도 host 쪽이 잃는 것이 없다.
  if (hostEl.value) hostEl.value.innerHTML = ''
}

onMounted(mountRemote)

async function remountIfRootChanged() {
  // 아직 마운트 전이거나 마운트 중이면 할 일이 없다 — mountRemote 가 최신 값을 읽는다.
  // 막혀 있던 경우에도 다시 본다 — 프로젝트를 고르면 그때 띄워야 한다.
  if (!unmountRemote && !blocked.value) return
  if (!blocked.value
      && readRoot() === mountedRoot && readAnalyzerGraph() === mountedDatabase) return
  teardown()
  await mountRemote()
}

// 1차 — Code 탭에서 폴더를 바꾸는 순간. 탭을 오가지 않아도 반영된다.
if (appWorkdir) watch(appWorkdir, remountIfRootChanged)

// 2차 — ref 를 거치지 않고 localStorage 만 바뀌는 경로(런처·PRD 모달)를 위해
// 탭이 다시 보일 때 한 번 더 대조한다. 같으면 아무것도 하지 않는다.
onActivated(remountIfRootChanged)

// 3차 — 선택기에서 분석 짝을 고치면 새로고침 없이 값만 바뀐다. 그대로 두면
// 분석기가 옛 graph 를 계속 쓰고, 거기서 분석을 돌리면 그 graph 가 비워진다.
watch(() => projectsStore.currentAnalyzerGraph, remountIfRootChanged)

onBeforeUnmount(teardown)
</script>

<template>
  <div class="analysis-panel">
    <div v-if="loadError" class="analysis-error">
      <div class="error-icon">⚠</div>
      <div class="error-text">
        <p>Analyzer 화면을 불러올 수 없습니다.</p>
        <p class="detail">{{ loadError }}</p>
        <p class="hint">robo-analyzer-frontend(5001 포트)가 build 후 serve 중인지 확인하세요.</p>
      </div>
    </div>

    <div v-if="blocked && !loadError" class="analysis-error">
      <div class="error-icon">○</div>
      <div class="error-text">
        <p v-if="noPair">이 프로젝트에는 분석을 담을 곳이 지정되어 있지 않습니다.</p>
        <p v-else>먼저 프로젝트를 선택해 주세요.</p>
        <p class="hint" v-if="noPair">위쪽 프로젝트 메뉴의 <b>분석 결과 바꾸기</b>에서
          이 프로젝트의 분석을 고르면 시작할 수 있습니다.</p>
        <p class="hint" v-else>분석 결과는 프로젝트마다 따로 보관됩니다.
          프로젝트를 정하지 않으면 결과를 어디에 담을지 알 수 없습니다.</p>
      </div>
    </div>

    <div v-show="isLoading && !loadError && !blocked" class="analysis-loading">
      <div class="spinner"></div>
      <span>Analyzer 로드 중…</span>
    </div>

    <!-- analyzer 앱이 이 컨테이너 안에 격리 마운트된다 -->
    <div ref="hostEl" class="analysis-host"></div>

  </div>
</template>

<style scoped>
.analysis-panel {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.analysis-host {
  width: 100%;
  height: 100%;
}

.analysis-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: #888;
}

.analysis-loading .spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #333;
  border-top-color: #0d6efd;
  border-radius: 50%;
  animation: analysis-spin 0.8s linear infinite;
}

@keyframes analysis-spin {
  to { transform: rotate(360deg); }
}

.analysis-error {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 40px;
  color: #888;
}

.analysis-error .error-icon {
  font-size: 48px;
  color: #f59e0b;
}

.analysis-error .detail {
  font-size: 12px;
  color: #f88;
  font-family: monospace;
}

.analysis-error .hint {
  font-size: 12px;
  color: #666;
  margin-top: 8px;
}


</style>
