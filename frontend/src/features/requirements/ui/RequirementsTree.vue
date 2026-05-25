<script setup>
import { ref } from 'vue'
import { useRequirementsStore } from '@/features/requirements/requirements.store'

/**
 * Requirements tree (026 — US1/US4): Epic → Feature → UserStory → AcceptanceCriteria.
 * Supports drag-n-drop of user stories between features and delete actions.
 *
 * Spec 030 — UserStory rows that the clarification agent flagged as
 * ambiguous show a yellow ❓N badge. Clicking the row selects the story
 * and opens its detail panel where the "명확화" tab takes over.
 */
const props = defineProps({
  tree: { type: Object, default: () => ({ epics: [], unassigned: [] }) },
  selectedId: { type: String, default: null },
})
const emit = defineEmits([
  'select',
  'move',
  'delete-feature',
  'delete-user-story',
  'clarify-scope',
])

const store = useRequirementsStore()

const expanded = ref(new Set())
const dragOverFeature = ref(null)

function ambiguityInfo(usId) {
  const f = store.clarificationFlags[usId]
  if (!f) return null
  const cats = (f.categories || []).filter(Boolean)
  return { count: (f.questionIds || []).length, categories: cats }
}

function key(prefix, id) {
  return `${prefix}:${id}`
}
function toggle(k) {
  if (expanded.value.has(k)) expanded.value.delete(k)
  else expanded.value.add(k)
  expanded.value = new Set(expanded.value)
}
function isOpen(k) {
  return expanded.value.has(k)
}

function onDragStart(evt, usId) {
  evt.dataTransfer.setData('text/us-id', usId)
  evt.dataTransfer.effectAllowed = 'move'
}
function isRealFeature(featureId) {
  return featureId && !featureId.startsWith('__unassigned__')
}
function onDrop(evt, featureId) {
  dragOverFeature.value = null
  const usId = evt.dataTransfer.getData('text/us-id')
  if (usId && isRealFeature(featureId)) emit('move', { userStoryId: usId, targetFeatureId: featureId })
}
</script>

<template>
  <div class="req-tree">
    <!-- Epics (Bounded Contexts) -->
    <div v-for="epic in tree.epics" :key="epic.id" class="tree-node tree-node--epic">
      <div class="tree-row" @click="toggle(key('epic', epic.id))">
        <span class="caret">{{ isOpen(key('epic', epic.id)) ? '▾' : '▸' }}</span>
        <span class="node-icon epic">EPIC</span>
        <span class="node-label">{{ epic.name }}</span>
        <button
          class="clarify-btn"
          title="요구사항 명확화"
          @click.stop="emit('clarify-scope', { scopeType: 'bounded_context', scopeId: epic.id, scopeName: epic.name })"
        >🔍</button>
      </div>

      <div v-if="isOpen(key('epic', epic.id))" class="tree-children">
        <!-- Features + the per-epic unassigned bucket -->
        <template
          v-for="feature in [...(epic.features || []), ...(epic.unassignedFeature ? [epic.unassignedFeature] : [])]"
          :key="feature.id"
        >
          <div
            class="tree-node tree-node--feature"
            :class="{ 'drag-over': dragOverFeature === feature.id }"
            @dragover.prevent="dragOverFeature = isRealFeature(feature.id) ? feature.id : null"
            @dragleave="dragOverFeature = null"
            @drop="onDrop($event, feature.id)"
          >
            <div class="tree-row" @click="toggle(key('feature', feature.id))">
              <span class="caret">{{ isOpen(key('feature', feature.id)) ? '▾' : '▸' }}</span>
              <span class="node-icon feature">FEAT</span>
              <span class="node-label">{{ feature.name }}</span>
              <button
                v-if="isRealFeature(feature.id)"
                class="clarify-btn"
                title="요구사항 명확화"
                @click.stop="emit('clarify-scope', { scopeType: 'feature', scopeId: feature.id, scopeName: feature.name })"
              >🔍</button>
              <button
                v-if="isRealFeature(feature.id)"
                class="del-btn"
                title="Feature 삭제"
                @click.stop="emit('delete-feature', feature)"
              >×</button>
            </div>

            <div v-if="isOpen(key('feature', feature.id))" class="tree-children">
              <div
                v-for="us in feature.userStories || []"
                :key="us.id"
                class="tree-node tree-node--us"
                draggable="true"
                @dragstart="onDragStart($event, us.id)"
              >
                <div
                  class="tree-row us-row"
                  :class="{ 'is-selected': selectedId === us.id, 'has-ambiguity': ambiguityInfo(us.id) }"
                  @click="emit('select', us.id)"
                >
                  <span
                    class="caret"
                    @click.stop="toggle(key('us', us.id))"
                  >{{ isOpen(key('us', us.id)) ? '▾' : '▸' }}</span>
                  <span class="node-icon us">US</span>
                  <span class="node-label">{{ us.role }}: {{ us.action }}</span>
                  <span
                    v-if="ambiguityInfo(us.id)"
                    class="ambig-badge"
                    :title="`명확화 필요 — ${ambiguityInfo(us.id).count}개 질문 (${ambiguityInfo(us.id).categories.join(', ')})`"
                  >❓ {{ ambiguityInfo(us.id).count }}</span>
                  <button
                    class="del-btn"
                    title="User Story 삭제"
                    @click.stop="emit('delete-user-story', us)"
                  >×</button>
                </div>

                <!-- Acceptance criteria -->
                <div v-if="isOpen(key('us', us.id))" class="tree-children">
                  <div
                    v-for="(c, i) in us.acceptanceCriteria || []"
                    :key="i"
                    class="tree-row ac-row"
                  >
                    <span class="node-icon ac">{{ c.kind }}</span>
                    <span class="node-label ac-label">{{ c.name }}</span>
                  </div>
                  <div v-if="!(us.acceptanceCriteria || []).length" class="tree-row ac-row empty">
                    인수조건 없음
                  </div>
                </div>
              </div>
              <div v-if="!(feature.userStories || []).length" class="tree-row empty-row">
                User Story 없음
              </div>
            </div>
          </div>
        </template>
        <div v-if="!(epic.features || []).length && !epic.unassignedFeature" class="tree-row empty-row">
          Feature 없음
        </div>
      </div>
    </div>

    <!-- Globally unassigned user stories (no BC) -->
    <div v-if="(tree.unassigned || []).length" class="tree-node tree-node--epic">
      <div class="tree-row" @click="toggle('unassigned-root')">
        <span class="caret">{{ isOpen('unassigned-root') ? '▾' : '▸' }}</span>
        <span class="node-icon epic unassigned">미분류</span>
      </div>
      <div v-if="isOpen('unassigned-root')" class="tree-children">
        <div
          v-for="us in tree.unassigned"
          :key="us.id"
          class="tree-row us-row"
          :class="{ 'is-selected': selectedId === us.id, 'has-ambiguity': ambiguityInfo(us.id) }"
          draggable="true"
          @dragstart="onDragStart($event, us.id)"
          @click="emit('select', us.id)"
        >
          <span class="node-icon us">US</span>
          <span class="node-label">{{ us.role }}: {{ us.action }}</span>
          <span
            v-if="ambiguityInfo(us.id)"
            class="ambig-badge"
            :title="`명확화 필요 — ${ambiguityInfo(us.id).count}개 질문`"
          >❓ {{ ambiguityInfo(us.id).count }}</span>
        </div>
      </div>
    </div>

    <div v-if="!(tree.epics || []).length && !(tree.unassigned || []).length" class="tree-row empty-row">
      요구사항이 없습니다. 문서를 업로드하거나 요구사항을 추가하세요.
    </div>
  </div>
</template>

<style scoped>
.req-tree { padding: 8px; font-size: 0.78rem; overflow-y: auto; }
.tree-children { margin-left: 14px; }
.tree-row {
  display: flex; align-items: center; gap: 5px; padding: 3px 4px;
  border-radius: 4px; cursor: pointer; white-space: nowrap;
}
.tree-row:hover { background: var(--color-bg-tertiary); }
.caret { width: 12px; color: var(--color-text-light); flex-shrink: 0; }
.node-icon {
  font-size: 0.56rem; font-weight: 700; padding: 1px 4px; border-radius: 3px;
  flex-shrink: 0;
}
.node-icon.epic { background: rgba(92, 124, 250, 0.2); color: #5c7cfa; }
.node-icon.epic.unassigned { background: var(--color-bg-tertiary); color: var(--color-text-light); }
.node-icon.feature { background: rgba(156, 54, 181, 0.18); color: #9c36b5; }
.node-icon.us { background: rgba(64, 192, 87, 0.2); color: #40c057; }
.node-icon.ac { background: var(--color-bg-tertiary); color: var(--color-text-light); text-transform: uppercase; }
.node-label { overflow: hidden; text-overflow: ellipsis; }
.ac-label { color: var(--color-text-light); }
.us-row.is-selected { background: rgba(34, 139, 230, 0.18); }
.del-btn {
  margin-left: auto; border: none; background: transparent; cursor: pointer;
  color: var(--color-text-light); font-size: 0.9rem; padding: 0 4px;
}
.del-btn:hover { color: #e03131; }
.clarify-btn {
  margin-left: auto; border: none; background: transparent; cursor: pointer;
  color: var(--color-text-light); font-size: 0.8rem; padding: 0 4px;
}
.clarify-btn:hover { color: var(--color-accent, #228be6); }
.clarify-btn + .del-btn { margin-left: 0; }
.empty-row, .ac-row.empty { color: var(--color-text-light); font-style: italic; padding-left: 18px; }
.tree-node--feature.drag-over { outline: 2px dashed var(--color-accent); border-radius: 4px; }
.tree-node--us[draggable='true'] { cursor: grab; }

/* spec 030 — ambiguity badge */
.us-row.has-ambiguity {
  background: linear-gradient(90deg, rgba(255, 196, 0, 0.10), transparent 60%);
}
.ambig-badge {
  font-size: 0.66rem; padding: 1px 6px; border-radius: 4px;
  background: rgba(255, 196, 0, 0.25); color: #8a6500;
  margin-left: 4px; cursor: help; white-space: nowrap;
}
</style>
