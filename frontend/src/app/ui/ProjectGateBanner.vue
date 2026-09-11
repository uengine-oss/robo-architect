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
 */
import { computed } from 'vue'
import { useAuthStore } from '@/features/auth/auth.store.js'

const auth = useAuthStore()

const notSelected = computed(() => auth.projectError === 'PROJECT_NOT_SELECTED')
const show = computed(() => !!auth.projectError)

// 사람에게는 **지금 할 일**만 말한다. 상태 코드도, 서버 사정도 화면의 몫이 아니다.
const text = computed(() =>
  notSelected.value
    ? '프로젝트를 선택해 주세요.'
    : '이 프로젝트를 볼 수 없습니다.',
)
const how = computed(() =>
  notSelected.value
    ? '위쪽 프로젝트 메뉴에서 고르거나 새로 만들 수 있습니다.'
    : '담당자에게 공유를 요청하거나 다른 프로젝트를 선택해 주세요.',
)

</script>

<template>
  <div v-if="show" class="pgate">
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
.pgate__text { font-weight: 600; }
.pgate__how { opacity: 0.8; }
</style>
