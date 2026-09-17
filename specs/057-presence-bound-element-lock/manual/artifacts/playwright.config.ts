import { defineConfig } from '@playwright/test'

// §057 매뉴얼 캡처용 self-contained 설정 (036 패턴 복제).
//
// Serial(workers:1) — **두 사람을 실제로 띄운다.** 동시편집은 혼자서는 찍을 수
// 없는 화면이고, 둘이 같은 요소를 두고 순서대로 움직여야 한다.
//
// 뷰포트를 1600×950 으로 잡는 이유: 이보다 좁으면 Inspector 와 캔버스가 한 화면에
// 안 들어와 **배너와 잠긴 입력칸을 한 장에 못 담는다.**
export default defineConfig({
  testDir: '.',
  testMatch: /playwright-057-.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 420_000, // 두 창 · 끊김 재현 구간이 길다
  reporter: 'line',
  use: {
    baseURL: process.env.APP_URL || 'http://localhost:5173',
    viewport: { width: 1600, height: 950 },
    storageState: { cookies: [], origins: [] },
    actionTimeout: 30_000,
    navigationTimeout: 60_000,
  },
})
