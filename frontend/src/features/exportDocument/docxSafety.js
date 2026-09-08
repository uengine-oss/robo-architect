/**
 * docx 를 깨뜨리지 않기 위한 최소 방어.
 *
 * 여기 있는 셋은 전부 **문서가 만들어진 뒤에야 드러나는** 문제를 막는다. 생성은
 * 성공하고 오류도 안 나는데, Word 가 "일부 콘텐츠를 읽을 수 없습니다"로 복구를 묻고
 * 사내 ECM 은 등록을 거부한다. 기준 구현(local-msaez)이 같은 이유로 넣은 것들이다.
 *
 *   local-msaez  50e1e327  제어문자 · 빈 캡처 · 종횡비
 *                7002186b  표 보더 style
 *
 * 화면과 떼어 둔 이유는 검사할 수 있게 하기 위해서다 — 제어문자가 섞인 문서를 만들어
 * 열어 보는 것은 손이 많이 가는데, 함수는 바로 넣어 볼 수 있다.
 * → `scripts/verify-docx-safety.mjs`
 */

/**
 * 문자열에서 XML 1.0 이 허용하지 않는 문자를 걷어낸다.
 *
 * LLM 과 레거시 원본에서 온 문자열이 그대로 TextRun 에 들어간다. 제어문자가 하나라도
 * 섞이면 OOXML 이 깨진다. 탭·개행·복귀는 XML 이 허용하므로 남긴다.
 *
 * 코드포인트로 거르는 이유는 정규식 리터럴에 제어문자를 적어 넣지 않기 위해서다 —
 * 눈에 안 보이는 문자가 소스에 남으면 나중에 손대다 조용히 망가진다.
 */
export function xmlSafe(s) {
  const str = String(s == null ? '' : s)
  let out = ''
  for (const ch of str) {
    const c = ch.codePointAt(0)
    if (c < 0x20 && c !== 0x09 && c !== 0x0a && c !== 0x0d) continue  // C0 제어문자
    if (c === 0xfffe || c === 0xffff) continue                        // 비문자
    out += ch
  }
  return out
}

/**
 * docx 에 넣어도 안전한 PNG 인지 본다.
 *
 * `htmlToImage` 가 실패하면 빈 dataURL 이 남는다. 그게 ImageRun 으로 들어가면 패키지가
 * 무효해진다. 캡처가 빠진 문서보다 **깨진 문서**가 나쁘므로, 미심쩍으면 그림을 뺀다.
 */
export function isValidPng(buf) {
  if (!buf) return false
  const len = buf.byteLength != null ? buf.byteLength : (buf.length || 0)
  if (len < 100) return false   // 사실상 빈 캡처
  try {
    const v = buf instanceof Uint8Array ? buf : new Uint8Array(buf)
    return v[0] === 0x89 && v[1] === 0x50 && v[2] === 0x4e && v[3] === 0x47
  } catch { return false }
}

/**
 * PNG 의 IHDR 에서 실제 크기를 읽어 종횡비를 지키며 페이지 안에 맞춘다.
 *
 * 고정 크기로 박으면 가로로 긴 도식이 눌린다. 크기를 못 읽으면 폭만 맞춘다.
 */
export function fitPng(buf, maxWidth, maxHeight) {
  try {
    const v = buf instanceof Uint8Array ? buf : new Uint8Array(buf)
    if (v.length >= 24) {
      const w = ((v[16] << 24) | (v[17] << 16) | (v[18] << 8) | v[19]) >>> 0
      const h = ((v[20] << 24) | (v[21] << 16) | (v[22] << 8) | v[23]) >>> 0
      if (w > 0 && h > 0) {
        const scale = Math.min(maxWidth / w, maxHeight / h, 1)
        return { width: Math.max(1, Math.round(w * scale)), height: Math.max(1, Math.round(h * scale)) }
      }
    }
  } catch { /* 아래 기본값 */ }
  return { width: maxWidth, height: Math.round(maxWidth * 0.64) }
}
