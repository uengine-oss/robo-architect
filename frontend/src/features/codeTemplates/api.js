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

// ── 템플릿 원본 보기와 수정 (TPL-1) ────────────────────────────────────────
//
// 템플릿은 산출물의 **파일이 원본**이고, 고친 것은 중앙 DB 에 쌓인다. 그래서
// 한 줄을 고치려고 전체를 다시 굽고 20여 대에 재설치할 일이 없다.
// 고치는 것은 관리자만이다 — 본문의 `<function>` 블록은 렌더러가 실제로 실행한다.

const fileUrl = (setName, path) =>
  `${BASE}/sets/${encodeURIComponent(setName)}/file?path=${encodeURIComponent(path)}`

/** 한 장의 원문. `version` 을 주면 그 이력 판을 `current` 자리에 담아 준다. */
export const getTemplateFile = (setName, path, version) =>
  getJson(fileUrl(setName, path) + (version ? `&version=${encodeURIComponent(version)}` : ''))

async function send(url, init) {
  const res = await fetch(url, init)
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

export const saveTemplateFile = (setName, path, body) =>
  send(`${BASE}/sets/${encodeURIComponent(setName)}/file`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, body }),
  })

/** 수정본을 버리고 산출물 원본으로 되돌린다. */
export const revertTemplateFile = (setName, path) =>
  send(fileUrl(setName, path), { method: 'DELETE' })
