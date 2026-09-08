/**
 * 검사가 백엔드를 직접 부를 때 쓰는 자격.
 *
 * 화면을 거치는 요청은 `globalSetup` 이 만든 로그인 상태를 쓴다. 그런데 spec 이
 * `request.get('http://localhost:8000/...')` 로 **직접** 부르면 그 상태가 안 실린다 —
 * 토큰이 localStorage 에 있고 이 호출은 브라우저를 거치지 않기 때문이다.
 *
 * 강제가 꺼져 있으면 빈 헤더를 돌려준다. 그때는 지금까지처럼 그냥 돌면 된다.
 */

const API = process.env.ROBO_API_URL || 'http://localhost:8000'

let cached: Record<string, string> | null = null

export async function apiHeaders(request: any, projectGraph = 'robo'): Promise<Record<string, string>> {
  if (cached) return cached
  try {
    const pr = await request.get(`${API}/api/auth/provider`)
    const provider = pr.ok() ? await pr.json() : {}
    if (!provider.enforce) return (cached = {})
    if (!provider.devLogin?.enabled) {
      console.warn('[api-auth] 강제는 켜졌는데 개발용 로그인이 없다')
      return (cached = {})
    }
    const lr = await request.post(`${API}/api/auth/dev-login`, {
      multipart: {
        loginId: provider.devLogin.loginId || 'test',
        password: process.env.AUTH_DEV_LOGIN_PASSWORD || 'test',
      },
    })
    const body = await lr.json().catch(() => ({}))
    if (!body.accessToken) {
      console.warn(`[api-auth] 로그인하지 못했다 (${body.status || lr.status()})`)
      return (cached = {})
    }
    return (cached = {
      Authorization: `Bearer ${body.accessToken}`,
      'X-Project-Graph': projectGraph,
    })
  } catch (e: any) {
    console.warn('[api-auth] 자격을 만들지 못했다:', e?.message)
    return (cached = {})
  }
}
