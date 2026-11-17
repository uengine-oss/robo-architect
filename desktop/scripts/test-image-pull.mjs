#!/usr/bin/env node
// The pull path of src/main/docker-images.ts against a real registry — without touching any
// image the app's stack uses. Needs `npm run build` (reads dist/) and Docker.
//
//   node scripts/test-image-pull.mjs
//
// 1. starts a throwaway registry (registry:3, 127.0.0.1:<free port>)
// 2. builds a throwaway image (alpine + 30 MB of random bytes), pushes it, deletes it locally
// 3. ensureImages() pulls it through the engine API, pinned to the pushed digest → byte progress
// 4. again → reused; through the CLI fallback → pulled; under a new name by ID → tagged
// 5. a tag the registry does not have → docker.image_pull_failed, not retried
// then removes the registry container and the throwaway images.
import { execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const { ensureImages } = require(path.join(here, '..', 'dist', 'main', 'main', 'docker-images.js'))

const docker = (args, opts = {}) => execFileSync('docker', args, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], ...opts }).trim()
const runDocker = async (args) => docker(args)
const log = (level, event, data) => console.log(`  [${level}] ${event} ${data ? JSON.stringify(data) : ''}`)
const ok = (cond, what) => { if (!cond) throw new Error(`FAILED: ${what}`); console.log(`ok - ${what}`) }

const freePort = () => new Promise((resolve) => { const s = net.createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => resolve(p)) }) })
const port = await freePort()
const registry = `ra-pull-test-registry-${port}`
const repo = `localhost:${port}/robo-architect-lite-pulltest`
const ref = `${repo}:0.1.0`
const cleanup = []

try {
  docker(['run', '-d', '--rm', '--name', registry, '-p', `127.0.0.1:${port}:5000`, 'registry:3'])
  cleanup.push(() => docker(['rm', '-f', registry]))
  for (let i = 0; i < 50; i += 1) {
    try { execFileSync('curl', ['-fsS', `http://127.0.0.1:${port}/v2/`], { stdio: 'ignore' }); break } catch { await new Promise((r) => setTimeout(r, 200)) }
  }

  const dockerfile = `FROM alpine:3.20\nRUN head -c 31457280 /dev/urandom > /blob && echo ${Date.now()} > /stamp\n`
  docker(['build', '-q', '-t', ref, '-'], { input: dockerfile })
  cleanup.push(() => { try { docker(['image', 'rm', '-f', ref]) } catch {} })
  const id = docker(['image', 'inspect', ref, '--format', '{{.Id}}'])
  const size = Number(docker(['image', 'inspect', ref, '--format', '{{.Size}}']))
  const pushed = docker(['push', ref])
  const digest = /digest: (sha256:[a-f0-9]{64})/.exec(pushed)?.[1]
  ok(!!digest, `pushed ${ref} (id ${id.slice(0, 19)}, digest ${digest?.slice(0, 19)}, ${Math.round(size / 1e6)} MB)`)
  docker(['image', 'rm', ref])
  ok(!docker(['image', 'ls', '-q', repo]), 'the throwaway image is gone locally')

  const entry = { name: 'graphBolt', ref, id, digest, size }
  const progress = []
  const r1 = await ensureImages({ images: [entry], archive: null, pull: true, runDocker, log, onProgress: (p) => progress.push(p) })
  ok(r1.pulled.length === 1, 'pulled through the engine API')
  const bytes = progress.filter((p) => p.currentBytes > 0 && p.currentBytes < p.totalBytes)
  console.log('  progress:', progress.map((p) => `${(p.currentBytes / 1e6).toFixed(1)}/${(p.totalBytes / 1e6).toFixed(1)}MB`).join(' '))
  ok(progress.length >= 2 && progress.at(-1).currentBytes >= progress.at(-1).totalBytes, `progress reached the end (${progress.length} ticks, ${bytes.length} with partial bytes)`)
  ok(docker(['image', 'inspect', ref, '--format', '{{.Id}}']) === id, 'the pulled image has the pushed identity')

  const r2 = await ensureImages({ images: [entry], archive: null, pull: true, runDocker, log })
  ok(r2.reused.length === 1 && r2.pulled.length === 0, 'second run reuses it')

  docker(['image', 'rm', ref])
  const r3 = await ensureImages({ images: [{ ...entry, digest: undefined }], archive: null, pull: true, runDocker, log, engineSocket: null })
  ok(r3.pulled.length === 1, 'pulled through the docker CLI fallback (by tag)')

  const alias = `${repo}:alias`
  cleanup.push(() => { try { docker(['image', 'rm', alias]) } catch {} })
  const r4 = await ensureImages({ images: [{ ...entry, ref: alias }], archive: null, pull: true, runDocker, log })
  ok(r4.tagged.length === 1, 'found by ID under another name → tagged, no download')

  let failure = ''
  try {
    await ensureImages({ images: [{ ...entry, ref: `${repo}:nope`, id: `sha256:${'0'.repeat(64)}`, digest: undefined }], archive: null, pull: true, runDocker, log })
  } catch (err) { failure = err.message }
  ok(/docker\.image_pull_failed/.test(failure), `a missing tag fails clearly: ${failure.slice(0, 140)}`)
  console.log('\nall pull checks passed')
} finally {
  for (const fn of cleanup.reverse()) { try { fn() } catch {} }
}
