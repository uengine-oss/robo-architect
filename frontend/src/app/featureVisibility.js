/**
 * 화면에서 **감추는 것**을 한 자리에 모은다.
 *
 * 왜 한 자리인가. `TopBar.vue` 가 사내망 배포에서 'Proposals' 와 'Code' 탭을
 * 뺐는데(2026-09-29), 그 탭이 꺼지면서 **딸려서 뜻을 잃는 진입점들**이 화면에
 * 남아 있었다. 그것들이 네 파일에 흩어져 있어서, 판단을 각자 베껴 두면
 * **한 곳만 되살리는 날**이 온다.
 *
 * ⚠ **컴포넌트·라우팅·API 는 그대로 둔다.** 여기서는 보일지 말지만 정한다 —
 * `TopBar.vue` 가 탭을 숨긴 방식과 같다. 되살릴 때는 아래 값을 바꾼다.
 */

/**
 * Proposal 생애주기(spec 039~042)를 화면에 내보이나.
 *
 * `false` 인 까닭: Proposals 는 worktree 안에서 Claude Code 셀(PTY)로 구현을
 * 돌리는데 **사내망에는 `claude` CLI 가 없다**. 열어 두면 눌렀을 때 아무 일도
 * 일어나지 않는 화면이 된다. `TopBar.vue` 의 `tabs` 와 **같은 뜻**이고, 그쪽을
 * 되살릴 때 여기도 함께 되살린다.
 */
export const PROPOSALS_VISIBLE = false

/**
 * 프로젝트/BC **헌장(Constitution)** 진입점을 내보이나.
 *
 * 헌장은 spec 041 이 **Proposal 의 Plan 단계를 위해** 들인 것이다. 쓰는 쪽을
 * 코드에서 확인했다 — 헌장 노드를 읽는 것은 `api/features/proposal_lifecycle`
 * **하나뿐**이다(`plan_runner` · `constitution_runner` · `stage_runners/*`).
 * 즉 Proposals 가 꺼져 있으면 헌장을 고쳐도 **아무도 읽지 않는다.**
 *
 * 그런 화면을 열어 두면 사용자가 "이게 무슨 뜻이지" 를 묻게 되고(2026-10-23 에
 * 실제로 물었다), 공들여 채운 값이 아무 데도 안 쓰인다. 그래서 **Proposals 를
 * 따라간다.**
 *
 * ⚠ 백엔드(`api/features/constitution`)와 모달은 **그대로 남는다.** 나중에
 * 헌장을 Proposal 밖에서도 쓰게 되면 이 값을 `true` 로 되돌리거나,
 * `PROPOSALS_VISIBLE` 에서 떼어 따로 정하면 된다.
 */
export const CONSTITUTION_VISIBLE = PROPOSALS_VISIBLE
