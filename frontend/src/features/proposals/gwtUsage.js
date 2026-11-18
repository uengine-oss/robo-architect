// B-3 ⑪ — Intent 의 인수조건이 검증에 쓰이는지 화면에 드러낸다(순수 로직).
//
// 검증(test_runner)은 전술 GWT(Command)와 전략 인수조건(UserStory)을 **둘 다** 잰다.
// 결과 항목의 `criterionSource` 가 'strategic' 이면 Intent 인수조건으로 잰 것이다.

function parse(raw, fallback) {
  if (typeof raw === 'string') {
    try { return JSON.parse(raw) } catch { return fallback }
  }
  return raw ?? fallback
}

/** strategicDiff 안 UserStory 인수조건 수. */
export function countIntentCriteria(strategicDiff) {
  const sd = parse(strategicDiff, {})
  const stories = Array.isArray(sd?.userStories) ? sd.userStories : []
  let n = 0
  for (const us of stories) {
    const ac = parse(us?.acceptanceCriteria, [])
    if (Array.isArray(ac)) n += ac.length
  }
  return n
}

/** 검증 결과 중 Intent 인수조건(strategic)으로 잰 항목의 PASS/FAIL/SKIP 집계. 없으면 null. */
export function summarizeStrategicResults(testResults, proposalId = null) {
  if (!testResults) return null
  if (proposalId && testResults.proposalId && testResults.proposalId !== proposalId) return null
  const items = (testResults.items || []).filter((it) => it?.criterionSource === 'strategic')
  if (!items.length) return null
  const out = { pass: 0, fail: 0, skip: 0 }
  for (const it of items) {
    const r = String(it.result || '').toUpperCase()
    if (r === 'PASS') out.pass += 1
    else if (r === 'FAIL') out.fail += 1
    else out.skip += 1
  }
  return out
}
