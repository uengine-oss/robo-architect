<script setup>
import { onMounted, onUnmounted, ref, computed, shallowRef, markRaw, provide } from 'vue'
import TopBar from '@/app/layout/TopBar.vue'
import NavigatorPanel from '@/features/navigator/ui/NavigatorPanel.vue'
import CanvasWorkspace from '@/features/canvas/ui/CanvasWorkspace.vue'
import BigPicturePanel from '@/features/canvas/ui/BigPicturePanel.vue'
import AggregatePanel from '@/features/canvas/ui/AggregatePanel.vue'
import BpmnPanel from '@/features/canvas/ui/BpmnPanel.vue'
import EventModelingPanel from '@/features/eventModeling/ui/EventModelingPanel.vue'
import ClaudeCodeTerminal from '@/features/claudeCode/ui/ClaudeCodeTerminal.vue'
import UserStoryEditModal from '@/features/userStories/ui/UserStoryEditModal.vue'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useUserStoryEditorStore } from '@/features/userStories/userStoryEditor.store'
import { useThemeStore } from '@/app/theme.store'
import { useBpmnStore } from '@/features/canvas/bpmn.store'

const navigatorStore = useNavigatorStore()
const userStoryEditor = useUserStoryEditorStore()
const themeStore = useThemeStore() // Initialize theme store
const bpmnStore = useBpmnStore()

// Tab state management
const activeTab = ref('Design')

// Claude Code workdir state
const claudeCodeWorkdir = ref('')

// Provide activeTab and Claude Code controls to child components
provide('activeTab', activeTab)
provide('openClaudeCode', (workdir) => {
  claudeCodeWorkdir.value = workdir || ''
  activeTab.value = 'Claude Code'
})

// Map tab names to components
const tabComponents = {
  'BPMN': markRaw(BpmnPanel),
  'Event Modeling': markRaw(EventModelingPanel),
  'Big picture': markRaw(BigPicturePanel),
  'Design': markRaw(CanvasWorkspace),
  'Aggregate': markRaw(AggregatePanel),
  'Claude Code': markRaw(ClaudeCodeTerminal)
}

// Cross-component tab switching (HybridEventStormingPanel → Event Modeling)
function _onSwitchTab(e) {
  const target = e?.detail
  if (typeof target === 'string' && tabComponents[target]) {
    activeTab.value = target
  }
}

const currentComponent = computed(() => tabComponents[activeTab.value])

// Navigator panel resize state
const navigatorWidth = ref(320)
const isResizingNavigator = ref(false)
const isNavigatorCollapsed = ref(false)
const savedNavigatorWidth = ref(320) // Store width when collapsing

function startResizeNavigator(e) {
  isResizingNavigator.value = true
  e.preventDefault()
  document.addEventListener('mousemove', onResizeNavigator)
  document.addEventListener('mouseup', stopResizeNavigator)
}

function onResizeNavigator(e) {
  if (!isResizingNavigator.value) return
  const next = Math.round(e.clientX)
  navigatorWidth.value = Math.max(200, Math.min(500, next))
  try {
    localStorage.setItem('navigator_panel_width', String(navigatorWidth.value))
  } catch {}
}

function stopResizeNavigator() {
  isResizingNavigator.value = false
  document.removeEventListener('mousemove', onResizeNavigator)
  document.removeEventListener('mouseup', stopResizeNavigator)
}

function toggleNavigator() {
  if (isNavigatorCollapsed.value) {
    // Expand: restore saved width
    navigatorWidth.value = savedNavigatorWidth.value
    isNavigatorCollapsed.value = false
  } else {
    // Collapse: save current width and set to 0
    savedNavigatorWidth.value = navigatorWidth.value
    navigatorWidth.value = 0
    isNavigatorCollapsed.value = true
  }
  try {
    localStorage.setItem('navigator_collapsed', String(isNavigatorCollapsed.value))
    localStorage.setItem('navigator_panel_width', String(savedNavigatorWidth.value))
  } catch {}
}

async function handleUserStorySaved() {
  try {
    await navigatorStore.refreshAll({ trigger: 'UserStoryEditModal:saved' })
  } catch (e) {
    console.error('[App] navigator refresh failed:', e)
  }
}

function handleUserStoryModalClose() {
  userStoryEditor.close()
}

onMounted(() => {
  // Load saved navigator width and collapsed state
  try {
    const v = Number(localStorage.getItem('navigator_panel_width'))
    if (Number.isFinite(v) && v >= 200) {
      savedNavigatorWidth.value = v
      navigatorWidth.value = v
    }
    const collapsed = localStorage.getItem('navigator_collapsed')
    if (collapsed === 'true') {
      isNavigatorCollapsed.value = true
      navigatorWidth.value = 0
    }
  } catch {}

  // Rehydrate hybrid session at the app level so BPMN canvas is ready the
  // moment the BPMN tab mounts (regardless of which tab the user refreshes on).
  if (bpmnStore.hybridSessionId) {
    bpmnStore.rehydrateHybrid().catch(() => { /* best-effort */ })
  }

  // Listen for cross-component tab switch requests
  window.addEventListener('robo:switch-tab', _onSwitchTab)
})

onUnmounted(() => {
  stopResizeNavigator()
  window.removeEventListener('robo:switch-tab', _onSwitchTab)
})
</script>

<template>
  <div class="app-container">
    <TopBar 
      :active-tab="activeTab"
      @update:active-tab="activeTab = $event"
    />
    <div class="main-content">
      <template v-if="activeTab !== 'Claude Code'">
        <div class="navigator-wrapper" :style="{ width: isNavigatorCollapsed ? '0' : navigatorWidth + 'px' }">
          <NavigatorPanel
            v-show="!isNavigatorCollapsed"
            :style="{ width: navigatorWidth + 'px' }"
          />

          <!-- Navigator Toggle Button (always visible) -->
          <button
            class="navigator-toggle"
            :class="{ 'is-collapsed': isNavigatorCollapsed }"
            @click="toggleNavigator"
            :title="isNavigatorCollapsed ? '네비게이터 펼치기' : '네비게이터 접기'"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline v-if="isNavigatorCollapsed" points="9 18 15 12 9 6"></polyline>
              <polyline v-else points="15 18 9 12 15 6"></polyline>
            </svg>
          </button>
        </div>

        <!-- Navigator Resizer (hover only) -->
        <div
          v-if="!isNavigatorCollapsed"
          class="navigator-resizer"
          @mousedown="startResizeNavigator"
          title="드래그하여 패널 너비 조절"
        ></div>
      </template>

      <!-- Tab Panel Container -->
      <div class="tab-panel-container">
        <KeepAlive>
          <component
            :is="currentComponent"
            :key="activeTab"
            v-bind="activeTab === 'Claude Code' ? { workdir: claudeCodeWorkdir } : {}"
          />
        </KeepAlive>
      </div>
    </div>
    
    <!-- User Story Edit Modal -->
    <UserStoryEditModal 
      :visible="userStoryEditor.isOpen"
      :user-story="userStoryEditor.userStory"
      @close="handleUserStoryModalClose"
      @saved="handleUserStorySaved"
    />
  </div>
</template>

<style scoped>
.navigator-toggle {
  width: 20px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--color-text-light);
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
  z-index: 10;
  position: absolute;
  top: 0;
  right: 0;
  padding: 0;
}

.navigator-toggle:hover {
  background: transparent;
  color: var(--color-text);
}

.navigator-toggle.is-collapsed:hover {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
  border-color: var(--color-accent);
}

.navigator-toggle.is-collapsed {
  right: auto;
  left: 0;
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: 0 6px 6px 0;
}

.navigator-resizer {
  width: 4px;
  cursor: col-resize;
  background: transparent;
  position: relative;
  flex-shrink: 0;
  transition: background 0.2s ease;
}

.navigator-resizer:hover {
  background: rgba(34, 139, 230, 0.3);
}

.main-content {
  position: relative;
}

.navigator-wrapper {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
}

.tab-panel-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
</style>

