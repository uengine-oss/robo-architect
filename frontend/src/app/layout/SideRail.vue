<script setup>
// 왼쪽 아이콘 레일 — Ontological Studio 의 Studio 레일과 같은 모양(패밀리 룩).
// 상단 탭 막대(TopBar)에 있던 화면 전환을 여기로 옮겼다. 위에 브랜드 박스, 가운데 화면,
// 아래에 그래프 연결 상태 · 테마 · 개발사 표시.
import { computed } from 'vue'
import { useThemeStore } from '@/app/theme.store'
import { useSessionStore } from '@/features/desktop-launcher/stores/session-store.js'

const props = defineProps({
  activeTab: { type: String, default: 'Proposals' },
})
const emit = defineEmits(['update:activeTab'])

const theme = useThemeStore()
const session = useSessionStore()

// 'Process' 는 BPM(Process)⇄Event Modeling(Processes) 서브토글을 묶은 한 항목(TopBar 서브토글 유지).
const ITEMS = [
  { tab: 'Proposals', label: '프로포절', icon: 'Proposals' },
  { tab: 'Stories', label: '요구사항', icon: 'Stories' },
  { tab: 'Process', label: '프로세스', icon: 'Process' },
  { tab: 'Design', label: '설계', icon: 'Design' },
  { tab: 'Data', label: '데이터', icon: 'Data' },
  { tab: 'Code', label: '코드', icon: 'Code' },
  { tab: 'Legacy', label: '레거시', icon: 'Legacy' },
]
const ICONS = {
  Proposals: '<path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/><path d="M9 13l2 2 4-4"/>',
  Stories: '<path d="M4 6.5h16M4 12h16M4 17.5h10"/><circle cx="18.5" cy="17.5" r="1.6"/>',
  Process: '<rect x="2.5" y="9" width="5.5" height="6" rx="1.4"/><rect x="16" y="9" width="5.5" height="6" rx="1.4"/><path d="M8 12h8"/><path d="M13.5 9.5L16 12l-2.5 2.5"/>',
  Design: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="8.5" y="13.5" width="7" height="7" rx="1.5"/><path d="M7 10.5v1.5h10v-1.5M12 12v1.5"/>',
  Data: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  Code: '<path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5"/><path d="M13.5 4.5l-3 15"/>',
  Legacy: '<rect x="3" y="4" width="18" height="16" rx="2.2"/><path d="M7 9.5l3 2.5-3 2.5M12.5 15h4.5"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
  moon: '<path d="M20 14.2A8 8 0 0 1 9.8 4a8 8 0 1 0 10.2 10.2z"/>',
}

function isActive(tab) {
  if (tab === 'Process') return ['Process', 'Processes', 'Event Modeling'].includes(props.activeTab)
  if (tab === 'Stories') return ['Stories', 'Requirements'].includes(props.activeTab)
  if (tab === 'Data') return ['Data', 'Aggregate'].includes(props.activeTab)
  return props.activeTab === tab
}

const graphLabel = computed(() => session.graph || (session.isDesktop ? '—' : 'web'))
</script>

<template>
  <nav class="rail" aria-label="화면">
    <div class="rail__brand" title="Robo Architect">
      <img src="/brand/ra-box.svg" alt="Robo Architect" />
    </div>
    <div class="rail__items">
      <button
        v-for="it in ITEMS"
        :key="it.tab"
        class="rail__item"
        :class="{ 'is-active': isActive(it.tab) }"
        :title="it.label"
        @click="emit('update:activeTab', it.tab)"
      >
        <svg class="rail__ic" viewBox="0 0 24 24" aria-hidden="true" v-html="ICONS[it.icon]"></svg>
        <span>{{ it.label }}</span>
      </button>
    </div>
    <div class="rail__fill"></div>
    <div class="rail__foot">
      <div class="rail__status" :title="`Ontological 그래프 ${graphLabel}`">
        <span class="rail__dot"></span>
        <span class="rail__graph">{{ graphLabel }}</span>
      </div>
      <button class="rail__btn" :title="theme.theme === 'dark' ? '라이트 테마' : '다크 테마'" @click="theme.toggleTheme()">
        <svg class="rail__ic" viewBox="0 0 24 24" aria-hidden="true" v-html="ICONS[theme.theme === 'dark' ? 'sun' : 'moon']"></svg>
      </button>
      <a class="rail__credit" href="https://www.uengine.org" target="_blank" rel="noopener" title="유엔진솔루션즈 개발 — www.uengine.org" aria-label="uEngine"></a>
    </div>
  </nav>
</template>

<style scoped>
.rail {
  width: 76px; flex: none; display: flex; flex-direction: column; align-items: stretch;
  background: var(--color-bg-secondary); border-right: 1px solid var(--color-border);
  padding: 12px 8px 10px; gap: 4px; user-select: none;
}
.rail__brand { display: grid; place-items: center; padding: 4px 0 12px; margin-bottom: 6px; border-bottom: 1px solid var(--color-border); }
.rail__brand img { width: 40px; height: 40px; }
/* one-colour box (desktop/scripts/make-brand.py): black, flipped for the dark theme
   (--brand-filter in main.css — a scoped :global() here would compile to the bare theme class) */
.rail__brand img { filter: var(--brand-filter, invert(1)); }
.rail__items { display: flex; flex-direction: column; gap: 2px; }
.rail__item {
  display: flex; flex-direction: column; align-items: center; gap: 5px; padding: 9px 2px 8px;
  border: 0; border-radius: 9px; background: transparent; color: var(--color-text-light);
  font-size: 11.5px; line-height: 1.2; cursor: pointer; position: relative;
}
.rail__item:hover { background: var(--color-bg-tertiary); color: var(--color-text-bright); }
.rail__item.is-active { background: var(--color-accent-soft); color: var(--color-accent); font-weight: 600; }
.rail__item.is-active::before {
  content: ''; position: absolute; left: -8px; top: 10px; bottom: 10px; width: 3px; border-radius: 0 3px 3px 0; background: var(--color-accent);
}
.rail__ic { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
.rail__fill { flex: 1; }
.rail__foot { display: flex; flex-direction: column; align-items: center; gap: 8px; padding-top: 10px; border-top: 1px solid var(--color-border); }
.rail__status { display: flex; flex-direction: column; align-items: center; gap: 4px; font-size: 10.5px; color: var(--color-accent); font-weight: 600; max-width: 100%; }
.rail__graph { max-width: 64px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rail__dot { width: 7px; height: 7px; border-radius: 50%; background: var(--color-accent); box-shadow: 0 0 0 3px var(--color-accent-soft); }
.rail__btn { width: 34px; height: 30px; border: 0; border-radius: 7px; background: transparent; color: var(--color-text-light); display: grid; place-items: center; cursor: pointer; }
.rail__btn:hover { background: var(--color-bg-tertiary); color: var(--color-text-bright); }
.rail__btn .rail__ic { width: 18px; height: 18px; }
.rail__credit {
  width: 52px; height: 13px; margin: 2px 0; background: var(--color-text-light);
  -webkit-mask: url(/brand/uengine-logo.svg) center / contain no-repeat; mask: url(/brand/uengine-logo.svg) center / contain no-repeat;
}
.rail__credit:hover { background: var(--color-text-bright); }
</style>
