/**
 * build-desktop-frontend.mjs — Electron 배포용 프론트엔드 빌드 (Module Federation co-locate)
 *
 * 모범사례: 배포본은 analyzer remote 를 별도 서버(5001) 없이 자급해야 한다.
 * 그래서 analyzer(robo-data-frontend 서브모듈)를 빌드해 host 의 dist 안에 함께 둔다.
 *
 *   1) host(robo-architect/frontend) 빌드  — remote URL = 'analyzer/assets/remoteEntry.js'(상대)
 *   2) analyzer(서브모듈) 빌드            — base = '/analyzer/' (청크가 app://app/analyzer/ 로 해석)
 *   3) analyzer/dist → host frontend/dist/analyzer/ 복사
 *
 * 결과: Electron 이 app://app/ 로 host 를, app://app/analyzer/ 로 remote 를 서빙 → 자급.
 * 개발 모드에선 이 스크립트 불필요(analyzer 를 5001 로 preview, host 는 기본 localhost:5001 사용).
 *
 * 실행:  node scripts/build-desktop-frontend.mjs   (robo-architect 루트에서)
 *        이후  cd desktop && npm run dist           (electron-builder 패키징)
 */
import { execSync } from 'node:child_process'
import { cpSync, existsSync, rmSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const HOST_FRONTEND = resolve(ROOT, 'frontend')
const ANALYZER = resolve(ROOT, 'robo-analyzer', 'robo-data-frontend')
const DEST = resolve(HOST_FRONTEND, 'dist', 'analyzer')

const REMOTE_URL = '/analyzer/assets/remoteEntry.js' // host 가 절대경로로 로드(app://app/analyzer/). 앞의 '/' 없으면 브라우저가 bare module specifier 로 보고 거부('Failed to resolve module specifier')
const ANALYZER_BASE = '/analyzer/'                  // analyzer 청크의 publicPath

function run(cmd, cwd, extraEnv = {}) {
  console.log(`\n[build] (${cwd}) ${cmd}`)
  execSync(cmd, { cwd, stdio: 'inherit', env: { ...process.env, ...extraEnv } })
}

if (!existsSync(resolve(ANALYZER, 'package.json'))) {
  console.error(
    `[build] analyzer 서브모듈이 없습니다: ${ANALYZER}\n` +
    `        먼저 실행: git submodule update --init --recursive`,
  )
  process.exit(1)
}

// 1) host 프론트 빌드 (remote URL 을 상대경로로 주입)
run('npm run build', HOST_FRONTEND, { ANALYZER_REMOTE_URL: REMOTE_URL })

// 2) analyzer 빌드 (base 를 /analyzer/ 로 주입)
//    host 와 동일하게 vite build 를 직접 호출(타입체크 게이트 vue-tsc 제외).
//    프로젝트의 host build·analyzer build:docker 모두 vite-only 라 이게 표준 배포 경로.
run('npm ci', ANALYZER)
run('npx vite build', ANALYZER, { ANALYZER_BASE })

// 3) analyzer dist 를 host dist 안으로 co-locate
console.log(`\n[build] co-locate: ${resolve(ANALYZER, 'dist')} → ${DEST}`)
if (existsSync(DEST)) rmSync(DEST, { recursive: true, force: true })
cpSync(resolve(ANALYZER, 'dist'), DEST, { recursive: true })

console.log(
  `\n[build] 완료 ✅  frontend/dist (host) + frontend/dist/analyzer (remote)\n` +
  `        다음:  cd desktop && npm run dist`,
)
