<script setup>
import { onMounted, onUnmounted, ref, watch, computed, shallowRef, markRaw, provide } from 'vue'
import TopBar from '@/app/layout/TopBar.vue'
import NavigatorPanel from '@/features/navigator/ui/NavigatorPanel.vue'
import CanvasWorkspace from '@/features/canvas/ui/CanvasWorkspace.vue'
import BigPicturePanel from '@/features/canvas/ui/BigPicturePanel.vue'
import AggregatePanel from '@/features/canvas/ui/AggregatePanel.vue'
import UserStoryEditModal from '@/features/userStories/ui/UserStoryEditModal.vue'
import { useNavigatorStore } from '@/features/navigator/navigator.store'
import { useUserStoryEditorStore } from '@/features/userStories/userStoryEditor.store'
import { createLogger, newOpId } from '@/app/logging/logger'

const navigatorStore = useNavigatorStore()
const userStoryEditor = useUserStoryEditorStore()

// Tab state management
const activeTab = ref('Design')

// Provide activeTab to child components
provide('activeTab', activeTab)

// Map tab names to components
const tabComponents = {
  'Big picture': markRaw(BigPicturePanel),
  'Design': markRaw(CanvasWorkspace),
  'Aggregate': markRaw(AggregatePanel)
}

const currentComponent = computed(() => tabComponents[activeTab.value])

// Navigator panel resize state
const navigatorWidth = ref(320)
const isResizingNavigator = ref(false)

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

const log = createLogger({ scope: 'App' })
const appInstanceId = newOpId('app')

function summarizeUserStory(us) {
  if (!us) return null
  return {
    id: us.id,
    // Keep content safe/compact: lengths only (enough to validate "what changed" without dumping text).
    roleLen: typeof us.role === 'string' ? us.role.length : 0,
    actionLen: typeof us.action === 'string' ? us.action.length : 0,
    benefitLen: typeof us.benefit === 'string' ? us.benefit.length : 0
  }
}

function getNavigatorSnapshot() {
  return {
    contextsCount: navigatorStore.contexts?.length ?? 0,
    unassignedUserStoriesCount: navigatorStore.userStories?.length ?? 0,
    contextTreesCount: navigatorStore.contextTrees ? Object.keys(navigatorStore.contextTrees).length : 0,
    navigatorLoading: !!navigatorStore.loading,
    navigatorError: navigatorStore.error ?? null
  }
}

async function handleUserStorySaved() {
  const opId = newOpId('us_save')
  const us = summarizeUserStory(userStoryEditor.userStory)
  const before = getNavigatorSnapshot()

  log.info(
    'user_story_saved_event_received',
    'User story was saved in the editor; refreshing Navigator to reflect changes.',
    { appInstanceId, opId, userStory: us, before }
  )

  const t0 = (globalThis.performance && performance.now) ? performance.now() : Date.now()
  try {
    // Refresh the navigator to reflect changes (pass reason metadata for traceability)
    await navigatorStore.refreshAll({ trigger: 'UserStoryEditModal:saved', opId, userStoryId: us?.id })
  } catch (e) {
    const durationMs = Math.round(((globalThis.performance && performance.now) ? performance.now() : Date.now()) - t0)
    log.error(
      'navigator_refresh_throw',
      'Navigator refresh threw an exception (unexpected); UI may be out of sync.',
      { appInstanceId, opId, durationMs, userStory: us, errorMessage: e?.message || String(e) }
    )
    return
  }

  const durationMs = Math.round(((globalThis.performance && performance.now) ? performance.now() : Date.now()) - t0)
  const after = getNavigatorSnapshot()

  if (after.navigatorError) {
    log.warn(
      'navigator_refresh_completed_with_error',
      'Navigator refresh finished but reported an error; verify API availability and retry if needed.',
      { appInstanceId, opId, durationMs, userStory: us, after }
    )
    return
  }

  log.info(
    'navigator_refresh_completed',
    'Navigator refresh completed successfully; UI should now reflect the saved user story changes.',
    { appInstanceId, opId, durationMs, userStory: us, after }
  )
}

function handleUserStoryModalClose() {
  const us = summarizeUserStory(userStoryEditor.userStory)
  log.info(
    'user_story_editor_close_requested',
    'User story editor modal requested to close; clearing editor state.',
    { appInstanceId, userStory: us, isOpen: userStoryEditor.isOpen }
  )
  userStoryEditor.close()
}

onMounted(() => {
  // Load saved navigator width
  try {
    const v = Number(localStorage.getItem('navigator_panel_width'))
    if (Number.isFinite(v) && v >= 200) navigatorWidth.value = v
  } catch {}

  log.info('app_mounted', 'App mounted; core layout components are ready.', {
    appInstanceId,
    envMode: (() => {
      try { return import.meta?.env?.MODE } catch { return undefined }
    })(),
    initial: {
      userStoryEditorOpen: !!userStoryEditor.isOpen,
      userStory: summarizeUserStory(userStoryEditor.userStory),
      navigator: getNavigatorSnapshot()
    }
  })
})

onUnmounted(() => {
  stopResizeNavigator()
})

watch(
  () => userStoryEditor.isOpen,
  (isOpen, wasOpen) => {
    // Only log transitions (skip initial noise when both are falsy)
    if (isOpen === wasOpen) return
    const us = summarizeUserStory(userStoryEditor.userStory)
    if (isOpen) {
      log.info(
        'user_story_editor_opened',
        'User story editor modal opened; user can edit and apply changes.',
        { appInstanceId, userStory: us }
      )
    } else {
      log.info(
        'user_story_editor_closed',
        'User story editor modal closed.',
        { appInstanceId, userStory: us }
      )
    }
  }
)
</script>

<template>
  <div class="app-container">
    <TopBar 
      :active-tab="activeTab"
      @update:active-tab="activeTab = $event"
    />
    <div class="main-content">
      <NavigatorPanel :style="{ width: navigatorWidth + 'px' }" />
      
      <!-- Navigator Resizer -->
      <div 
        class="navigator-resizer"
        @mousedown="startResizeNavigator"
        title="드래그하여 패널 너비 조절"
      ></div>
      
      <!-- Tab Panel Container -->
      <div class="tab-panel-container">
        <KeepAlive>
          <component :is="currentComponent" :key="activeTab" />
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
.navigator-resizer {
  width: 6px;
  cursor: col-resize;
  background: transparent;
  position: relative;
  flex-shrink: 0;
}

.navigator-resizer:hover {
  background: rgba(34, 139, 230, 0.12);
}

.tab-panel-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}
</style>

