/**
 * 템플릿 한 장이 **문법적으로 성립하는가**.
 *
 * 고칠 수 있게 된 순간부터(TPL-1) 문법 오류는 흔한 일이 됐다. 그대로 저장하면
 * 중앙 DB 에 들어가 **모든 PC 의 생성이 그 장에서 깨진다** — 고친 사람은 이미
 * 자기 화면을 떠난 뒤다. 그래서 저장 전에 한 번 컴파일해 본다.
 *
 * 쪼개는 규칙은 백엔드(`repository.parse_template`)와 같다 — front matter 를 떼고
 * `<function>` 을 가른다. **권위는 그쪽이다.** 여기는 사람이 바로 보라고 두는
 * 거울이고, 그래서 규칙이 어긋나면 이쪽을 고친다.
 *
 * `new Function(src)` 은 **컴파일만** 한다 — 본문을 실행하지 않는다. 실행은
 * 렌더링할 때 `renderer.js` 가 한다.
 */

import Handlebars from 'handlebars'

const FUNCTION_BLOCK = /<function>([\s\S]*?)<\/function>/g
const FRONT_MATTER_SEP = '\n---\n'

/** front matter 를 뗀 나머지. 구분자가 없으면 통째로 본문이다. */
export function bodyOf(text) {
  const raw = String(text || '')
  const cut = raw.indexOf(FRONT_MATTER_SEP)
  return cut >= 0 ? raw.slice(cut + FRONT_MATTER_SEP.length) : raw
}

/**
 * 문법 오류 문구. 성립하면 `null`.
 *
 * 메시지에 **무엇이 깨졌는지**를 앞에 붙인다 — Handlebars 의 원문만 보여 주면
 * 사람은 그것이 템플릿 문법 얘기인지 자바 얘기인지 가리지 못한다.
 */
export function syntaxError(text) {
  const rest = bodyOf(text)
  // **태그 짝을 먼저 센다.** 이것이 Handlebars 컴파일로는 안 잡힌다 — 안 닫힌
  // `<function>` 은 정규식에 안 걸리니 블록으로 **안 보이고**, 남은 JS 는
  // Handlebars 에게 그냥 글자다. 그대로 저장되면 그 JavaScript 가 생성된
  // 파일에 **본문으로 찍힌다**. 서버 검사(`syntax.py`)와 같은 규칙이다.
  const opens = (rest.match(/<function>/g) || []).length
  const closes = (rest.match(/<\/function>/g) || []).length
  if (opens !== closes) {
    return `\`<function>\` 태그의 짝이 맞지 않습니다 — 여는 것 ${opens}개, 닫는 것 ${closes}개.`
  }
  const blocks = [...rest.matchAll(FUNCTION_BLOCK)]
  const body = rest.replace(FUNCTION_BLOCK, '')
  try {
    Handlebars.precompile(body)
  } catch (e) {
    return `템플릿 문법: ${(e && e.message) || e}`
  }
  for (const [, src] of blocks) {
    try {
      new Function(src) // eslint-disable-line no-new-func -- 컴파일만 한다
    } catch (e) {
      return `<function> 블록의 JavaScript 문법: ${(e && e.message) || e}`
    }
  }
  return null
}
