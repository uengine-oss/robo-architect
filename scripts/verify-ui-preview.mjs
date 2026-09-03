/**
 * UI 인스펙터 미리보기 — 실제 장면 데이터로 스타일 규칙을 검사한다.
 *
 * 미리보기가 잘리는지는 눈으로만 보였다. 프런트엔드에 유닛 러너가 없어서
 * (Playwright 뿐이고, Design 캔버스까지 몰고 가는 경로는 잘 깨진다) 이 규칙은
 * 이렇게 지킨다 — **컴포넌트가 쓰는 바로 그 모듈**을 불러 그래프의 UI 노드
 * 전부에 걸어 본다.
 *
 *   node scripts/verify-ui-preview.mjs
 *
 * 백엔드가 떠 있어야 한다.
 */
import { execFileSync } from 'child_process'
import { nodeStyle, textStyle } from '../open-pencil/src/federation/frameStyle.ts'

const CYPHER = `MATCH (u:UI) RETURN u.name AS name, u.sceneGraph AS sg`
const raw = execFileSync('docker', [
  'exec', 'ontological-dev', 'psql', '-h', '127.0.0.1', '-p', '28816', '-U', 'dev', '-d', 'og',
  '-tAc', `SELECT og_cypher('${process.env.ROBO_GRAPH || 'robo'}', $$ ${CYPHER} $$)`,
], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 })

const scenes = []
for (const line of raw.split('\n')) {
  if (!line.trim()) continue
  try {
    const row = JSON.parse(line)
    const sg = typeof row.sg === 'string' ? JSON.parse(row.sg) : row.sg
    if (sg?.nodes) scenes.push({ name: row.name, sg })
  } catch { /* 부분 출력은 건너뛴다 */ }
}

let failed = 0
const check = (ok, label, detail = '') => {
  console.log(`${ok ? '✓' : '✗'} ${label}${detail ? '  ' + detail : ''}`)
  if (!ok) failed++
}

check(scenes.length > 0, 'UI 장면을 읽었다', `${scenes.length}개`)

const texts = []
for (const { name, sg } of scenes)
  for (const n of Object.values(sg.nodes)) if (n?.type === 'TEXT') texts.push({ name, n })
check(texts.length > 0, 'TEXT 노드가 있다', `${texts.length}개`)

// 컴포넌트가 실제로 만드는 스타일 — nodeStyle 위에 textStyle 을 덮는다.
const styleOf = (n) => ({ ...nodeStyle(n), ...textStyle(n) })

// 잘림의 조건: 높이가 고정인데 넘치는 것을 감춘다.
const clipped = texts.filter(({ n }) => {
  const s = styleOf(n)
  return s.overflow === 'hidden' && s.height && s.height !== 'auto'
})
check(clipped.length === 0, '높이를 고정한 채 넘침을 감추지 않는다',
      clipped.length ? `${clipped.length}개 — 예: "${(clipped[0].n.text || '').slice(0, 20)}"` : '')

// Figma 가 잰 값(WIDTH_AND_HEIGHT)을 너비 제약으로 쓰지 않는다.
const hugged = texts.filter(({ n }) => (n.textAutoResize || 'NONE') === 'WIDTH_AND_HEIGHT')
const overConstrained = hugged.filter(({ n }) => styleOf(n).width && styleOf(n).width !== 'auto')
check(overConstrained.length === 0, '잰 값을 너비 제약으로 쓰지 않는다',
      `hug ${hugged.length}개 중 ${overConstrained.length}개`)

// 줄바꿈이 살아 있어야 한다.
const noWrap = texts.filter(({ n }) => styleOf(n).whiteSpace !== 'pre-wrap')
check(noWrap.length === 0, '줄바꿈이 보존된다', noWrap.length ? `${noWrap.length}개` : '')

console.log(failed ? `\n실패 ${failed}건` : '\n전부 통과')
process.exit(failed ? 1 : 0)
