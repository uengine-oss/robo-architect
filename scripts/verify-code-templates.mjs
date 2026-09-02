/**
 * 템플릿 기반 코드 생성 — 끝까지 돌려 보고 결과를 검사한다.
 *
 * 프런트엔드에 유닛 러너가 없어서(Playwright 뿐) 이 경로는 이렇게 지킨다.
 * **배포되는 모듈을 그대로 불러** 실제 API·실제 모델로 렌더링하므로, 화면에서
 * 보게 될 것과 같은 결과를 검사한다.
 *
 *   node scripts/verify-code-templates.mjs [sessionId] [serviceId] [set]
 *
 * 백엔드가 떠 있어야 한다. 세션은 생략하면 첫 번째 산출물 세션을 쓴다.
 */
import { renderAll } from '../frontend/src/features/codeTemplates/renderer.js'
import { buildTree, collapseChains, firstFile } from '../frontend/src/features/codeTemplates/tree.js'

const BASE = process.env.ROBO_API || 'http://127.0.0.1:8000'
const [, , argSession, argService = 'sample', argSet = 'template-poscodx'] = process.argv

const get = async (p) => {
  const r = await fetch(BASE + p)
  if (!r.ok) throw new Error(`${p} → HTTP ${r.status}`)
  return r.json()
}

let failed = 0
const check = (ok, label, detail = '') => {
  console.log(`${ok ? '✓' : '✗'} ${label}${detail ? '  ' + detail : ''}`)
  if (!ok) failed++
}

const sessionId =
  argSession || (await get('/api/deliverables/sessions')).sessions?.[0]?.id
if (!sessionId) {
  console.error('산출물 세션이 없습니다 — 이벤트 스토밍 승격을 먼저 끝내세요.')
  process.exit(1)
}
console.log(`세션 ${sessionId} · serviceId ${argService} · 템플릿 ${argSet}\n`)

const { files: templates, summary } = await get(
  `/api/code-templates/sets/${encodeURIComponent(argSet)}/files`,
)
const ctx = await get(
  `/api/code-templates/context?sessionId=${encodeURIComponent(sessionId)}&serviceId=${encodeURIComponent(argService)}`,
)

const { files, errors } = renderAll(templates, ctx)

check(summary.renderable > 0, '렌더 대상 템플릿이 있다', `${summary.renderable}/${summary.files}장`)
check(errors.length === 0, '렌더링 오류가 없다', errors.length ? errors[0].error : '')
for (const e of errors.slice(0, 5)) console.log(`    ${e.template} — ${e.error}`)
check(files.length > 0, '파일이 생성됐다', `${files.length}개`)

// 미치환 자리표시자가 남으면 템플릿이 요구한 값을 컨텍스트가 못 준 것이다.
const unrendered = files.filter((f) => /\{\{/.test(f.content) || /\{\{/.test(f.path))
check(unrendered.length === 0, '미치환 {{ }} 가 없다', unrendered[0]?.path || '')

// `undefined` 는 이름 변형이 빠졌을 때 필드·경로에 그대로 찍힌다.
const undef = files.filter((f) => f.content.includes('undefined') || f.path.includes('undefined'))
check(undef.length === 0, 'undefined 가 새지 않았다', undef[0]?.path || '')

// 빈 패키지 마디 — Handlebars 가 상위 스코프를 안 타서 생기던 것.
// `package` 줄만이 아니라 `import` 줄에도 난다. 처음엔 package 만 봤고,
// 되돌려 심은 결함을 놓쳐서 넓혔다.
const emptySegLine = (text) =>
  (text.match(/^\s*(?:package|import)\s+[\w.]*\.\.[\w.]*/m) || [])[0]
const emptySeg = files.filter((f) => emptySegLine(f.content))
check(emptySeg.length === 0, '패키지·import 에 빈 마디가 없다',
      emptySeg.length ? `${emptySeg[0].path} — ${emptySegLine(emptySeg[0].content).trim()}` : '')

const unbalanced = files.filter((f) => {
  if (!f.path.endsWith('.java')) return false
  const o = (f.content.match(/\{/g) || []).length
  const c = (f.content.match(/\}/g) || []).length
  return o !== c
})
check(unbalanced.length === 0, '자바 중괄호가 맞는다', unbalanced[0]?.path || '')

check(files.every((f) => f.content.length > 0), '빈 파일이 없다')

// JDK 타입을 생성 패키지에서 import 하는 것.
//
// 템플릿의 `isPrimitive` 는 String·Integer·Long·Double·Float·Boolean·Date 만
// 원시로 보고 나머지는 전부 값 객체로 취급해 import 한다. 그래서 우리 모델의
// `UUID`·`boolean` 같은 이름이 그대로 새면
// `import ….store.domain.vo.UUID;` 가 나오고, 그 클래스는 존재하지 않는다.
const JDK_TYPES = new Set([
  'String', 'Integer', 'Long', 'Double', 'Float', 'Boolean', 'Byte', 'Short',
  'Character', 'Object', 'Date', 'Timestamp', 'UUID', 'BigDecimal', 'BigInteger',
  'List', 'Set', 'Map', 'Collection',
  'boolean', 'int', 'long', 'double', 'float', 'char', 'byte', 'short',
])
const jdkImport = (text) => {
  for (const line of text.split('\n')) {
    const m = line.match(/^\s*import\s+[\w.]*\.(\w+)\s*;/)
    if (m && JDK_TYPES.has(m[1]) && /\.(vo|dto|entity)\./.test(line)) return line.trim()
  }
  return null
}
const jdkImports = files.filter((f) => f.path.endsWith('.java') && jdkImport(f.content))
check(jdkImports.length === 0, 'JDK 타입을 생성 패키지에서 import 하지 않는다',
      jdkImports.length ? `${jdkImports[0].path} — ${jdkImport(jdkImports[0].content)}` : '')

const tree = collapseChains(buildTree(files))
const countFiles = (ns) => ns.reduce((a, n) => a + (n.dir ? countFiles(n.children) : 1), 0)
check(countFiles(tree) === files.length, '트리가 파일을 하나도 잃지 않는다',
      `${countFiles(tree)}/${files.length}`)
check(!!firstFile(tree), '트리에서 첫 파일을 찾는다', firstFile(tree)?.path || '')

const perTop = {}
for (const f of files) perTop[f.path.split('/')[0]] = (perTop[f.path.split('/')[0]] || 0) + 1
console.log('\nBC 별:', JSON.stringify(perTop))
console.log(failed ? `\n실패 ${failed}건` : '\n전부 통과')
process.exit(failed ? 1 : 0)
