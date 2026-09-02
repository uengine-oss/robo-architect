/** 템플릿 기반 코드 생성 — 백엔드 읽기 API. */

const BASE = '/api/code-templates'

async function getJson(url) {
  const res = await fetch(url)
  if (!res.ok) {
    let detail = `HTTP ${res.status}`
    try {
      const body = await res.json()
      if (body && body.detail) detail = body.detail
    } catch { /* 본문이 JSON 이 아니면 상태 코드로 둔다 */ }
    throw new Error(detail)
  }
  return res.json()
}

export const listSets = () => getJson(`${BASE}/sets`)

export const listFiles = (setName) =>
  getJson(`${BASE}/sets/${encodeURIComponent(setName)}/files`)

export const getContext = (sessionId, serviceId) =>
  getJson(`${BASE}/context?sessionId=${encodeURIComponent(sessionId)}&serviceId=${encodeURIComponent(serviceId)}`)

/** 산출물 세션 목록 — serviceId 기본값을 세션 이름에서 제안하려고 쓴다. */
export const listSessions = () => getJson('/api/deliverables/sessions')
