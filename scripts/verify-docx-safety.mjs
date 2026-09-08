/**
 * docx 안전장치 검사.
 *
 * 여기서 막는 셋은 전부 **문서는 만들어지는데 열 때 깨지는** 부류다. 오류가 안 나므로
 * 생성 로그로는 알 수 없고, Word 를 열거나 ECM 에 올려야 드러난다. 기준 구현
 * (local-msaez `50e1e327` · `7002186b`)이 같은 이유로 넣은 것들을 우리도 갖췄는지 본다.
 *
 *   node scripts/verify-docx-safety.mjs
 */
import { xmlSafe, isValidPng, fitPng } from '../frontend/src/features/exportDocument/docxSafety.js'
import { readFileSync } from 'fs'

let failed = 0
function check(name, cond, detail = '') {
  if (cond) console.log(`  ok   ${name}`)
  else { failed++; console.log(`  FAIL ${name}${detail ? ' — ' + detail : ''}`) }
}

console.log('\nXML 비허용 문자')
{
  // C0 제어문자 — 하나만 섞여도 OOXML 이 깨진다.
  const ctrl = String.fromCharCode(0, 1, 8, 11, 12, 14, 27, 31)
  const dirty = `휴가${ctrl}신청`
  check('C0 제어문자를 걷어낸다', xmlSafe(dirty) === '휴가신청', JSON.stringify(xmlSafe(dirty)))

  // 탭·개행·복귀는 XML 이 허용한다 — 지우면 본문이 뭉개진다.
  const keep = 'a\tb\nc\rd'
  check('탭·개행·복귀는 남긴다', xmlSafe(keep) === keep, JSON.stringify(xmlSafe(keep)))

  check('비문자 U+FFFE / U+FFFF 를 걷어낸다',
    xmlSafe('a' + String.fromCharCode(0xfffe) + String.fromCharCode(0xffff) + 'b') === 'ab')
  check('한글·이모지·서러게이트 쌍은 그대로', xmlSafe('연차 부여 🗓 정산') === '연차 부여 🗓 정산')
  check('null·undefined 를 빈 문자열로', xmlSafe(null) === '' && xmlSafe(undefined) === '')
  check('숫자도 문자열로 받는다', xmlSafe(42) === '42')
}

console.log('\n캡처 이미지 검증')
{
  const png = (w, h, extra = 200) => {
    const b = new Uint8Array(24 + extra)
    b.set([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a], 0)
    b[16] = (w >>> 24) & 255; b[17] = (w >>> 16) & 255; b[18] = (w >>> 8) & 255; b[19] = w & 255
    b[20] = (h >>> 24) & 255; b[21] = (h >>> 16) & 255; b[22] = (h >>> 8) & 255; b[23] = h & 255
    return b
  }
  check('정상 PNG 를 통과시킨다', isValidPng(png(800, 600)))
  check('빈 캡처를 막는다', !isValidPng(new Uint8Array(0)) && !isValidPng(null))
  check('짧은 잔재를 막는다 (100바이트 미만)', !isValidPng(png(10, 10, 0)))
  check('PNG 가 아닌 것을 막는다', !isValidPng(new Uint8Array(300)))
  check('ArrayBuffer 도 받는다', isValidPng(png(800, 600).buffer))
}

console.log('\n종횡비')
{
  const png = (w, h) => {
    const b = new Uint8Array(224)
    b.set([0x89, 0x50, 0x4e, 0x47], 0)
    b[16] = (w >>> 24) & 255; b[17] = (w >>> 16) & 255; b[18] = (w >>> 8) & 255; b[19] = w & 255
    b[20] = (h >>> 24) & 255; b[21] = (h >>> 16) & 255; b[22] = (h >>> 8) & 255; b[23] = h & 255
    return b
  }
  const wide = fitPng(png(2000, 500), 550, 700)
  check('가로로 긴 도식이 눌리지 않는다', Math.abs(wide.width / wide.height - 4) < 0.05,
    `${wide.width}x${wide.height}`)
  check('폭 한계를 넘지 않는다', wide.width <= 550)

  const tall = fitPng(png(500, 3000), 550, 700)
  check('세로로 긴 도식이 페이지를 넘지 않는다', tall.height <= 700, `${tall.width}x${tall.height}`)
  check('세로도 비율을 지킨다', Math.abs(tall.width / tall.height - 500 / 3000) < 0.01)

  const small = fitPng(png(200, 100), 550, 700)
  check('작은 그림을 억지로 늘리지 않는다', small.width === 200 && small.height === 100,
    `${small.width}x${small.height}`)

  const broken = fitPng(new Uint8Array(4), 550, 700)
  check('크기를 못 읽어도 값을 준다', broken.width === 550 && broken.height > 0)
}

console.log('\n내보내기 배선')
{
  // 함수가 있어도 부르지 않으면 소용없다. 실제 경로에서 쓰는지 본다.
  const src = readFileSync(
    new URL('../frontend/src/features/exportDocument/ui/exporters/captureExporter.js', import.meta.url), 'utf-8')
  check('모든 텍스트가 지나는 자리에서 거른다', /function txt\([^)]*\)[^{]*\{[^}]*xmlSafe\(/.test(src))
  check('그림을 넣기 전에 검증한다', src.includes('isValidPng(img)'))
  check('그림 크기를 계산해 넣는다', src.includes('fitPng(img'))
  check('표 보더에 style 을 준다 — 없으면 선이 안 그려진다', src.includes('BorderStyle.SINGLE'))
  check('머리글 셰이딩에 type 을 준다 — 없으면 w:val 없는 태그가 나간다',
    src.includes('ShadingType.CLEAR') && !/shading: \{ fill:/.test(src))
  check('ImageRun 에 png 를 명시한다 — 없으면 확장자가 .undefined 가 된다', /type: 'png'/.test(src))
  check('표 머리글을 장마다 되풀이한다', src.includes('tableHeader: true'))
  check('행을 가운데서 자르지 않는다', src.includes('cantSplit: true'))
  check('ECM 등록용 정본화를 거친다', readFileSync(
    new URL('../frontend/src/features/exportDocument/ui/ExportDocumentDialog.vue', import.meta.url), 'utf-8')
    .includes('docx-normalization/normalize'))
}

console.log(failed === 0 ? '\n전부 통과\n' : `\n${failed}건 실패\n`)
process.exit(failed === 0 ? 0 : 1)
