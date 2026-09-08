import { request } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'fs'
import { dirname } from 'path'

/**
 * 검사용 로그인 상태를 미리 만든다.
 *
 * `AUTH_ENFORCE` 를 켜는 순간 기존 검사가 전부 로그인 화면에 막힌다. 검사마다
 * 로그인을 넣으면 새로 만드는 검사가 그걸 잊고, 그때는 "왜 화면이 안 뜨지"로
 * 보인다 — 원인이 인증이라는 것이 드러나지 않는다.
 *
 * 강제가 꺼져 있거나 개발용 로그인이 없으면 **빈 상태**를 만든다. 그 경우 지금까지
 * 처럼 그냥 돌면 되고, 여기서 실패시키면 인증과 무관한 검사까지 못 돌게 된다.
 *
 * 로그인 화면 자체를 보는 검사는 이 상태를 쓰면 안 된다 — 그 spec 이
 * `test.use({ storageState: { cookies: [], origins: [] } })` 로 비운다.
 */

export const STATE_PATH = 'tests/.auth/state.json'

const BASE = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5173'

export default async function globalSetup() {
  const empty = { cookies: [], origins: [] }
  const write = (state: any) => {
    mkdirSync(dirname(STATE_PATH), { recursive: true })
    writeFileSync(STATE_PATH, JSON.stringify(state, null, 2))
  }

  const ctx = await request.newContext({ baseURL: BASE })
  try {
    const pr = await ctx.get('/api/auth/provider')
    if (!pr.ok()) return write(empty)
    const provider = await pr.json()
    if (!provider.enforce) {
      console.log('[setup] 인증 강제가 꺼져 있다 — 빈 상태로 둔다')
      return write(empty)
    }
    if (!provider.devLogin?.enabled) {
      console.warn('[setup] 강제는 켜졌는데 개발용 로그인이 없다 — 검사가 막힐 것이다')
      return write(empty)
    }

    const lr = await ctx.post('/api/auth/dev-login', {
      multipart: {
        loginId: provider.devLogin.loginId || 'test',
        password: process.env.AUTH_DEV_LOGIN_PASSWORD || 'test',
      },
    })
    const body = await lr.json().catch(() => ({}))
    if (!body.accessToken) {
      console.warn(`[setup] 로그인하지 못했다 (${body.status || lr.status()})`)
      return write(empty)
    }

    // 프로젝트도 골라 둔다. 안 정하면 연결 바인딩이 켜졌을 때 403 이 난다.
    const projectsResp = await ctx.get('/api/projects', {
      headers: { Authorization: `Bearer ${body.accessToken}` },
    })
    const projects = projectsResp.ok() ? (await projectsResp.json()).projects || [] : []
    const design = projects.find((p: any) => p.graph === 'robo') || projects[0]

    const localStorage = [{ name: 'robo.auth.token', value: body.accessToken }]
    if (design) localStorage.push({ name: 'robo.auth.project', value: design.graph })
    console.log(`[setup] 로그인함 — 프로젝트 ${design ? design.graph : '(없음)'}`)
    write({ cookies: [], origins: [{ origin: BASE, localStorage }] })
  } catch (e: any) {
    console.warn('[setup] 로그인 준비 실패 — 빈 상태로 둔다:', e?.message)
    write(empty)
  } finally {
    await ctx.dispose()
  }
}
