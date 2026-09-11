/**
 * 실패한 API 응답을 오류로 바꾸는 한 곳.
 *
 * **왜 한 곳이어야 하나.** 스토어마다 실패를 직접 해석하면 판정이 조금씩 달라지고,
 * 그 차이가 화면에서 거짓말이 된다. 실제로 이렇게 나왔다 — 프로젝트가 하나도 없는
 * 사용자에게 백엔드는 403 을 정확히 돌려줬는데,
 *
 *   "Failed to fetch user stories (HTTP 403)"   ← 우리가 만든 문구
 *   e.message.includes('Failed to fetch')       ← 네트워크 판정 규칙
 *
 * 자기가 만든 문구를 자기 규칙이 네트워크 장애로 읽어서 **"서버 연결 실패"** 라고
 * 알렸다. 백엔드는 멀쩡했고, 사람은 서버를 들여다보게 된다.
 *
 * 그래서 판정을 문구가 아니라 **사실**로 한다: HTTP 응답이 왔으면 서버는 살아 있다.
 */

/** 프로젝트 때문에 막힌 응답의 코드. 백엔드 `BindingDenied.code` 와 같은 값이다. */
const PROJECT_CODES = new Set(['PROJECT_NOT_SELECTED', 'PROJECT_FORBIDDEN'])

/**
 * 실패 응답 → Error. `httpStatus` 를 달아 두므로 아래 `isNetworkError` 가
 * 문구를 추측하지 않아도 된다. 403 이면 `projectError` 에 코드를 싣는다.
 *
 * @param {Response} response 실패한 응답
 * @param {string} what 사람이 읽을 대상 이름 ("user stories")
 * @returns {Promise<Error>}
 */
export async function apiFailure(response, what) {
  if (response.status === 403) {
    const body = await response.json().catch(() => ({}))
    if (PROJECT_CODES.has(body.code) || body.detail) {
      const err = new Error(body.detail || '이 프로젝트를 볼 수 없습니다.')
      err.httpStatus = 403
      err.projectError = body.code || 'PROJECT_FORBIDDEN'
      return err
    }
  }
  const err = new Error(`Failed to fetch ${what} (HTTP ${response.status})`)
  err.httpStatus = response.status
  return err
}

/**
 * 정말 서버에 못 닿은 것인가.
 *
 * **HTTP 상태가 있으면 네트워크 장애가 아니다.** 응답이 왔다는 뜻이기 때문이다.
 * 그 경우는 문구를 아무리 뒤져도 네트워크로 읽으면 안 된다.
 */
export function isNetworkError(e) {
  if (e && e.httpStatus) return false
  const msg = (e && e.message) || ''
  return (
    msg.includes('ECONNREFUSED') ||
    msg.includes('ECONNRESET') ||
    msg.includes('Failed to fetch') ||
    (e && e.name) === 'TypeError'
  )
}
