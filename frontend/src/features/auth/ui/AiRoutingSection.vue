<script setup>
/**
 * AI 호출 경로 — 갈래마다 AI 호출이 **어디로 나가는지** 한 줄씩.
 *
 * 목적: 현장 관리자가 서버 로그 없이 "P-GPT 로 가고 있나" 를 확인한다. 초록만 보여주면
 * 있으나 마나다 — 게이트웨이를 안 지나는 갈래를 이름으로 부르는 것이 핵심이다.
 *
 * 2026-11-18 정리: 예전엔 줄마다 환경변수 이름·내부 설계 메모를 펼쳐 두었다. 그것은
 * 고객 관리자가 고칠 수 없는 서버 설정이라 **「자세히」 안으로** 접었다. 판에 없는 갈래
 * (포스코 웹의 pdf2bpmn · 서버 판의 Claude Code)는 감춘다. 틀린 줄도 바로잡았다
 * (`api/platform/ai_gateway.py` 의 `shipped`).
 *
 * 값은 `GET /api/auth/provider` 의 `aiGateway` 다. 비밀값은 담기지 않는다.
 */
import { computed } from 'vue'
import { useAuthStore } from '@/features/auth/auth.store.js'
import { customer } from '@/app/customer.js'
import { visiblePaths, destinationLabel, STATUS_LABEL } from '../aiRouting.js'

const auth = useAuthStore()

// 게이트웨이를 화면에서 부르는 이름 — 고객 확장 값(`ai.gatewayName`).
const gatewayName = customer.ai.gatewayName

// 서버 판(web)은 VITE_DISABLE_CLAUDE_TERMINAL=1 로 굽는다 — Claude Code 갈래가 없다.
// 서버는 화면이 어떻게 구워졌는지 모르므로(shipped=null) 여기서 정한다.
const claudeAvailable = import.meta.env.VITE_DISABLE_CLAUDE_TERMINAL !== '1'

const state = computed(() => (auth.provider || {}).aiGateway || null)
const paths = computed(() => visiblePaths(state.value, { claudeAvailable }))
const blockedCount = computed(() => ((state.value || {}).blocked || []).length)

// 옛 백엔드에 붙으면 이 값이 없다. 빈 칸을 초록으로 그리면 안 옮긴 것을
// 옮겼다고 읽는다 — 아예 안 그린다.
const available = computed(() => !!state.value)

const STATUS = STATUS_LABEL
const destination = (p) => destinationLabel(p, gatewayName)
</script>

<template>
  <div v-if="available" class="settings-section air">
    <div class="settings-section__header">
      <h3 class="settings-section__title">AI 호출 경로</h3>
      <span class="settings-section__description">
        {{ gatewayName }} {{ state.enabled ? '켜짐' : '꺼짐' }}
      </span>
    </div>

    <table class="air__table">
      <thead>
        <tr><th>갈래</th><th>어디로</th><th>상태</th></tr>
      </thead>
      <tbody>
        <tr v-for="p in paths" :key="p.id" :class="`air__row--${p.status}`" :data-path="p.id">
          <td class="air__name">{{ p.label }}</td>
          <td>{{ destination(p) }}</td>
          <td><span class="air__badge">{{ STATUS[p.status] || p.status }}</span></td>
        </tr>
      </tbody>
    </table>

    <p v-if="blockedCount" class="air__blocked">
      {{ blockedCount }}개 갈래는 설정으로 못 옮깁니다 — 사내망 납품에서 별도 작업이 필요합니다.
    </p>

    <!-- 운영자용 — 주소 · 덮은 설정 · 환경변수. 고객 관리자가 고칠 수 있는 값이 아니어서 접어 둔다. -->
    <details class="air__more">
      <summary>자세히 (운영자용)</summary>
      <p class="air__line">
        <template v-if="state.enabled">게이트웨이 주소: {{ state.baseUrl }}</template>
        <template v-else>게이트웨이를 켜려면 서버 <code>.env</code> 에 <code>PGPT_BASE_URL</code> · <code>PGPT_API_KEY</code> 를 지정합니다.</template>
      </p>
      <!-- 덮은 것을 숨기면 "왜 안 바뀌지"를 못 푼다. -->
      <p v-if="state.overrides && state.overrides.length" class="air__line">
        {{ gatewayName }} 가 {{ state.overrides.join(' · ') }} 를 덮었습니다.
      </p>
      <ul class="air__notes">
        <li v-for="p in paths" :key="p.id">
          <b>{{ p.label }}</b>
          <span v-if="p.target" class="air__target"> — {{ p.target }}</span>
          <div v-if="p.note" class="air__why">{{ p.note }}</div>
        </li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.air__table { width: 100%; margin-top: 10px; border-collapse: separate; border-spacing: 0 4px; font-size: 12px; }
.air__table th { text-align: left; font-weight: 500; font-size: 11px; opacity: 0.6; padding: 0 8px; }
.air__table td { padding: 6px 8px; background: var(--surface-2, rgba(127, 127, 127, 0.08)); }
.air__table td:first-child { border-radius: 6px 0 0 6px; }
.air__table td:last-child { border-radius: 0 6px 6px 0; width: 84px; }
.air__name { font-weight: 600; }
.air__badge {
  display: inline-block;
  min-width: 60px;
  font-size: 10px;
  text-align: center;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(127, 127, 127, 0.18);
}
/* 게이트웨이를 못 지나는 갈래가 눈에 띄어야 한다 — 이 화면의 목적이 그것이다. */
.air__row--unroutable .air__badge { background: rgba(220, 80, 60, 0.22); }
.air__row--routed .air__badge { background: rgba(60, 160, 100, 0.22); }
.air__blocked { margin: 8px 0 0; font-size: 11px; color: rgb(200, 90, 70); }
.air__more { margin-top: 10px; font-size: 11px; }
.air__more summary { cursor: pointer; opacity: 0.7; }
.air__line { margin: 6px 0 0; opacity: 0.8; word-break: break-all; }
.air__notes { list-style: none; margin: 6px 0 0; padding: 0; display: grid; gap: 6px; }
.air__target { opacity: 0.7; word-break: break-all; }
.air__why { opacity: 0.6; line-height: 1.45; margin-top: 2px; }
</style>
