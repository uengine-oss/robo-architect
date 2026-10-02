<script setup>
/**
 * 프로젝트 때문에 막혔을 때의 안내 한 줄.
 *
 * **왜 있어야 하나.** 프로젝트가 하나도 없는 사용자는 화면마다 403 을 받는다.
 * 백엔드는 정확히 "프로젝트를 먼저 고르세요"라고 답하는데, 그 말이 콘솔에만
 * 남고 화면에는 빈 패널과 "서버 연결 실패"가 보였다 — 멀쩡한 서버를 의심하게
 * 만든다. 여기가 그 답을 사람에게 보여 주는 자리다.
 *
 * 상태는 스토어가 아니라 **인터셉터가 적는다**(`app/http.js`). 화면마다 403 을
 * 따로 해석하면 한 곳만 빠져도 그 화면은 다시 거짓말을 한다.
 *
 * **같은 질문의 다른 답도 여기서 한다.** 중앙 DB 에서 이 PC 의 `AUTH_ROLE_SECRET` 이
 * 서버와 다르면 읽기 등급 사용자의 조회가 전부 막히는데, 사람이 묻는 것은 똑같다 —
 * "왜 아무것도 안 보이나". 배너를 하나 더 만드는 대신 이 자리에서 답한다.
 * 설치가 잘못된 것이 더 큰 사실이므로 **그쪽을 먼저** 보여 준다.
 */
import { computed } from 'vue'
import { useAuthStore } from '@/features/auth/auth.store.js'

const auth = useAuthStore()

const notSelected = computed(() => auth.projectError === 'PROJECT_NOT_SELECTED')
/** 이 PC 의 설정 때문에 막힌 것. 프로젝트 안내보다 **앞선다.** */
const graphFault = computed(() => auth.graphError)
const show = computed(() => !!auth.graphError || !!auth.projectError)

// 사람에게는 **지금 할 일**만 말한다. 상태 코드도, 서버 사정도 화면의 몫이 아니다.
const text = computed(() => {
  if (graphFault.value) return '이 PC 의 설정이 중앙 DB 서버와 다릅니다.'
  return notSelected.value ? '프로젝트를 선택해 주세요.' : '이 프로젝트를 볼 수 없습니다.'
})
// 설치 문제는 **백엔드가 보낸 말을 그대로** 쓴다. 화면이 고쳐 쓰면 둘이 어긋난다.
const how = computed(() => {
  if (graphFault.value) return graphFault.value.detail
  return notSelected.value
    ? '위쪽 프로젝트 메뉴에서 고르거나 새로 만들 수 있습니다.'
    : '담당자에게 공유를 요청하거나 다른 프로젝트를 선택해 주세요.'
})

</script>

<template>
  <div v-if="show" class="pgate" :class="{ 'pgate--fault': graphFault }">
    <span class="pgate__text">{{ text }}</span>
    <span class="pgate__how">{{ how }}</span>
  </div>
</template>

<style scoped>
.pgate {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: #fff8e1;
  border-bottom: 1px solid #ffe082;
  color: #6d4c00;
  font-size: 12px;
}
/* 설치가 잘못된 것은 고를 것이 없는 상태와 **색으로도** 달라야 한다. */
.pgate--fault {
  background: #fdecea;
  border-bottom-color: #f5c6c2;
  color: #7f231c;
}
.pgate__text { font-weight: 600; }
.pgate__how { opacity: 0.8; }
</style>
