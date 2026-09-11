<script setup>
/**
 * AI 호출 경로 진단 — P-GPT 로 무엇이 옮겨졌고 무엇이 안 옮겨졌나.
 *
 * **여섯 갈래인데 설정 이름이 갈래마다 달랐다.** 그래서 "P-GPT 로 돌렸다"고
 * 말할 수 있는 자리가 없었다 — 어떤 갈래는 옮겨졌고 어떤 갈래는 여전히 밖으로
 * 나가는데 화면에도 로그에도 그 구분이 안 보였다.
 *
 * 여기가 그 자리다. 초록만 보여주면 이 화면은 있으나 마나다 — **안 옮겨진
 * 갈래를 이름으로 부르는 것**이 목적이다. 사내망 납품에서는 그쪽이 차단
 * 항목이다(pdf2bpmn 이 외부 SaaS 라 문서 업로드가 막힌다).
 *
 * 값은 `GET /api/auth/provider` 의 `aiGateway` 다. 비밀값은 담기지 않는다.
 */
import { computed } from 'vue'
import { useAuthStore } from '@/features/auth/auth.store.js'

const auth = useAuthStore()

const state = computed(() => (auth.provider || {}).aiGateway || null)
const paths = computed(() => (state.value || {}).paths || [])
const blockedCount = computed(() => ((state.value || {}).blocked || []).length)

// 옛 백엔드에 붙으면 이 값이 없다. 빈 칸을 초록으로 그리면 안 옮긴 것을
// 옮겼다고 읽는다 — 아예 안 그린다.
const available = computed(() => !!state.value)

const LABEL = {
  routed: '게이트웨이',
  default: '기본값',
  'config-only': '별도 설정',
  unroutable: '못 옮김',
}
</script>

<template>
  <div v-if="available" class="settings-section air">
    <div class="settings-section__header">
      <h3 class="settings-section__title">AI 호출 경로</h3>
      <span class="settings-section__description">
        <template v-if="state.enabled">
          P-GPT 켜짐 — {{ state.baseUrl }}
        </template>
        <template v-else>
          P-GPT 꺼짐 — PGPT_BASE_URL 을 지정하면 채팅이 게이트웨이로 갑니다
        </template>
      </span>
    </div>

    <!-- 덮은 것을 숨기면 "왜 안 바뀌지"를 못 푼다. -->
    <p v-if="state.overrides && state.overrides.length" class="air__note">
      P-GPT 가 {{ state.overrides.join(' · ') }} 를 덮었습니다.
    </p>

    <ul class="air__list">
      <li v-for="p in paths" :key="p.id" class="air__row" :class="`air__row--${p.status}`">
        <span class="air__badge">{{ LABEL[p.status] || p.status }}</span>
        <span class="air__name">{{ p.label }}</span>
        <span class="air__target">{{ p.target || '—' }}</span>
        <span v-if="p.note" class="air__why">{{ p.note }}</span>
      </li>
    </ul>

    <p v-if="blockedCount" class="air__blocked">
      {{ blockedCount }}개 갈래는 설정으로 못 옮깁니다 — 사내망 납품에서 별도 작업이 필요합니다.
    </p>
  </div>
</template>

<style scoped>
.air__list { list-style: none; margin: 10px 0 0; padding: 0; display: grid; gap: 6px; }
.air__row {
  display: grid;
  grid-template-columns: 72px 128px 1fr;
  gap: 8px;
  align-items: baseline;
  font-size: 12px;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--surface-2, rgba(127, 127, 127, 0.08));
}
.air__badge {
  font-size: 10px;
  text-align: center;
  padding: 2px 0;
  border-radius: 999px;
  background: rgba(127, 127, 127, 0.18);
}
/* 못 옮긴 갈래가 눈에 띄어야 한다 — 이 화면의 목적이 그것이다. */
.air__row--unroutable .air__badge { background: rgba(220, 80, 60, 0.22); }
.air__row--routed .air__badge { background: rgba(60, 160, 100, 0.22); }
.air__name { font-weight: 600; }
.air__target { opacity: 0.75; word-break: break-all; }
.air__why { grid-column: 2 / -1; opacity: 0.6; font-size: 11px; line-height: 1.45; }
.air__note, .air__blocked { margin: 8px 0 0; font-size: 11px; opacity: 0.8; }
.air__blocked { color: rgb(200, 90, 70); }
</style>
