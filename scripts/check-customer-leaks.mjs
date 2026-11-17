#!/usr/bin/env node
/**
 * 기본(default) 빌드에 **고객 문자열이 새지 않았나** 본다 — 단일 브랜치 통합 설계 §3-3 "새는 문자열 0".
 *
 *   node scripts/check-customer-leaks.mjs <폴더> [<폴더> …]
 *
 * 폴더 아래 텍스트 파일(js · css · html · json · map 제외)을 훑어 금지 문자열을 찾는다.
 * 하나라도 있으면 어느 파일에 무엇이 있는지 적고 1 로 끝난다.
 *
 * 왜 번들을 보나: 소스 grep 은 "import 경로에 없다" 를 증명하지 못한다. 고객 폴더를
 * 잘못 import 하면 소스에는 문자열이 없어도 번들에 들어간다.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, extname } from 'node:path'

// 고객별 금지 문자열. 고객을 더하면 여기에 한 줄.
const FORBIDDEN = {
  posco: ['poscodx', 'swpsso', 'searchDataDictionary', '설계_', 'P-GPT'],
}

const TEXT = new Set(['.js', '.mjs', '.cjs', '.css', '.html', '.json', '.py', '.yml', '.yaml', '.env', '.txt'])

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === 'node_modules' || name === '.git') continue
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) yield* walk(p)
    else if (TEXT.has(extname(name)) && !name.endsWith('.map')) yield p
  }
}

const roots = process.argv.slice(2)
if (roots.length === 0) {
  console.error('사용법: node scripts/check-customer-leaks.mjs <폴더> [<폴더> …]')
  process.exit(2)
}

const hits = []
let scanned = 0
for (const root of roots) {
  for (const file of walk(root)) {
    scanned += 1
    const text = readFileSync(file, 'utf8')
    for (const [cust, words] of Object.entries(FORBIDDEN)) {
      for (const w of words) {
        if (text.includes(w)) hits.push(`${file}: ${cust} 문자열 "${w}"`)
      }
    }
  }
}

if (scanned === 0) {
  console.error(`훑은 파일이 0개다 — 빌드가 비었거나 경로가 틀렸다: ${roots.join(', ')}`)
  process.exit(2)
}
if (hits.length) {
  console.error(`고객 문자열이 기본 빌드에 샜다 (${hits.length}건):`)
  for (const h of hits) console.error('  ' + h)
  process.exit(1)
}
console.log(`OK — ${scanned}개 파일에 고객 문자열 0`)
