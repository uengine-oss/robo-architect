<script setup>
/**
 * 파일·폴더 아이콘.
 *
 * 기준 구현(local-msaez CodeGenerator)은 Vuetify 의 MDI 를 쓴다
 * (`mdi-language-java`·`mdi-xml`·`mdi-folder-open` …). 우리는 Vuetify 도 MDI 도
 * 쓰지 않으므로 같은 구분을 인라인으로 그린다. 폰트·아이콘 패키지에 기대지
 * 않아 오프라인 납품에서도 그대로 뜬다.
 *
 * 폴더 모양은 Code 탭의 FileTreePane 과 같은 path 다 — 두 트리가 다르게
 * 보이면 같은 앱으로 읽히지 않는다.
 */
import { computed } from 'vue'

const props = defineProps({
  name: { type: String, default: '' },
  dir: { type: Boolean, default: false },
  open: { type: Boolean, default: false },
})

// 확장자 → 배지 글자와 색. 기준 구현의 아이콘 구분을 그대로 옮겼다.
const BADGES = {
  java: ['J', 'var(--ccw-orange)'],
  xml: ['X', 'var(--ccw-red)'],
  html: ['H', 'var(--ccw-red)'],
  json: ['{}', 'var(--ccw-yellow)'],
  yml: ['Y', 'var(--ccw-teal)'],
  yaml: ['Y', 'var(--ccw-teal)'],
  properties: ['P', 'var(--ccw-text-muted)'],
  md: ['MD', 'var(--ccw-accent)'],
  markdown: ['MD', 'var(--ccw-accent)'],
  txt: ['T', 'var(--ccw-text-dim)'],
  js: ['JS', 'var(--ccw-yellow)'],
  ts: ['TS', 'var(--ccw-accent)'],
  vue: ['V', 'var(--ccw-green)'],
  py: ['PY', 'var(--ccw-cyan)'],
  sql: ['S', 'var(--ccw-purple)'],
  sh: ['$', 'var(--ccw-green)'],
}

const badge = computed(() => {
  const ext = (props.name.split('.').pop() || '').toLowerCase()
  return BADGES[ext] || ['·', 'var(--ccw-text-dim)']
})

// 열린 폴더와 닫힌 폴더의 실루엣이 달라야 접힘 상태가 한눈에 보인다.
const folderPath = computed(() =>
  props.open
    ? 'M1.5 4.5 V12 a1 1 0 0 0 1 1 H13 a1 1 0 0 0 1-1 V6 a1 1 0 0 0-1-1 H7.5 L6 3.5 H2.5 a1 1 0 0 0-1 1 Z'
    : 'M1.5 4.5 a1 1 0 0 1 1-1 H6 L7.5 5 H13 a1 1 0 0 1 1 1 V12 a1 1 0 0 1-1 1 H2.5 a1 1 0 0 1-1-1 Z',
)
</script>

<template>
  <svg
    v-if="dir"
    class="fi fi--folder"
    width="14"
    height="14"
    viewBox="0 0 16 16"
    aria-hidden="true"
  >
    <path :d="folderPath" fill="currentColor" opacity="0.9" />
  </svg>
  <span
    v-else
    class="fi fi--badge"
    :style="{ color: badge[1] }"
    aria-hidden="true"
  >{{ badge[0] }}</span>
</template>

<style scoped>
.fi {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; min-width: 16px; height: 16px; flex-shrink: 0;
}
.fi--folder { color: var(--ccw-accent); }
.fi--badge {
  font-size: 9px; font-weight: 700; letter-spacing: -0.5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
