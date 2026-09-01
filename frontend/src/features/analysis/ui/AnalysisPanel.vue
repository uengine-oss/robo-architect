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
import { ref, inject, watch, onMounted, onBeforeUnmount, onActivated } from 'vue'

const ROOT_KEY = 'claude_code_workspace_root'

const hostEl = ref(null)
const loadError = ref('')
const isLoading = ref(true)
let unmountRemote = null
// 지금 마운트된 remote 가 받은 루트. 재마운트 여부는 이 값과의 비교로만 정한다.
let mountedRoot

// App 이 provide 하는 메인 세션 workdir. Code 탭에서 폴더를 바꾸면
// syncMainRoot 가 이 ref 와 localStorage 를 함께 갱신한다. ref 를 감시하면
// 탭을 오가지 않아도 즉시 알 수 있어서, 이쪽이 1차 출처다.
const appWorkdir = inject('claudeCodeWorkdir', null)

// localStorage 는 폴백이자 두 번째 출처다. 런처(Electron)와 PRD 생성 모달은
// 이 키만 쓰고 ref 는 건드리지 않는다.
function readRoot() {
  const fromRef = appWorkdir?.value
  if (fromRef) return fromRef
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
    currentRoot.value = projectRoot
  } catch (err) {
    loadError.value = err?.message || String(err)
  } finally {
    isLoading.value = false
  }
}

// ── 분석 폴더 직접 고르기 ─────────────────────────────────────────────────
// remote 는 이 경로를 표시만 하고 바꾸지 못한다. 유일한 입구가 Code 탭의
// 터미널 폴더 버튼인데, 그건 활성 터미널 세션을 옮기는 것이고 프로젝트
// 루트로 승격되는 것은 main 세션일 때뿐이라, "바꿨는데 분석 대상은 그대로"
// 가 조용히 일어난다. 분석 대상을 정하는 자리는 분석 화면이어야 한다.
const showPicker = ref(false)
const pickerData = ref({ current_path: '', parent_path: null, directories: [] })
const isBrowsing = ref(false)
const currentRoot = ref(undefined)

async function browseDirectory(path) {
  // 상대 경로면 양쪽에서 다 닿는다 — 브라우저는 Vite 프록시가, Electron 은
  // app:// 프로토콜 핸들러가 /api/** 를 백엔드로 넘긴다. 포트를 알 필요가 없다.
  isBrowsing.value = true
  try {
    const r = await fetch(`/api/claude-code/browse-directory?path=${encodeURIComponent(path || '~')}`)
    if (r.ok) pickerData.value = await r.json()
  } catch { /* 목록만 못 받은 것 — 열린 채로 둔다 */ }
  finally { isBrowsing.value = false }
}

function openPicker() {
  showPicker.value = true
  browseDirectory(currentRoot.value || '~')
}

async function applyRoot(path) {
  showPicker.value = false
  if (!path || path === mountedRoot) return
  // 두 출처를 함께 갱신한다 — Code 탭·런처와 같은 키를 쓰므로 화면 간에 어긋나지 않는다.
  try { localStorage.setItem(ROOT_KEY, path) } catch { /* 저장 실패해도 이번 마운트는 진행 */ }
  if (appWorkdir) appWorkdir.value = path
  currentRoot.value = path
  teardown()
  await mountRemote()
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
  if (!unmountRemote) return
  if (readRoot() === mountedRoot) return
  teardown()
  await mountRemote()
}

// 1차 — Code 탭에서 폴더를 바꾸는 순간. 탭을 오가지 않아도 반영된다.
if (appWorkdir) watch(appWorkdir, remountIfRootChanged)

// 2차 — ref 를 거치지 않고 localStorage 만 바뀌는 경로(런처·PRD 모달)를 위해
// 탭이 다시 보일 때 한 번 더 대조한다. 같으면 아무것도 하지 않는다.
onActivated(remountIfRootChanged)

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

    <!-- 분석 대상 폴더. remote 안의 경로는 표시 전용이라 여기서 바꾼다. -->
    <div v-if="!loadError" class="analysis-root-bar">
      <span class="root-label">분석 폴더</span>
      <span class="root-path" :title="currentRoot || ''">{{ currentRoot || '선택 안 됨 (업로드 모드)' }}</span>
      <button class="root-change" @click="openPicker">변경</button>
    </div>

    <!-- analyzer 앱이 이 컨테이너 안에 격리 마운트된다 -->
    <div ref="hostEl" class="analysis-host"></div>

    <div v-if="showPicker" class="root-picker-overlay" @keydown.esc.window="showPicker = false">
      <div class="root-picker">
        <div class="root-picker__head">
          <span>분석할 폴더 선택</span>
          <button class="root-picker__close" @click="showPicker = false">✕</button>
        </div>
        <div class="root-picker__path">{{ pickerData.current_path || '…' }}</div>
        <div class="root-picker__list">
          <div v-if="isBrowsing" class="root-picker__empty">읽는 중…</div>
          <template v-else>
            <button
              v-if="pickerData.parent_path"
              class="root-picker__item"
              @click="browseDirectory(pickerData.parent_path)"
            >../</button>
            <button
              v-for="d in pickerData.directories"
              :key="d"
              class="root-picker__item"
              @click="browseDirectory(pickerData.current_path + '/' + d)"
            >{{ d }}/</button>
            <div v-if="!pickerData.directories.length" class="root-picker__empty">하위 폴더 없음</div>
          </template>
        </div>
        <div class="root-picker__foot">
          <button class="root-picker__cancel" @click="showPicker = false">취소</button>
          <button class="root-picker__ok" @click="applyRoot(pickerData.current_path)">이 폴더로</button>
        </div>
      </div>
    </div>
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


.analysis-root-bar {
  position: absolute; top: 0; left: 0; right: 0; z-index: 5;
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; font-size: 12px;
  background: var(--surface-2, #f6f7f9);
  border-bottom: 1px solid var(--border, #e3e5e8);
}
.root-label { color: var(--text-muted, #6b7280); flex: none; }
.root-path {
  flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text, #111827);
}
.root-change {
  flex: none; padding: 3px 10px; font-size: 12px; cursor: pointer;
  border: 1px solid var(--border, #d1d5db); border-radius: 4px;
  background: var(--surface, #fff); color: inherit;
}
.root-change:hover { background: var(--surface-3, #eef0f3); }

/* 경로 바가 차지한 만큼 remote 를 밀어 내린다 — 겹치면 analyzer 상단이 가려진다. */
.analysis-root-bar ~ .analysis-host { height: calc(100% - 33px); margin-top: 33px; }

.root-picker-overlay {
  position: absolute; inset: 0; z-index: 20;
  display: flex; align-items: center; justify-content: center;
  background: rgba(0, 0, 0, 0.35);
}
.root-picker {
  width: min(560px, 90%); max-height: 70%;
  display: flex; flex-direction: column;
  background: var(--surface, #fff); border-radius: 8px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
}
.root-picker__head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; border-bottom: 1px solid var(--border, #e3e5e8); font-weight: 600;
}
.root-picker__close { border: 0; background: none; cursor: pointer; font-size: 14px; color: inherit; }
.root-picker__path {
  padding: 8px 14px; font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  color: var(--text-muted, #6b7280);
  border-bottom: 1px solid var(--border, #e3e5e8);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.root-picker__list { flex: 1; overflow: auto; padding: 6px 0; }
.root-picker__item {
  display: block; width: 100%; text-align: left;
  padding: 6px 14px; border: 0; background: none; cursor: pointer;
  font-size: 13px; color: inherit;
}
.root-picker__item:hover { background: var(--surface-3, #eef0f3); }
.root-picker__empty { padding: 10px 14px; font-size: 12px; color: var(--text-muted, #6b7280); }
.root-picker__foot {
  display: flex; justify-content: flex-end; gap: 8px;
  padding: 10px 14px; border-top: 1px solid var(--border, #e3e5e8);
}
.root-picker__cancel, .root-picker__ok {
  padding: 5px 14px; font-size: 13px; cursor: pointer;
  border: 1px solid var(--border, #d1d5db); border-radius: 4px;
  background: var(--surface, #fff); color: inherit;
}
.root-picker__ok { background: var(--primary, #2563eb); border-color: var(--primary, #2563eb); color: #fff; }
</style>
