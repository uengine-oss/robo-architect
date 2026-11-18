// 프로젝트를 만들 때 고른 의도(그린필드/브라운필드)를 DDD 마법사 기본값으로 (라이트 지적 C-5 ⑩).
//
// 의도는 데스크톱 lite 의 홈 "프로젝트 만들기" 모달이 묻고, main 이 설정의
// `projectTypes[그래프]` 에 둔다(desktop/src/main/launcher/projects.ts). 여기서는
// `window.desktop.projects.list()` 가 실어 주는 `projectType` 을 읽기만 한다.
//
//   - 웹 판: `window.desktop` 이 없다 → `null`(마법사는 지금 기본값 그대로)
//   - enterprise: `projects:list` 를 거절한다 → `null`
//   - 의도를 안 고른 옛 프로젝트 → `null`
// **두 번 묻지 않는다** 가 목적이지 고정이 아니다 — 마법사에서 사용자가 바꿀 수 있다.

export const PROJECT_TYPES = ['greenfield', 'brownfield']

/** 목록에서 그 그래프의 의도. 모르면 `null`. */
export function projectTypeFor(projects, graph) {
  if (!graph || !Array.isArray(projects)) return null
  const hit = projects.find((p) => p && p.name === graph)
  return hit && PROJECT_TYPES.includes(hit.projectType) ? hit.projectType : null
}

/** 지금 프로젝트의 의도를 데스크톱에서 읽는다. 어떤 실패도 `null`(= 지금 동작). */
export async function loadProjectTypeDefault(graph, win = typeof window !== 'undefined' ? window : undefined) {
  const list = win?.desktop?.projects?.list
  if (!graph || typeof list !== 'function') return null
  try {
    const r = await list()
    return r && r.ok ? projectTypeFor(r.data, graph) : null
  } catch {
    return null
  }
}
