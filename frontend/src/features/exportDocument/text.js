/**
 * 산출물 문서에 **글자를 어떻게 적는가** — 자르기와 참/거짓.
 *
 * ## 왜 따로 있나
 *
 * 둘 다 `captureExporter.js` 안에 있었고, 그 파일은 `html-to-image`·`pptxgenjs` 를
 * 들여와서 **검사에서 불러올 수 없다**(브라우저가 있어야 한다). 그래서 판정만 떼어
 * 둔다 — `runtime-status/messages.js` 와 같은 이유다.
 *
 * ## 무엇을 재나
 *
 * 2026-10-08 에 기준 프로젝트(`prj_16972790c0`)의 실제 값으로 재서 둘 다 결함이었다.
 */

/**
 * 요약 표에 넣을 만큼 **줄이되, 낱말을 끊지 않는다.**
 *
 * 실측 — `.slice(0, 80)` 이 BC 설명 **5/5**(165~260자)와 Read Model 설명
 * **14/14**(118~247자)를 **낱말 중간에서** 끊었다. 문서에 이렇게 들어갔다 —
 *
 * ```
 * …including dynamic approval lin
 * …expiration of annual leave enti
 * ```
 *
 * 말줄임이 없어서 **읽는 사람은 그게 문장의 끝인 줄 안다.** 게다가 화면 미리보기는
 * 자르지 않으므로 **미리보기로는 이것이 보이지 않았다.**
 *
 * 전문은 다른 자리에 그대로 있다(BC 설명은 `BC 상세`, Read Model 설명은 `API 명세` 의
 * Read Model 블록). 그래서 요약 표에서 줄이는 것은 맞고, **줄였다는 것만 보이면** 된다.
 */
export function clip(text, max) {
  const s = String(text ?? '').trim()
  if (!s) return '-'
  if (s.length <= max) return s
  const cut = s.slice(0, max)
  // 마지막 공백에서 자른다. 공백이 없는 긴 토큰(식별자·한 덩이 한글)이면 그냥 자른다 —
  // 그 경우에도 말줄임은 붙으므로 "끝이 아니다" 는 보인다.
  const space = cut.lastIndexOf(' ')
  return (space > max * 0.6 ? cut.slice(0, space) : cut).trimEnd() + '…'
}

/**
 * 조회 결과가 **다건인가 단건인가.**
 *
 * `isMultipleResult || '-'` 로 적고 있었다. `false` 는 **단건이라는 사실**인데 `-`
 * (=모른다)로 바뀌어, 읽는 사람은 "이 Read Model 은 결과 형태를 안 정했다" 고 읽는다.
 * 기준 프로젝트에는 `false` 가 0개여서 **드러나지 않고 있었다.**
 */
export function resultKind(value) {
  if (value == null || value === '') return '-'
  if (typeof value === 'string') return value
  return value ? '다건' : '단건'
}
