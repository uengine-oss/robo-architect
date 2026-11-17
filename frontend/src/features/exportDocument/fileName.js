/**
 * 산출물 파일 이름 — 이름을 만드는 규칙을 한곳에 둔다.
 *
 * 이름 **틀**은 고객 확장 값(`customer.deliverables.fileNameTemplate`)이다. 코어는 틀을
 * 모른다 — 호출부가 틀을 넘기고, 여기서는 칸만 채운다.
 *
 *   틀이 있을 때  : 틀의 칸 `{project}` `{kind}` `{yyyyMMdd}` `{HHmmss}` 를 채우고 `.{ext}` 를 붙인다.
 *                   시각은 **브라우저 현지 시각**(`toISOString()` 은 UTC 라 한국 09시 전엔
 *                   전날 날짜가 붙었다).
 *   틀이 없을 때  : 코어 기본 이름 `{baseName}-YYYY-MM-DD.{ext}` (옛 형식 그대로 — UTC 날짜).
 *
 * 정본화 요청(`filename`)과 실제 내려받는 이름이 이 함수가 낸 **한 값**을 같이 쓴다
 * (전에는 두 곳에서 따로 만들어 초 단위로 어긋날 수 있었다).
 *
 * 이 파일은 `@customer` 를 직접 읽지 않는다 — 단위 시험이 빌드 alias 없이 불러 쓰도록.
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

/** `YYYYMMDD` — 브라우저 현지 시각. */
export function formatLocalDate(date = new Date()) {
  return `${date.getFullYear()}${pad2(date.getMonth() + 1)}${pad2(date.getDate())}`
}

/** `HHmmss` — 브라우저 현지 시각. */
export function formatLocalTime(date = new Date()) {
  return `${pad2(date.getHours())}${pad2(date.getMinutes())}${pad2(date.getSeconds())}`
}

/** `YYYYMMDD_HHmmss` — 브라우저 현지 시각. */
export function formatLocalTimestamp(date = new Date()) {
  return `${formatLocalDate(date)}_${formatLocalTime(date)}`
}

/** 코어 기본 이름(옛 형식): `{baseName}-YYYY-MM-DD.{ext}` — UTC 날짜. */
export function legacyFileName(baseName, ext, date = new Date()) {
  return `${baseName}-${date.toISOString().split('T')[0]}.${ext}`
}

/**
 * 산출물 파일 이름.
 *
 * @param {object} o
 * @param {string|null} o.template  고객 틀(없으면 코어 기본 이름)
 * @param {string} o.kind           산출물 종류(틀의 `{kind}`) — 예: 서비스설계서
 * @param {string} [o.baseName]     틀이 없을 때의 기본 이름 앞부분(없으면 kind)
 * @param {string} [o.projectName]  틀의 `{project}`
 * @param {Date}   [o.date]
 * @param {string} [o.ext]
 */
export function buildDeliverableFileName({ template, kind, baseName, projectName, date = new Date(), ext = 'docx' }) {
  if (!template) return legacyFileName(baseName || kind, ext, date)
  const values = {
    project: sanitizeFileNamePart(projectName),
    kind: sanitizeFileNamePart(kind, ''),
    yyyyMMdd: formatLocalDate(date),
    HHmmss: formatLocalTime(date),
  }
  const stem = String(template).replace(/\{(\w+)\}/g, (m, key) => (key in values ? values[key] : m))
  return `${stem}.${ext}`
}

/** 서비스설계서(Word 내보내기) 파일 이름. `template` 은 `customer.deliverables.fileNameTemplate`. */
export function serviceDesignDocFileName(projectName, { template = null, date = new Date() } = {}) {
  return buildDeliverableFileName({ template, kind: '서비스설계서', baseName: '설계산출물', projectName, date })
}
