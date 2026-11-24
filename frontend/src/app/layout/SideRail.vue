<script setup>
// 왼쪽 아이콘 레일 — Ontological Studio 의 Studio 레일과 같은 모양(패밀리 룩).
// 상단 탭 막대(TopBar)에 있던 화면 전환을 여기로 옮겼다. 위에 브랜드 박스, 가운데 화면,
// 아래에 그래프 연결 상태 · 테마 · 개발사 표시.
// 레거시 탭에서는 앱 화면 대신 레거시 기능의 메뉴(코드 · 데이터 소스 · 코드 그래프 · 데이터 스키마)만 보인다.
import { computed, onMounted, ref } from 'vue'
import { useThemeStore } from '@/app/theme.store'
import { useSessionStore } from '@/features/desktop-launcher/stores/session-store.js'
import { LEGACY_FEATURES, legacyFeature, openLegacyFeature } from '@/features/analysis/legacyNav'
import { visibleTabs } from '@/app/customer'
import { FIGMA_VISIBLE } from '@/app/featureVisibility'
import { useRuntimeStore } from '@/features/runtime-status/runtime.store.js'
import { detectShellTabs, railTabTarget, wantsInPlace } from './railTabs'

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
  // 'Template' — 템플릿 기반 코드 생성(ENT-GEN-001). 통합 P4 에서 레일 항목이 됐다.
  { tab: 'Template', label: '템플릿', icon: 'Template' },
  { tab: 'Legacy', label: '레거시', icon: 'Legacy' },
]
// 고객 확장이 감춘 화면은 뺀다(포스코: Proposals·Code — 사내망에 claude CLI 가 없다).
const shownTabs = new Set(visibleTabs(ITEMS.map((it) => it.tab)))
const visibleItems = ITEMS.filter((it) => shownTabs.has(it.tab))

// 058 T029 — 준비 안 된 기능은 **진입을 막되 이유를 말한다.** 좁게 간다: 이름이 붙은 자리(레거시 탐색)만.
// 넓게 막으면 프로브가 한 번 틀린 날 멀쩡한 앱이 통째로 잠긴다(2026-10-07 실제로 배선이 틀렸다).
const runtime = useRuntimeStore()
const TAB_CAPABILITY = { Legacy: 'legacy-analysis' }
const blocked = (tab) => (TAB_CAPABILITY[tab] ? !runtime.isAvailable(TAB_CAPABILITY[tab]) : false)
const blockedWhy = (tab) => (TAB_CAPABILITY[tab] ? runtime.blockedReason(TAB_CAPABILITY[tab]) : null)
const ICONS = {
  Proposals: '<path d="M6 3.5h8.5L19 8v12.5H6z"/><path d="M14 3.5V8h5"/><path d="M9 13l2 2 4-4"/>',
  Stories: '<path d="M4 6.5h16M4 12h16M4 17.5h10"/><circle cx="18.5" cy="17.5" r="1.6"/>',
  Process: '<rect x="2.5" y="9" width="5.5" height="6" rx="1.4"/><rect x="16" y="9" width="5.5" height="6" rx="1.4"/><path d="M8 12h8"/><path d="M13.5 9.5L16 12l-2.5 2.5"/>',
  Design: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="8.5" y="13.5" width="7" height="7" rx="1.5"/><path d="M7 10.5v1.5h10v-1.5M12 12v1.5"/>',
  Data: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  Code: '<path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5"/><path d="M13.5 4.5l-3 15"/>',
  Template: '<rect x="3.5" y="3.5" width="17" height="17" rx="2"/><path d="M3.5 9h17M9 9v11.5"/><path d="M12.5 13h5M12.5 16.5h3.5"/>',
  Legacy: '<rect x="3" y="4" width="18" height="16" rx="2.2"/><path d="M7 9.5l3 2.5-3 2.5M12.5 15h4.5"/>',
  LegacyCode: '<path d="M8.5 7L3.5 12l5 5M15.5 7l5 5-5 5"/>',
  LegacySources: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6"/><path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  LegacyGraph: '<circle cx="12" cy="5.5" r="2.2"/><circle cx="5.5" cy="18" r="2.2"/><circle cx="18.5" cy="18" r="2.2"/><path d="M11 7.5L6.6 16M13 7.5l4.4 8.5M7.7 18h8.6"/>',
  LegacySchema: '<rect x="3.5" y="4.5" width="17" height="15" rx="2"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10"/>',
  figma: '<path d="M8.5 3.5h3.5v6H8.5a3 3 0 0 1 0-6z"/><path d="M12 3.5h3.5a3 3 0 0 1 0 6H12z"/><path d="M8.5 9.5H12v6H8.5a3 3 0 0 1 0-6z"/><circle cx="15.5" cy="12.5" r="3"/><path d="M8.5 15.5H12v3a3 3 0 1 1-3.5-3z"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4"/>',
  moon: '<path d="M20 14.2A8 8 0 0 1 9.8 4a8 8 0 1 0 10.2 10.2z"/>',
}

function isActive(tab) {
  if (tab === 'Process') return ['Process', 'Processes', 'Event Modeling'].includes(props.activeTab)
  if (tab === 'Stories') return ['Stories', 'Requirements'].includes(props.activeTab)
  if (tab === 'Data') return ['Data', 'Aggregate'].includes(props.activeTab)
  return props.activeTab === tab
}

const isLegacy = computed(() => props.activeTab === 'Legacy')
// 데스크톱 셸은 레거시를 **따로 탭**으로 열어 그 탭의 레일을 레거시 메뉴로만 채운다(돌아갈 곳은 다른 탭).
// 웹 판(포스코 등)에는 셸 탭이 없다 — 레일이 레거시 메뉴로만 바뀌면 다른 화면으로 돌아갈 길이 없어진다.
// 그래서 웹에서는 앱 화면 목록을 그대로 두고, 레거시 아래에 그 메뉴를 붙인다(통합 P4).
//
// "셸 탭이 있다" 는 **lite 프로필의 탭 창**일 때만이다(railTabs.js). enterprise 도 preload 가 같아
// `window.raShell` 이 있지만 탭 처리기가 없다 — 예전 판은 그걸로 갈라 enterprise 의 「레거시」 클릭이 사라졌다.
const hasShellTabs = ref(false)
onMounted(async () => { hasShellTabs.value = await detectShellTabs() })
const legacyOnlyRail = computed(() => isLegacy.value && hasShellTabs.value)

// C-1 ④ — lite 탭 창에서는 레일 클릭이 **새 탭**으로 연다(같은 화면 탭이 있으면 그 탭으로, reuse).
// Ctrl/⌘-클릭은 제자리 전환. 웹 판·enterprise 는 지금처럼 제자리다.
// 「레거시」는 수식키와 상관없이 따로 탭이다 — 레거시 탭의 레일은 레거시 메뉴만 보이므로, 지금 탭을
// 레거시로 바꾸면 원래 화면으로 돌아갈 메뉴가 없어진다.
async function select(tab, event) {
  const shellTabs = hasShellTabs.value
  const inPlace = tab === 'Legacy' ? false : wantsInPlace(event)
  // 코드 화면은 작업 폴더를 아직 안 골랐으면 App 이 PRD 안내를 띄운다(onRailSelect) — 그 길을 그대로 탄다.
  const codeUnset = tab === 'Code' && !codeWorkspaceSet()
  const target = codeUnset ? null : railTabTarget({ tab, current: isActive(tab), shellTabs, inPlace })
  if (target) {
    try {
      const id = await window.raShell.openTab(target)
      if (id) return
    } catch { /* 탭을 못 열면 제자리로 — 누른 것이 사라지지 않게 */ }
  }
  emit('update:activeTab', tab)
}

function codeWorkspaceSet() {
  try { return !!localStorage.getItem('claude_code_workspace_root') } catch { return false }
}

// 설정 · Figma 창은 TopBar 가 들고 있다 — 이벤트로 연다
function openEv(name) { window.dispatchEvent(new CustomEvent(name)) }

const graphLabel = computed(() => session.graph || (session.isDesktop ? '—' : 'web'))
</script>

<template>
  <nav class="rail" aria-label="화면">
    <div class="rail__brand" title="Robo Architect">
      <img src="/brand/ra-box.svg" alt="Robo Architect" />
    </div>
    <div v-if="legacyOnlyRail" class="rail__items" aria-label="레거시">
      <button
        v-for="f in LEGACY_FEATURES"
        :key="f.id"
        class="rail__item"
        :class="{ 'is-active': legacyFeature === f.id }"
        :title="f.label"
        @click="openLegacyFeature(f.id)"
      >
        <svg class="rail__ic" viewBox="0 0 24 24" aria-hidden="true" v-html="ICONS[f.icon]"></svg>
        <span>{{ f.label }}</span>
      </button>
    </div>
    <div v-else class="rail__items">
      <button
        v-for="it in visibleItems"
        :key="it.tab"
        class="rail__item"
        :class="{ 'is-active': isActive(it.tab), 'is-blocked': blocked(it.tab) }"
        :title="blocked(it.tab) ? blockedWhy(it.tab) : it.label"
        :disabled="blocked(it.tab)"
        @click="select(it.tab, $event)"
      >
        <svg class="rail__ic" viewBox="0 0 24 24" aria-hidden="true" v-html="ICONS[it.icon]"></svg>
        <span>{{ it.label }}</span>
      </button>
      <!-- 웹 판: 레거시 화면일 때 그 메뉴를 레일 안에 붙인다 -->
      <div v-if="isLegacy" class="rail__sub" aria-label="레거시">
        <button
          v-for="f in LEGACY_FEATURES"
          :key="f.id"
          class="rail__item rail__item--sub"
          :class="{ 'is-active': legacyFeature === f.id }"
          :title="f.label"
          @click="openLegacyFeature(f.id)"
        >
          <svg class="rail__ic" viewBox="0 0 24 24" aria-hidden="true" v-html="ICONS[f.icon]"></svg>
          <span>{{ f.label }}</span>
        </button>
      </div>
    </div>
    <div class="rail__fill"></div>
    <div class="rail__foot">
      <div class="rail__status" :title="`Ontological 그래프 ${graphLabel}`">
        <span class="rail__dot"></span>
        <span class="rail__graph">{{ graphLabel }}</span>
      </div>
      <!-- Figma 가 꺼진 서버(포스코)에서는 단추부터 없다 — featureVisibility FIGMA_VISIBLE -->
      <button v-if="FIGMA_VISIBLE" class="rail__btn" title="Figma 연동" @click="openEv('robo:open-figma')">
        <svg class="rail__ic" viewBox="0 0 24 24" aria-hidden="true" v-html="ICONS.figma"></svg>
      </button>
      <button class="rail__btn" title="설정" @click="openEv('robo:open-settings')">
        <svg class="rail__ic" viewBox="0 0 24 24" aria-hidden="true" v-html="ICONS.gear"></svg>
      </button>
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
  word-break: keep-all; text-align: center;
}
.rail__item:hover { background: var(--color-bg-tertiary); color: var(--color-text-bright); }
.rail__item.is-active { background: var(--color-accent-soft); color: var(--color-accent); font-weight: 600; }
.rail__item.is-blocked { opacity: 0.45; cursor: not-allowed; }
.rail__sub { display: flex; flex-direction: column; gap: 2px; margin: 2px 0 4px; padding-top: 4px; border-top: 1px dashed var(--color-border); }
.rail__item--sub { padding: 6px 2px 5px; font-size: 10.5px; }
.rail__item--sub .rail__ic { width: 18px; height: 18px; }
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
