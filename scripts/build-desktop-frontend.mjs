/** Build the Architect host and co-locate the Analyzer federation remote. */
import { execSync } from 'node:child_process'
import { cpSync, existsSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const HOST_FRONTEND = resolve(ROOT, 'frontend')
const ANALYZER = resolve(
  process.env.ROBO_ANALYZER_FRONTEND_DIR ||
    resolve(ROOT, 'robo-analyzer', 'robo-data-frontend'),
)
const DEST = resolve(HOST_FRONTEND, 'dist', 'analyzer')
const REMOTE_URL = '/analyzer/assets/remoteEntry.js'
const ANALYZER_BASE = '/analyzer/'

function run(command, cwd, extraEnv = {}) {
  console.log(`\n[build] (${cwd}) ${command}`)
  execSync(command, { cwd, stdio: 'inherit', env: { ...process.env, ...extraEnv } })
}

function requireFile(path, action) {
  if (!existsSync(path)) {
    throw new Error(`missing ${path}\n[ACTION] ${action}`)
  }
}

requireFile(resolve(HOST_FRONTEND, 'node_modules'), `cd "${HOST_FRONTEND}" && npm ci`)
requireFile(resolve(ANALYZER, 'package.json'), 'run robo.cmd setup architect-electron')
requireFile(resolve(ANALYZER, 'node_modules'), `cd "${ANALYZER}" && npm ci`)

run('npm.cmd run build', HOST_FRONTEND, { ANALYZER_REMOTE_URL: REMOTE_URL })
run('npx.cmd vite build', ANALYZER, { ANALYZER_BASE })

const analyzerDist = resolve(ANALYZER, 'dist')
requireFile(analyzerDist, 'inspect the Analyzer frontend build log')
console.log(`\n[build] co-locate: ${analyzerDist} -> ${DEST}`)
rmSync(DEST, { recursive: true, force: true })
cpSync(analyzerDist, DEST, { recursive: true })
requireFile(resolve(DEST, 'assets', 'remoteEntry.js'), 'inspect the federation build configuration')

console.log('\n[build] complete: frontend/dist + frontend/dist/analyzer')
