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

/** localStorage 는 환경에 따라 접근 자체가 던진다. 실패해도 앱이 죽지 않게 한다. */
function readStored(key) {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStored(key, value) {
  try {
    if (value === null || value === undefined) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
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
  /** 강제가 꺼져 있으면 로그인 없이도 쓰던 대로 쓴다. */
  const enforced = computed(() => !!(provider.value || {}).enforce)

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

  /** 인터셉터 전용. 같은 코드를 다시 적어 화면이 깜빡이지 않게 한다. */
  function setProjectError(code) {
    const next = code || null
    if (projectError.value !== next) projectError.value = next
  }

  async function loadProvider() {
    try {
      const r = await fetch('/api/auth/provider')
      provider.value = r.ok ? await r.json() : null
    } catch {
      provider.value = null
    }
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
    token, projectGraph, user, status, provider, checking, projectError,
    authenticated, pending, rejected, isAdmin, enforced,
    setToken, setProject, setProjectError,
    loadProvider, refresh, devLogin, ssoLogin, logout,
  }
})
