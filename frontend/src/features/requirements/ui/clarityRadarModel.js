/**
 * 명확화 레이더(ClarityRadar.vue)의 계산 — 화면 없이 잴 수 있게 떼어 둔다.
 *
 * lite ⑯: **"모름"을 "맑음"으로 그리지 않는다.**
 *   - 스캔하지 않은 축(scanned=false · score=null)은 면적 0 + 회색 점선으로 그린다.
 *     1.0 으로 그리면 한 번도 스캔하지 않은 프로젝트가 "완전히 명확"으로 보인다.
 *   - 대상 요구사항이 없으면(total==0) 퍼센트를 숨기고 "대상 요구사항 없음".
 *   - 축의 상태(coverage)와 "N건 모호"(flags)가 어긋나면 헤더에 경고 한 줄.
 *
 * 옛 백엔드(scanned 필드 없음)도 읽는다 — 그때는 status 가 있으면 스캔된 것으로 본다.
 */

/** 이 축에 실제 신호(스캔·플래그·답변)가 있었나. */
export function isScanned(row) {
  if (!row) return false
  if (typeof row.scanned === 'boolean') return row.scanned
  return row.status != null
}

/** 레이더에 그릴 반지름 비율(0..1). 미스캔은 0 — 1.0 으로 그리지 않는다. */
export function radialScore(row) {
  if (!isScanned(row)) return 0
  const s = Number(row.score)
  if (!Number.isFinite(s)) return 0
  return Math.min(1, Math.max(0, s))
}

/**
 * 머리의 상태.
 *   state: 'empty'(대상 없음) | 'unscanned'(스캔 안 함) | 'partial'(일부만) | 'scanned'
 *   pct:   퍼센트 정수, 보여 줄 수 없으면 null
 */
export function summarize(scores) {
  const rows = scores?.scores || []
  const total = scores?.totalUserStories ?? 0
  const scannedRows = rows.filter(isScanned)
  if (total === 0) return { state: 'empty', pct: null, scannedCount: 0, axisCount: rows.length }
  if (scannedRows.length === 0) {
    return { state: 'unscanned', pct: null, scannedCount: 0, axisCount: rows.length }
  }
  let overall = scores?.overallScore
  if (overall === undefined) {
    // 옛 응답: 미스캔 축은 0 으로 쳐서 평균(면적과 같은 뜻).
    overall = rows.length ? rows.reduce((a, r) => a + radialScore(r), 0) / rows.length : null
  }
  const pct = overall == null ? null : Math.round(overall * 100)
  return {
    state: scannedRows.length < rows.length ? 'partial' : 'scanned',
    pct,
    scannedCount: scannedRows.length,
    axisCount: rows.length,
  }
}

/**
 * flags(메모리의 "모호" 표시)와 coverage(축 상태)가 어긋나는가.
 *   - 축이 clear/resolved(=1.0)인데 그 축에 모호 표시가 남아 있다
 *   - 머리가 100% 인데 모호 요구사항이 있다
 * 돌려주는 것: 어긋난 축의 category 목록(머리 경고에 쓴다). 없으면 [].
 */
export function flagCoverageMismatch(scores) {
  const rows = scores?.scores || []
  const bad = rows
    .filter((r) => isScanned(r) && (r.status === 'clear' || r.status === 'resolved') && (r.flaggedCount ?? 0) > 0)
    .map((r) => r.category)
  const { pct } = summarize(scores)
  if (bad.length === 0 && pct === 100 && (scores?.flaggedUserStories ?? 0) > 0) {
    return ['*']
  }
  return bad
}
