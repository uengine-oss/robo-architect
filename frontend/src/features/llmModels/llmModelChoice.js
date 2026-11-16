/**
 * 사용자가 고른 생성 모델 — **사람마다** 자기 것을 고른다(2026-11-16 결정).
 *
 * 브라우저에 사번(uid)별로 둔다: `robo.llm.model:<uid>`. 같은 PC 를 다른 사람이 써도 섞이지 않는다.
 * 요청마다 `X-LLM-Model` 헤더로 실린다(`app/http.js`). 서버는 P-GPT `/models` 목록에 있는 이름만
 * 받고, 아니면 기본값(compose 의 LLM_MODEL)으로 돈다 — 여기서 잘못 골라도 생성이 깨지지 않는다.
 * 빈 값 = 기본값.
 */
import { ref } from 'vue'

const PREFIX = 'robo.llm.model:'
const chosen = ref('')
let loadedFor = null

function keyFor(uid) {
  return PREFIX + (uid || 'anonymous')
}

/** 지금 사용자의 선택을 읽어 둔다(사용자가 바뀌면 다시 읽는다). */
export function loadChoice(uid) {
  if (loadedFor === uid) return chosen.value
  loadedFor = uid
  try {
    chosen.value = window.localStorage.getItem(keyFor(uid)) || ''
  } catch {
    chosen.value = ''
  }
  return chosen.value
}

export function saveChoice(uid, model) {
  const value = (model || '').trim()
  chosen.value = value
  loadedFor = uid
  try {
    if (value) window.localStorage.setItem(keyFor(uid), value)
    else window.localStorage.removeItem(keyFor(uid))
  } catch {
    /* 저장이 막힌 환경 — 이번 창에서만 쓴다 */
  }
}

/** 헤더에 실을 값. 빈 문자열이면 싣지 않는다. */
export function currentChoice(uid) {
  return loadChoice(uid)
}

export const llmModelChoice = chosen
