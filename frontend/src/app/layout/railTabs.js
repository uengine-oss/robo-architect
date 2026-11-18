// 왼쪽 레일 클릭을 **새 탭으로 열지** 정한다 (라이트 지적 C-1 ④).
//
// ## 누가 새 탭을 쓰나
//
// 데스크톱 **lite** 프로필만이다 — 창 하나에 탭 줄(main/tabs.ts)이 있다.
//   - 웹 판(포스코 등): `window.desktop` 이 없다 → 지금처럼 제자리 전환
//   - enterprise 프로필: preload 는 같아서 `window.raShell` 이 **있다**. 그런데 탭 창이 아니라
//     main 이 `shell:tabs:open` 처리기를 아예 안 단다(wireShellIpc 는 lite 에서만) — 그래서
//     `raShell.openTab` 이 있다는 것만으로 가르면 enterprise 에서 누른 것이 **조용히 사라진다.**
//     판정은 main 이 정한 프로필(`getRuntimeState().desktopProfile`)로 한다(LauncherView 와 같은 근거).
//
// ## 규칙
//
//   - 기본: `openTab({ view, reuse: true })` — 같은 화면 탭이 있으면 그 탭으로 간다(탭이 안 불어난다)
//   - Ctrl/⌘-클릭: 제자리 전환(한 창에서 보고 싶을 때)
//   - 지금 보고 있는 화면을 또 누르면: 아무 데도 안 간다(제자리)
//   - 탭 줄이 모르는 화면(템플릿 등): 제자리 — tabs.ts 의 VIEWS 에 없는 화면은 탭이 기본 화면으로 열린다

/** desktop/src/main/tabs.ts 의 VIEWS 와 같은 목록. 여기 없는 화면은 제자리로 연다. */
export const SHELL_TAB_VIEWS = new Set(['Proposals', 'Stories', 'Process', 'Design', 'Data', 'Code', 'Legacy'])

let detecting = null

/** 이 창이 lite 탭 창 안인가. 한 번만 묻는다. 모르면 `false`(= 지금 동작). */
export function detectShellTabs(win = typeof window !== 'undefined' ? window : undefined) {
  if (detecting) return detecting
  detecting = (async () => {
    if (!win?.raShell?.openTab || !win?.desktop?.app?.getRuntimeState) return false
    try {
      const r = await win.desktop.app.getRuntimeState()
      const state = r && 'ok' in r ? (r.ok ? r.data : null) : r
      return state?.desktopProfile === 'lite'
    } catch {
      return false
    }
  })()
  return detecting
}

/** 검사용 — 감지 결과를 잊는다. */
export function _resetShellTabsDetection() {
  detecting = null
}

/**
 * 레일 클릭 → 열 탭. `null` 이면 제자리 전환(지금 동작).
 *
 * @param {{ tab: string, current: boolean, shellTabs: boolean, inPlace?: boolean }} input
 *   current — 지금 이 탭이 보이는 화면인가 · inPlace — Ctrl/⌘ 가 눌렸는가
 */
export function railTabTarget({ tab, current, shellTabs, inPlace = false }) {
  if (!shellTabs || inPlace || current) return null
  if (!SHELL_TAB_VIEWS.has(tab)) return null
  return { view: tab, reuse: true }
}

/** 클릭 이벤트에서 "제자리" 수식키를 읽는다 — Windows/Linux 는 Ctrl, macOS 는 ⌘. */
export const wantsInPlace = (event) => !!(event && (event.ctrlKey || event.metaKey))
