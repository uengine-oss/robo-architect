// 준비는 끝났는데 아직 Claude 셀로 들어가지 않은 구현 — **화면을 넘어 사는 상태**.
//
// ## 왜 localStorage 인가
//
// 이 값이 SandboxProgressView 안의 `ref` 하나였을 때, 사용자가 Proposal 탭을 떠나면
// 컴포넌트가 언마운트되어 값이 사라졌다. 그러면 한꺼번에 셋이 없어진다:
//   · "「Claude Code 셀로 이동」을 눌러야 구현이 시작된다" 는 안내문(`v-if="pendingLaunch"`)
//   · 그 버튼이 주 버튼(primary) 자리에서 보조 버튼(outline)으로 내려앉는다
//   · Code 탭에는 애초에 **아무 안내가 없다**
//
// 2026-11-11 에 실제로 그렇게 됐다. 준비는 끝났는데(`POST …/implement` 200) 명령이
// 주입되지 않은 채 Code 탭의 **프로젝트 루트 main 셀**이 열려, claude 첫 실행 신뢰·확인
// 절차만 치르고 PRD 도 챗도 나오지 않았다. 사용자는 Proposal 탭으로 되돌아가 버튼을
// 다시 눌러야 했고, 그래야 한다는 안내는 그 시점 화면에 남아 있지 않았다.
//
// 세션 목록(`claude_code_workspace_sessions`)이 이미 같은 방식으로 산다. 여기에 두면
// Proposal 탭과 Code 탭이 **같은 것**을 본다.
//
// ## 모양
//
//   { [proposalId]: { worktreePath, command, restart } }
//
// 읽기·쓰기 모두 실패를 삼킨다 — localStorage 가 막힌 곳에서도 화면은 돌아야 하고,
// 그때는 "이번 탭에서만 기억한다" 로 전처럼 동작한다(더 나빠지지 않는다).

export const PENDING_LAUNCH_KEY = 'proposal_pending_launch'

function readAll() {
  try {
    const raw = JSON.parse(localStorage.getItem(PENDING_LAUNCH_KEY) || '{}')
    return raw && typeof raw === 'object' && !Array.isArray(raw) ? raw : {}
  } catch {
    return {}
  }
}

function writeAll(all) {
  try {
    localStorage.setItem(PENDING_LAUNCH_KEY, JSON.stringify(all))
  } catch {
    /* 저장이 막혀도 이번 탭에서는 ref 로 돈다 */
  }
}

/** 하나 읽기. `worktreePath` 가 없는 찌꺼기는 **없는 것으로 본다**. */
export function readPendingLaunch(proposalId) {
  if (!proposalId) return null
  const v = readAll()[proposalId]
  return v && v.worktreePath ? v : null
}

/** 대기 중인 것 전부 — Code 탭의 띠가 "무엇이 아직 시작되지 않았나" 를 묻는다. */
export function listPendingLaunches() {
  const all = readAll()
  return Object.keys(all)
    .filter((id) => all[id] && all[id].worktreePath)
    .map((id) => ({ proposalId: id, ...all[id] }))
}

/** 쓰기 · 지우기(`value` 가 비면 지운다). 담는 칸은 셋으로 고정한다. */
export function writePendingLaunch(proposalId, value) {
  if (!proposalId) return
  const all = readAll()
  if (value && value.worktreePath) {
    all[proposalId] = {
      worktreePath: value.worktreePath,
      command: value.command || null,
      restart: !!value.restart,
    }
  } else {
    delete all[proposalId]
  }
  writeAll(all)
}

export function clearPendingLaunch(proposalId) {
  writePendingLaunch(proposalId, null)
}
