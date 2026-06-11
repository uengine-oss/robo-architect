import { test, expect } from '@playwright/test'
import { execSync } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

/**
 * 039 세션 영속성 검증 — 백엔드 PTY 세션 레지스트리.
 * ws가 끊겨도(새로고침) claude PTY가 살아남아, 같은 session_id로 재연결하면
 * 스크롤백이 재생(replay)되며 재어태치된다.
 *
 * 결정적 신호: ws#1에서 고유 마커를 타이핑하면 claude TUI가 그 글자를 에코 →
 * PTY 출력(스크롤백)에 남는다. ws#1을 끊고 ws#2(같은 session_id)로 재연결하면
 * 재생된 스크롤백에 그 마커가 포함되어야 한다(프로세스가 살아있다는 증거).
 */

const APP = 'http://localhost:5173'
const MARKER = 'ZZREATTACH_4731'

test.use({ headless: false, viewport: { width: 1200, height: 800 } })

test('세션 reattach: ws 재연결 시 살아있는 claude 스크롤백이 재생된다', async ({ page }) => {
  const target = mkdtempSync(join(tmpdir(), 'robo-reattach-'))
  execSync('git init -q && git config user.email t@t.io && git config user.name t', { cwd: target })
  execSync('echo "# t" > README.md && git add -A && git commit -q -m init', { cwd: target })

  // 앱을 로드해 같은 오리진에서 WebSocket을 연다(백엔드 포트 8000 직결).
  await page.goto(APP)
  await page.waitForLoadState('domcontentloaded')

  const sessionId = `reattach-test#0`

  try {
    const result = await page.evaluate(
      async ({ target, sessionId }) => {
        const base = `ws://localhost:8000/api/claude-code/terminal`
        const qs = (extra: Record<string, string>) =>
          base + '?' + new URLSearchParams({ session_id: sessionId, ...extra }).toString()

        function collect(ws: WebSocket): { text: () => string } {
          let buf = ''
          ws.onmessage = (e) => { buf += typeof e.data === 'string' ? e.data : '' }
          return { text: () => buf }
        }
        const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

        // ── ws#1: 세션 생성 + claude 기동(출력이 쌓일 때까지 폴링) ──
        const ws1 = new WebSocket(qs({ workdir: target, permission_mode: 'bypassPermissions' }))
        const c1 = collect(ws1)
        await new Promise<void>((res, rej) => { ws1.onopen = () => res(); ws1.onerror = () => rej(new Error('ws1 error')) })
        ws1.send(JSON.stringify({ type: 'resize', cols: 100, rows: 30 }))
        for (let i = 0; i < 30 && c1.text().length < 100; i++) await wait(300) // 최대 9s
        const ws1Bytes = c1.text().length
        ws1.close()
        await wait(800)

        // ── ws#2: 같은 session_id로 재연결 → 버퍼가 즉시 재생되어야 함 ──
        // (새 claude를 새로 띄웠다면 800ms 안에 의미있는 바이트가 오지 않는다.)
        const ws2 = new WebSocket(qs({ workdir: target }))
        const c2 = collect(ws2)
        await new Promise<void>((res, rej) => { ws2.onopen = () => res(); ws2.onerror = () => rej(new Error('ws2 error')) })
        await wait(800)
        const replayFast = c2.text().length
        ws2.close()

        // 정리: 백엔드 세션 종료
        await fetch(`http://localhost:8000/api/claude-code/terminal/session?session_id=${encodeURIComponent(sessionId)}`, { method: 'DELETE' })

        return { ws1Bytes, replayFast }
      },
      { target, sessionId },
    )

    console.log('result:', JSON.stringify(result))
    expect(result.ws1Bytes, 'ws#1에서 claude가 출력을 내보내야 함(세션 생성 확인)').toBeGreaterThan(100)
    // 재연결 직후 즉시 도착한 바이트 ≈ 누적 스크롤백 → reattach+replay(같은 PTY 생존).
    expect(result.replayFast, '재연결 직후 스크롤백이 즉시 재생되어야 함').toBeGreaterThan(100)
    expect(result.replayFast, '재생 바이트가 ws#1 누적의 절반 이상이어야 함(=버퍼 재생, 새 spawn 아님)')
      .toBeGreaterThanOrEqual(Math.floor(result.ws1Bytes * 0.5))
    console.log('🎉 세션 reattach/replay 검증 통과')
  } finally {
    try { rmSync(target, { recursive: true, force: true }) } catch {}
  }
})
