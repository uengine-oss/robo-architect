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
import { ref, onMounted, onBeforeUnmount, onActivated } from 'vue'

const ROOT_KEY = 'claude_code_workspace_root'

const hostEl = ref(null)
const loadError = ref('')
const isLoading = ref(true)
let unmountRemote = null
// 지금 마운트된 remote 가 받은 루트. 재마운트 여부는 이 값과의 비교로만 정한다.
let mountedRoot

function readRoot() {
  try { return localStorage.getItem(ROOT_KEY) || undefined } catch { return undefined }
}

async function mountRemote() {
  isLoading.value = true
  loadError.value = ''
  try {
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
    unmountRemote = remote.default.mount(hostEl.value, { embedded: true, projectRoot, neo4j })
    mountedRoot = projectRoot
  } catch (err) {
    loadError.value = err?.message || String(err)
  } finally {
    isLoading.value = false
  }
}

function teardown() {
  try { unmountRemote?.() } catch { /* 이미 해제됨 */ }
  unmountRemote = null
  // remote 가 자기 DOM 을 남기고 가더라도 다음 마운트가 그 위에 겹치지 않게.
  // 이 컨테이너는 remote 전용이라 비워도 host 쪽이 잃는 것이 없다.
  if (hostEl.value) hostEl.value.innerHTML = ''
}

onMounted(mountRemote)

onActivated(async () => {
  // 첫 활성화는 onMounted 직후라 아직 마운트 중일 수 있다 — 그때는 할 일이 없다.
  if (!unmountRemote) return
  if (readRoot() === mountedRoot) return
  teardown()
  await mountRemote()
})

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

    <div v-show="isLoading && !loadError" class="analysis-loading">
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
