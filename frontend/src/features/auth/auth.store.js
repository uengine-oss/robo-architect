/**
 * 세션 상태.
 *
 * 토큰은 `localStorage` 에 둔다. Electron 과 브라우저가 같은 코드를 쓰고, 새로고침
 * 뒤에도 다시 로그인하지 않게 하려는 것이다. 토큰에는 사번·역할·승인 여부만
 * 들어 있고 비밀은 없다.
 *
 * **부팅 때 서버에 한 번 물어본다.** 토큰이 살아 있어도 그 사이에 승인이 취소됐을
 * 수 있어서, 저장된 토큰만 믿고 화면을 열지 않는다.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const TOKEN_KEY = 'robo.auth.token'
const PROJECT_KEY = 'robo.auth.project'

/**
 * 토큰은 **`sessionStorage`** 에 둔다. `localStorage` 가 아니다.
 *
 * 둘의 차이가 그대로 제품의 차이가 된다 —
 *
 *   localStorage     창을 닫았다 켜도 남는다 → 앱을 껐다 켜도 로그인 화면이
 *                    안 뜬다(토큰 TTL 8시간). 사내 배포본에서 자리를 비운 PC 가
 *                    다음 사람에게 그대로 열려 있다는 뜻이다.
 *   sessionStorage   문서 컨텍스트가 살아 있는 동안만 남는다. **새로고침은
 *                    견디고**(프로젝트 전환이 `location.reload()` 를 쓴다),
 *                    앱을 끄면 사라진다.
 *
 * 그래서 "앱을 켜면 로그인부터" 가 성립하면서도, 쓰는 도중의 새로고침에
 * 다시 로그인시키지 않는다.
 *
 * 저장소는 환경에 따라 접근 자체가 던진다(시크릿 창, 사이트 데이터 차단).
 * 실패해도 앱이 죽지 않게 감싼다 — 그 경우 이번 세션은 메모리로만 돈다.
 */
function store() {
  return window.sessionStorage
}

/**
 * 예전 빌드가 `localStorage` 에 남긴 토큰을 지운다.
 *
 * 옮기기만 하면 옛 토큰이 디스크에 **그대로 남는다.** 읽지는 않지만 남아 있는
 * 자격증명이고, PC 를 넘겨받은 사람이 파일에서 꺼낼 수 있다. 한 번만 돌면 된다.
 */
try {
  window.localStorage.removeItem(TOKEN_KEY)
  window.localStorage.removeItem(PROJECT_KEY)
} catch {
  /* 접근이 막힌 환경 — 지울 것도 없다 */
}

function readStored(key) {
  try {
    return store().getItem(key)
  } catch {
    return null
  }
}

function writeStored(key, value) {
  try {
    if (value === null || value === undefined) store().removeItem(key)
    else store().setItem(key, value)
  } catch {
    /* 저장하지 못해도 이번 세션은 메모리로 돈다 */
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(readStored(TOKEN_KEY))
  const projectGraph = ref(readStored(PROJECT_KEY))
  const user = ref(null)
  /** 'unknown' 은 아직 서버에 물어보기 전이다 — 로그인 화면을 성급히 띄우지 않는다. */
  const status = ref('unknown')
  const provider = ref(null)
  /**
   * `provider` 가 담긴 것을 **어떻게 알았는지**. `'unknown' | 'loaded' | 'unreachable'`.
   *
   * 이게 없을 때 `provider === null` 은 두 가지를 동시에 뜻했다 —
   * "아직 못 물어봤다" 와 "물어봤고, 강제가 꺼져 있다". 그래서 백엔드에 닿기
   * 전에는 `enforced` 가 false 로 접혀 **인증 강제가 없는 것처럼 열렸다.**
   * 실제로 그랬다: 창이 뜨고 백엔드가 응답하기까지 44초가 비었고(2026-09-29
   * 실측), 그 사이 로그인 화면 없이 런처가 그려졌다. 첫 설치에서는 백엔드
   * 기동이 2분을 넘을 수 있다(desktop/src/main/backend.ts 주석).
   */
  const providerStatus = ref('unknown')
  const checking = ref(false)
  /**
   * 프로젝트 때문에 막힌 상태. `PROJECT_NOT_SELECTED` 또는 `PROJECT_FORBIDDEN`.
   *
   * **호출부가 정하지 않는다.** 인터셉터가 응답을 보고 여기에 적는다 — 스토어마다
   * 403 을 따로 해석하게 두면 한 곳만 빠져도 그 화면은 "서버 연결 실패"라고
   * 말한다. 실제로 그렇게 나왔다: 프로젝트가 0개인 사용자에게 백엔드가
   * 멀쩡한데 죽었다고 알렸다.
   */
  const projectError = ref(null)

  const authenticated = computed(() => status.value === 'approved' && !!user.value)
  const pending = computed(() => status.value === 'pending')
  const rejected = computed(() => status.value === 'rejected')
  const isAdmin = computed(() => (user.value || {}).role === 'admin')
  /**
   * 인증 강제 여부. `'unknown' | 'on' | 'off'`.
   *
   * **모를 때가 'off' 가 아니다.** 이것을 boolean 하나로 둔 것이 아래 `gate` 가
   * 막으려는 fail-open 을 만들었다.
   */
  const enforcement = computed(() => {
    if (providerStatus.value !== 'loaded') return 'unknown'
    return (provider.value || {}).enforce ? 'on' : 'off'
  })
  /** 강제가 꺼져 있으면 로그인 없이도 쓰던 대로 쓴다. */
  const enforced = computed(() => enforcement.value === 'on')

  /**
   * 화면을 무엇으로 여는가. `'checking' | 'unreachable' | 'login' | 'open'`.
   *
   * 판정을 여기 한 곳에 모은 이유는 **이것만 시험하면 되게** 하려는 것이다.
   * 전에는 이 조건이 `App.vue` 의 computed 한 줄에 펼쳐져 있어서 단위 시험이
   * 닿지 못했고, 그래서 fail-open 이 아무 경고 없이 납품본까지 갔다.
   *
   * 원칙: **모를 때는 닫는다.**
   */
  const gate = computed(() => {
    if (enforcement.value === 'unknown') {
      return providerStatus.value === 'unreachable' ? 'unreachable' : 'checking'
    }
    if (enforcement.value === 'off') return 'open'
    if (checking.value || status.value === 'unknown') return 'checking'
    return authenticated.value ? 'open' : 'login'
  })

  function setToken(value) {
    token.value = value || null
    writeStored(TOKEN_KEY, token.value)
  }

  function setProject(graph) {
    projectGraph.value = graph || null
    writeStored(PROJECT_KEY, projectGraph.value)
    // 고쳤으니 막힘도 푼다. 남겨 두면 프로젝트를 만든 뒤에도 안내가 붙어 있다.
    projectError.value = null
  }

  /**
   * 인터셉터 전용. 같은 코드를 다시 적어 화면이 깜빡이지 않게 한다.
   *
   * **`PROJECT_NOT_SELECTED` 는 프로젝트가 정해진 뒤에는 버린다.** 그 403 은
   * 늦게 도착한 것이다 — 화면들의 `onMounted` 조회는 `/api/projects` 응답을
   * 기다리지 않고 먼저 나가고(`projects.store.js` 의 주석 참고), 그 응답이
   * 첫 프로젝트를 고른 **뒤에** 돌아온다. 그러면 `setProject` 가 지운 안내가
   * 다시 붙고, 아무도 다시 지우지 않는다.
   *
   * 2026-09-30 증상: 앱을 처음 띄우면 첫 프로젝트로 들어가 있는데 **"프로젝트를
   * 선택해 주세요" 가 그대로 남아 있었다.** 프로젝트가 정해진 화면에서 그 문구는
   * 참이 아니다.
   *
   * `PROJECT_FORBIDDEN` 은 다르다 — 고른 프로젝트를 못 볼 수 있으니 그대로 적는다.
   */
  function setProjectError(code) {
    let next = code || null
    if (next === 'PROJECT_NOT_SELECTED' && projectGraph.value) next = null
    if (projectError.value !== next) projectError.value = next
  }

  async function loadProvider({ attempts = 1, delayMs = 500 } = {}) {
    const maxAttempts = Math.max(1, Number(attempts) || 1)
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        const r = await fetch('/api/auth/provider')
        if (r.ok) {
          provider.value = await r.json()
          providerStatus.value = 'loaded'
          return provider.value
        }
      } catch {
        /* Electron may render before the packaged backend is listening. */
      }

      if (attempt < maxAttempts) {
        await new Promise(resolve => setTimeout(resolve, delayMs))
      }
    }

    // 이번엔 못 닿았다. **이미 알아낸 것은 지우지 않는다** — 로그인 화면이
    // `loadProvider()` 를 1회짜리로 한 번 더 부르기 때문이다. 거기서 잠깐
    // 끊긴 것을 "서버가 사라졌다" 로 읽으면, 로그인하던 사람이 오류 화면으로
    // 튕겨 나간다.
    if (providerStatus.value !== 'loaded') providerStatus.value = 'unreachable'
    return provider.value
  }

  /** 저장된 토큰이 아직 쓸 만한지 서버에 확인한다. */
  async function refresh() {
    checking.value = true
    try {
      if (!token.value) {
        user.value = null
        status.value = 'anonymous'
        return
      }
      const r = await fetch('/api/auth/me')
      if (!r.ok) throw new Error(String(r.status))
      const body = await r.json()
      user.value = body.authenticated ? body.user : null
      status.value = body.status || (body.authenticated ? 'approved' : 'anonymous')
      if (!body.authenticated && !body.status) setToken(null)
    } catch {
      // 서버에 닿지 못한 것과 토큰이 죽은 것을 구별할 수 없다. 토큰은 지우지
      // 않고 익명으로 둔다 — 지우면 잠깐 끊겼을 때 다시 로그인하게 된다.
      user.value = null
      status.value = 'anonymous'
    } finally {
      checking.value = false
    }
  }

  function apply(body) {
    status.value = body.status || 'anonymous'
    user.value = body.authenticated ? body.user : null
    if (body.accessToken) setToken(body.accessToken)
    return body
  }

  /** 사내망 밖 개발용. 서버에서 꺼져 있으면 404 가 온다. */
  async function devLogin(loginId, password) {
    const form = new FormData()
    form.append('loginId', loginId)
    form.append('password', password)
    const r = await fetch('/api/auth/dev-login', { method: 'POST', body: form })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) throw new Error(body.detail || `로그인 실패 (${r.status})`)
    return apply(body)
  }

  /** SWP 로그인 페이지로 보낸다. 돌아오면 콜백이 세션을 만든다. */
  async function ssoLogin() {
    const callback = `${window.location.origin}/api/auth/sso/valid`
    const r = await fetch(`/api/auth/sso/init?callbackUrl=${encodeURIComponent(callback)}`)
    if (!r.ok) throw new Error('SSO 를 시작할 수 없습니다.')
    const { redirectUrl } = await r.json()
    window.location.href = redirectUrl
  }

  function logout() {
    setToken(null)
    user.value = null
    status.value = 'anonymous'
  }

  return {
    token, projectGraph, user, status, provider, providerStatus, checking, projectError,
    authenticated, pending, rejected, isAdmin, enforced, enforcement, gate,
    setToken, setProject, setProjectError,
    loadProvider, refresh, devLogin, ssoLogin, logout,
  }
})
