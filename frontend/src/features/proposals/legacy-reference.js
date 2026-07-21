/** Single projection for legacyReferences v1/v2 + element-level legacyRefs (evlink).
 *
 * 요소↔레거시 연결의 단일 진실은 각 설계 요소가 소유한 `legacyRefs`(생성 시점에 기록,
 * 백엔드 legacy_element_refs 가 provenance 부분집합으로 검증)다. 과거의 문자열
 * substring 매칭(matchingLegacyReferences)은 누락·오탐을 만들어 제거했다.
 */

export function normalizeLegacyReferences(refs) {
  return (refs || []).map((stage) => ({
    ...stage,
    version: stage.version || 1,
    retrieves: (stage.retrieves || []).map((retrieve) => ({
      ...retrieve,
      searchedNodes: retrieve.searchedNodes || retrieve.nodes || [],
      inspections: retrieve.inspections || [],
    })),
  }))
}

export function legacyReferenceItems(refs) {
  const items = new Map()
  for (const stage of normalizeLegacyReferences(refs)) {
    for (const retrieve of stage.retrieves) {
      for (const node of retrieve.searchedNodes) {
        if (!node?.id) continue
        const current = items.get(node.id) || { id: node.id, searched: true, inspected: false }
        items.set(node.id, { ...current, ...node, searched: true })
      }
      for (const inspection of retrieve.inspections) {
        const id = inspection?.nodeId
        if (!id) continue
        const current = items.get(id) || { id, searched: false, inspected: false }
        items.set(id, {
          ...current,
          name: inspection.name || current.name || '',
          label: inspection.label || current.label || '',
          logicalName: inspection.logicalName || current.logicalName || '',
          summary: inspection.summary || current.summary || '',
          source: inspection.source || current.source,
          columns: inspection.columns || current.columns || [],
          inspected: inspection.ok === true,
          inspectionError: inspection.ok === false ? inspection.error : current.inspectionError,
        })
      }
    }
  }
  return [...items.values()]
}

export function legacyReferenceCount(refs) {
  return legacyReferenceItems(refs).length
}

/** provenance 를 nodeId → item Map 으로 (LegacyTag 표시 강화용 조회 인덱스). */
export function provenanceIndex(refs) {
  return new Map(legacyReferenceItems(refs).map((item) => [item.id, item]))
}

/** 표시용 소스 경로 — analyzer 가 주는 절대경로를 마지막 2단(폴더/파일)으로 줄인다. */
export function shortSourcePath(filePath) {
  const parts = String(filePath || '').split(/[\\/]+/).filter(Boolean)
  return parts.slice(-2).join('/')
}

/**
 * 요소의 레거시 근거 판정 — 결정론, 요소 데이터만 사용.
 *
 * - linked : legacyRefs 에 유효 항목 존재 → 근거 노드에 연결됨
 * - new    : legacyRefs === [] (검증기가 정규화한 정직한 "근거 없음")
 * - unknown: legacyRefs 키 자체가 없음 → 요소별 근거 기록 이전(구버전) 제안.
 *            "신규"로 오표기하지 않는다(T6).
 *
 * 깨진 항목(문자열이 아닌 nodeId, null 등)은 화면을 죽이지 않고 걸러낸다 —
 * 백엔드 관문 이전에 저장된 외부/구 데이터 방어.
 */
export function elementLegacyBasis(element) {
  const raw = element?.legacyRefs
  if (!Array.isArray(raw)) return { state: 'unknown', refs: [] }
  const refs = raw
    .map((ref) => (typeof ref === 'string' ? { nodeId: ref } : ref))
    .filter((ref) => ref && typeof ref.nodeId === 'string' && ref.nodeId.trim())
  if (!refs.length) return { state: 'new', refs: [] }
  const seen = new Set()
  return {
    state: 'linked',
    refs: refs.filter((ref) => !seen.has(ref.nodeId) && seen.add(ref.nodeId)),
  }
}
