/**
 * 화면에서 **감추는 것**을 한 자리에 모은다.
 *
 * 왜 한 자리인가. `TopBar.vue` 가 사내망 배포에서 'Proposals' 와 'Code' 탭을
 * 뺐는데(2026-09-29), 그 탭이 꺼지면서 **딸려서 뜻을 잃는 진입점들**이 화면에
 * 남아 있었다. 그것들이 네 파일에 흩어져 있어서, 판단을 각자 베껴 두면
 * **한 곳만 되살리는 날**이 온다.
 *
 * ⚠ **컴포넌트·라우팅·API 는 그대로 둔다.** 여기서는 보일지 말지만 정한다 —
 * `TopBar.vue` 가 탭을 숨긴 방식과 같다.
 *
 * 값은 **고객 확장**(`customer.features`)에서 온다 — 고객이 감추면 여기가 `false` 가 된다.
 * 기본 빌드(`VITE_CUSTOMER=default`)는 둘 다 보인다. export 이름은 쓰는 곳을 안 바꾸도록
 * 그대로 둔다.
 */
import { ref, computed } from 'vue'
import { customer } from './customer.js'

/**
 * Proposal 생애주기(spec 039~042)를 화면에 내보이나.
 *
 * 고객이 `false` 로 두는 까닭(예: 사내망 배포): Proposals 는 worktree 안에서 Claude Code 셀(PTY)로 구현을
 * 돌리는데 **사내망에는 `claude` CLI 가 없다**. 열어 두면 눌렀을 때 아무 일도
 * 일어나지 않는 화면이 된다. `TopBar.vue` 의 `tabs` 와 **같은 뜻**이고, 그쪽을
 * 되살릴 때 여기도 함께 되살린다.
 */
export const PROPOSALS_VISIBLE = customer.features.proposals !== false

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
 * ⚠ 백엔드(`api/features/constitution`)와 모달은 **그대로 남는다.** 따라가는 규칙은
 * `customer.js` 가 정한다(`features.constitution` 이 null 이면 proposals 를 따른다) —
 * 확장이 `features.constitution` 을 따로 적으면 그 값이 이긴다.
 */
export const CONSTITUTION_VISIBLE = customer.features.constitution !== false

// ── 서버가 정하는 것 (망마다 다름) ─────────────────────────────────────────────

/**
 * Figma 연동을 내보이나 — **서버 `.env`**(`ROBO_FIGMA_ENABLED`)가 정한다(2026-11-24).
 *
 * 위 둘(빌드 때 고객 확장)과 달리 런타임 값이다. 같은 포스코 이미지라도 사내 서버에 https 가 생기면
 * 다시 켤 수 있어야 해서다. 포스코 확장은 서버 기본값을 꺼 둔다 — 사내 서버가 http 라 Figma 앱이
 * 플러그인 연결을 막는다. 꺼지면 Figma 진입점(레일 단추 · 연동 창 · 생성 방식의 Figma 선택지 ·
 * 인스펙터의 Figma 단추 · 요구사항 가져오기의 Figma 탭)을 모두 숨기고, 화면 생성은 HTML 와이어프레임만 쓴다.
 *
 * 모르는 동안(null)은 **숨긴다** — 꺼진 망에서 잠깐 보였다 사라지면 안 된다. 서버가 이 값을 모르는
 * 옛 판(404)이면 지금처럼 보인다.
 */
const figmaFlag = ref(null)
export const FIGMA_VISIBLE = computed(() => figmaFlag.value === true)
/** 서버가 **꺼졌다고 답한** 뒤에만 참 — 저장된 선택을 HTML 로 바꾸는 일은 이걸로(모르는 동안 덮어쓰지 않게) */
export const FIGMA_OFF = computed(() => figmaFlag.value === false)

let featuresLoading = null
export function loadServerFeatures() {
  if (featuresLoading) return featuresLoading
  featuresLoading = (async () => {
    try {
      const r = await fetch('/api/features')
      if (r.status === 404) { figmaFlag.value = true; return }
      if (!r.ok) throw new Error(String(r.status))
      const body = await r.json()
      figmaFlag.value = body.figma !== false
    } catch {
      featuresLoading = null   // 서버에 못 닿았다 — 다음에 다시 읽는다. 그동안은 숨긴 채로 둔다.
    }
  })()
  return featuresLoading
}
