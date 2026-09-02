/**
 * 우리 생성기가 기준 구현(MSAez)과 같은 코드를 내는지 대조한다.
 *
 * 같은 모델·같은 템플릿·같은 렌더 엔진에 **순회 방식만** 바꿔 돌린다.
 *   A) 기준 — `modelForElements[forEach]` (MSAez 가 실제로 쓰는 타입별 평면 목록)
 *   B) 우리 — `itemsFor` (컨텍스트 중첩 순회)
 * 렌더 엔진이 같으므로 차이가 나면 그것은 전부 **순회와 모델 모양**에서 온다.
 *
 * 모델은 MSAez 의 Postgres 에서 꺼낸다. 기준 변환은 MSAez 자신의
 * `CodeGeneratorCore` 를 그대로 불러 쓴다 — 우리가 흉내 내지 않는다.
 *
 *   1) MSAez 스택과 Architect 백엔드가 떠 있어야 한다
 *   2) 모델을 꺼낸다
 *      docker exec msaez-postgres psql -U msaez -d msaez -tAc \
 *        "SELECT value::text FROM definitions WHERE project_id='3_es_<모델ID>'" > /tmp/msaez-model.json
 *   3) node scripts/compare-with-msaez.mjs /tmp/msaez-model.json [버전]
 *
 * `local-msaez` 클론이 필요하다(`MSAEZ_HOME` 으로 위치를 바꿀 수 있다).
 */
import { createRequire } from 'module'
import fs from 'fs'
// handlebars 는 프런트엔드 의존성이다 — 저장소 루트에는 없다.
const { default: Handlebars } = await import(
  new URL('../frontend/node_modules/handlebars/lib/index.js', import.meta.url).href
)
import { itemsFor, registerHelpers } from '../frontend/src/features/codeTemplates/renderer.js'

const require = createRequire(import.meta.url)
globalThis.window = { location: { hash: '' } }
const MSAEZ_HOME = process.env.MSAEZ_HOME || '/Users/seongwon/Desktop/local-msaez'
const CodeGeneratorCore = require(
  `${MSAEZ_HOME}/platform/src/components/designer/modeling/CodeGeneratorCore.js`,
)
const MODEL_FILE = process.argv[2]
const VERSION = process.argv[3]
if (!MODEL_FILE) {
  console.error('사용법: node scripts/compare-with-msaez.mjs <모델 JSON> [버전]')
  process.exit(1)
}
const raw = JSON.parse(fs.readFileSync(MODEL_FILE, 'utf8'))
const versions = Object.keys(raw.versionLists || {})
const version = VERSION || versions[versions.length - 1]
console.log(`모델 ${MODEL_FILE} · 버전 ${version} (있는 것: ${versions.join(', ')})\n`)
const model = JSON.parse(raw.versionLists[version].versionValue)
const canvas = {
  overrideElements: (v) => v,
  validateElementFormat: (e) => !!e && !Array.isArray(e) && !!e.elementView && !!e._type && Object.keys(e).indexOf('name') !== -1,
  validateRelationFormat: (r) => !!r && !Array.isArray(r) && !!r.relationView && !!r._type && Object.keys(r).indexOf('name') !== -1,
}
const { rootModel, modelForElements } = new CodeGeneratorCore({ canvas }).convertModelForCodeGen(model, {})

const res = await fetch('http://127.0.0.1:8000/api/code-templates/sets/template-poscodx/files')
const { files: templates } = await res.json()
const ctx = { boundedContexts: rootModel.boundedContexts, options: { serviceId: 'sample' }, currentTimestamp: 'TS' }

// A) MSAez 순회 — 렌더 엔진은 우리 것을 그대로 쓴다.
function renderWith(pick) {
  const hb = Handlebars.create()
  const scope = { contexts: {}, dataProjection: 'cqrs' }
  registerHelpers(hb, templates.flatMap(t => t.functions || []), scope)
  const out = new Map()
  const errs = []
  const ambient = (n, seen = new WeakSet()) => {
    if (Array.isArray(n)) return n.map(x => ambient(x, seen))
    if (!n || typeof n !== 'object' || seen.has(n)) return n
    seen.add(n)
    const o = { options: ctx.options, currentTimestamp: ctx.currentTimestamp }
    for (const [k, v] of Object.entries(n)) o[k] = ambient(v, seen)
    return o
  }
  for (const t of templates) {
    if (!t.forEach || t.isConfiguration) continue
    for (const item of pick(t.forEach)) {
      const m = ambient({ ...item, ...scope.contexts })
      try {
        const dir = t.path ? hb.compile(t.path)(m) : ''
        const name = t.fileName ? hb.compile(t.fileName)(m) : t.relativePath.split('/').pop()
        out.set([dir, name].filter(Boolean).join('/'), hb.compile(t.body || '')(m))
      } catch (e) { errs.push(`${t.relativePath}: ${e.message}`) }
    }
  }
  return { out, errs }
}

const A = renderWith((fe) => modelForElements[fe] || [])
const B = renderWith((fe) => itemsFor(fe, ctx))

console.log(`A) MSAez 순회 : ${A.out.size}개 (오류 ${A.errs.length})`)
console.log(`B) 우리 순회   : ${B.out.size}개 (오류 ${B.errs.length})`)

const onlyA = [...A.out.keys()].filter(k => !B.out.has(k))
const onlyB = [...B.out.keys()].filter(k => !A.out.has(k))
const both = [...A.out.keys()].filter(k => B.out.has(k))
const diff = both.filter(k => A.out.get(k) !== B.out.get(k))

console.log(`\n공통 ${both.length}개 · 내용 불일치 ${diff.length}개`)
console.log(`A 에만 ${onlyA.length}개`, onlyA.slice(0, 6).map(p => p.split('/').pop()).join(', '))
console.log(`B 에만 ${onlyB.length}개`, onlyB.slice(0, 6).map(p => p.split('/').pop()).join(', '))
for (const k of diff.slice(0, 3)) {
  console.log(`\n--- 다름: ${k}`)
  const a = A.out.get(k).split('\n'), b = B.out.get(k).split('\n')
  for (let i = 0; i < Math.max(a.length, b.length); i++)
    if (a[i] !== b[i]) { console.log(`  A[${i}] ${JSON.stringify(a[i])}`); console.log(`  B[${i}] ${JSON.stringify(b[i])}`); break }
}

// 파일 하나라도 다르거나 빠지면 실패다.
const failed = diff.length + onlyA.length + onlyB.length
console.log(failed ? `\n불일치 ${failed}건` : '\n기준과 동일하다')
process.exit(failed ? 1 : 0)
