/**
 * 산출물 문서의 **섹션 번호** — 어느 섹션이 실리고, 몇 번인가.
 *
 * ## 왜 따로 있나
 *
 * 번호를 매기는 쪽(화면 템플릿)과 섹션을 싣는 쪽(`captureExporter`)이 **조건을 따로
 * 적고 있었다.** 그러면 한쪽만 고쳐져 어긋난다 — 실제로 어긋났다(아래).
 * 한 자리에 두고 둘이 같이 쓴다. `.vue` 안에 두면 검사가 못 부른다.
 *
 * ## 무엇이 틀렸나 (2026-10-08)
 *
 * 켜 두었는데 **데이터가 없어 안 실리는** 섹션이 셋이다 —
 *
 * ```
 * 밸류 스트림      업로드 문서에서 나온다
 * Aggregate 설계   Aggregate 를 가진 BC 가 있어야 한다
 * 추적성 매트릭스   세션 산출물이 있어야 한다
 * ```
 *
 * 번호를 "켜졌는가" 로만 매기면 **안 실린 섹션이 번호를 먹는다.** 코드 분석 문서를
 * 올리지 않고 바로 생성하면 밸류 스트림과 추적성이 비므로 문서가 `1 → 3 → …` 으로
 * 뛰고, 받는 사람에게는 **섹션이 빠진 문서**로 보인다.
 */

/** 문서에 실리는 순서. 번호는 이 순서로 매긴다. */
export const SECTION_ORDER = [
  'userStories',
  'valueStream',
  'boundedContext',
  'aggregateDesign',
  'modelOverview',
  'apiSpecification',
  'aggregateDetail',
  'traceabilityMatrix',
]

/**
 * 그 섹션이 **문서에 실제로 실리는가.**
 *
 * `selected` 는 사용자가 켠 것, `data` 는 그 섹션이 실릴 수 있는지를 가르는 수다.
 * `userStories` 는 비어도 "등록된 사용자 스토리가 없습니다" 를 적으므로 **늘 실린다** —
 * 빈 것과 안 실리는 것은 다르다.
 */
export function sectionShown(selected, data) {
  const on = selected || {}
  const d = data || {}
  return {
    userStories: Boolean(on.userStories),
    valueStream: Boolean(on.valueStream && d.valueStreamCount),
    boundedContext: Boolean(on.boundedContext),
    aggregateDesign: Boolean(on.aggregateDesign && d.aggregateDesignCount),
    modelOverview: Boolean(on.modelOverview),
    apiSpecification: Boolean(on.apiSpecification),
    aggregateDetail: Boolean(on.aggregateDetail),
    traceabilityMatrix: Boolean(on.traceabilityMatrix && d.hasTraceSummary),
  }
}

/** 실리는 것만 **1부터 빈틈없이** 번호를 준다. */
export function sectionNumbers(shown) {
  const s = shown || {}
  let n = 0
  const nums = {}
  for (const key of SECTION_ORDER) {
    if (s[key]) nums[key] = ++n
  }
  return nums
}
