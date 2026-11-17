/**
 * 산출물 파일 이름 (2026-11-16) — 고객이 정한 규칙을 한곳에서 만든다.
 *
 *   서비스설계서: 설계_{프로젝트명}_서비스설계서_YYYYMMDD_HHmmss.docx
 *
 * 전에는 `toISOString()` 으로 날짜를 찍어 **UTC** 였다 — 한국 09시 전에 내려받으면
 * 전날 날짜가 붙었다. 여기서는 **브라우저 현지 시각**을 쓴다.
 *
 * 정본화 요청(`filename`)과 실제 내려받는 이름이 이 함수가 낸 **한 값**을 같이 쓴다
 * (전에는 두 곳에서 따로 만들어 초 단위로 어긋날 수 있었다).
 */

/** 파일명에 못 쓰는 글자(Windows 기준) + 제어문자. */
// eslint-disable-next-line no-control-regex
const FORBIDDEN = /[\\/:*?"<>|\u0000-\u001f\u007f]/g

/**
 * 프로젝트명을 파일 이름에 넣을 수 있게 다듬는다.
 * 금지 문자·제어문자, 앞뒤 공백, 끝의 점은 `_` 로 바꾸고, 비면 `프로젝트`.
 */
export function sanitizeFileNamePart(name, fallback = '프로젝트') {
  const raw = name == null ? '' : String(name)
  if (!raw.trim()) return fallback
  return raw
    .replace(FORBIDDEN, '_')
    .replace(/^\s+|\s+$/g, '_')
    .replace(/\.+$/, '_')
}

const pad2 = (n) => String(n).padStart(2, '0')

/** `YYYYMMDD_HHmmss` — 브라우저 현지 시각. */
export function formatLocalTimestamp(date = new Date()) {
  return (
    `${date.getFullYear()}${pad2(date.getMonth() + 1)}${pad2(date.getDate())}` +
    `_${pad2(date.getHours())}${pad2(date.getMinutes())}${pad2(date.getSeconds())}`
  )
}

/**
 * 규칙 이름 일반형: `{prefix}_{프로젝트명}_{docType}_YYYYMMDD_HHmmss.{ext}`.
 * 다른 산출물(예: Aggregate정의서)에 규칙이 정해지면 docType 만 바꿔 쓴다.
 */
export function buildDeliverableFileName({ projectName, docType, date = new Date(), ext = 'docx', prefix = '설계' }) {
  return `${prefix}_${sanitizeFileNamePart(projectName)}_${docType}_${formatLocalTimestamp(date)}.${ext}`
}

/** 서비스설계서(Word 내보내기) 파일 이름. */
export function serviceDesignDocFileName(projectName, date = new Date()) {
  return buildDeliverableFileName({ projectName, docType: '서비스설계서', date })
}
