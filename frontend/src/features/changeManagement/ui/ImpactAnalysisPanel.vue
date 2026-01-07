<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  title: { type: String, default: 'Impact Analysis' },

  // Seed / connected objects (Round 0)
  connectedNodes: { type: Array, default: () => [] },

  // Propagation
  propagationEnabled: { type: Boolean, default: false },
  propagationConfirmed: { type: Array, default: () => [] },
  propagationReview: { type: Array, default: () => [] },
  propagationRounds: { type: Number, default: 0 },
  propagationStopReason: { type: String, default: '' },

  // Optional counts
  relatedCount: { type: Number, default: null },
  proposedChangesCount: { type: Number, default: null },

  // Controls
  showReview: { type: Boolean, default: true }
})

const showPropagationDetails = ref(true)
const showPropagationReview = ref(false)
const propagationViewMode = ref('timeline') // 'timeline' | 'list'

function formatNodeType(type) {
  const icons = {
    UserStory: '🧩',
    BoundedContext: '🏷️',
    Aggregate: '📦',
    Command: '⚡',
    ReadModel: '📖',
    Event: '📣',
    Policy: '📜',
    UI: '🖥️',
    Property: '{ }'
  }
  return icons[type] || '•'
}

function formatStopReason(reason) {
  const labels = {
    disabled: 'Disabled',
    no_seeds: 'No seed nodes',
    fixpoint_no_frontier: 'Fixpoint (no frontier)',
    fixpoint_no_new_confirmed: 'Fixpoint (no new confirmed)',
    max_rounds_reached: 'Max rounds reached',
    max_confirmed_reached: 'Max confirmed reached',
    budget_exhausted: 'Budget exhausted',
    llm_parse_error: 'LLM parse error'
  }
  return labels[reason] || reason || '-'
}

function formatSuggestedType(t) {
  const labels = {
    rename: 'rename',
    update: 'update',
    create: 'create',
    connect: 'connect',
    delete: 'delete',
    unknown: 'unknown'
  }
  return labels[t] || t || 'unknown'
}

function groupByRound(candidates) {
  const groups = {}
  for (const c of candidates || []) {
    const r = c.round ?? 0
    if (!groups[r]) groups[r] = []
    groups[r].push(c)
  }
  return Object.keys(groups)
    .map(Number)
    .sort((a, b) => a - b)
    .map(round => ({ round, candidates: groups[round] }))
}

const confirmedByRound = computed(() => groupByRound(props.propagationConfirmed))
const reviewByRound = computed(() => groupByRound(props.propagationReview))

function getRoundTotal(round) {
  const confirmed = (props.propagationConfirmed || []).filter(c => (c.round ?? 0) === round).length
  const review = (props.propagationReview || []).filter(c => (c.round ?? 0) === round).length
  return { confirmed, review, total: confirmed + review }
}
</script>

<template>
  <div class="impact-panel">
    <div class="impact-summary">
      <div class="impact-summary__header">
        <span class="impact-summary__icon">🎯</span>
        <span>{{ title }}</span>
      </div>

      <div class="impact-stats">
        <div class="impact-stat">
          <span class="impact-stat__value">{{ connectedNodes.length }}</span>
          <span class="impact-stat__label">Connected Objects</span>
        </div>

        <div class="impact-stat" v-if="propagationEnabled">
          <span class="impact-stat__value">{{ propagationConfirmed.length }}</span>
          <span class="impact-stat__label">Propagation (2nd+ Confirmed)</span>
        </div>

        <div class="impact-stat" v-if="typeof relatedCount === 'number'">
          <span class="impact-stat__value">{{ relatedCount }}</span>
          <span class="impact-stat__label">Related (Other BCs)</span>
        </div>

        <div class="impact-stat" v-if="typeof proposedChangesCount === 'number'">
          <span class="impact-stat__value">{{ proposedChangesCount }}</span>
          <span class="impact-stat__label">Proposed Changes</span>
        </div>
      </div>
    </div>

    <div class="propagation" v-if="propagationEnabled">
      <div class="section-title section-title--row">
        <div>
          <span class="section-title__icon">🧭</span>
          Propagation (2nd~N-th order candidates)
        </div>
        <div class="view-mode-toggle">
          <button
            class="toggle-btn"
            :class="{ 'toggle-btn--active': propagationViewMode === 'timeline' }"
            @click="propagationViewMode = 'timeline'"
            title="Timeline View"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="2" x2="12" y2="22"></line>
              <circle cx="12" cy="6" r="3"></circle>
              <circle cx="12" cy="18" r="3"></circle>
            </svg>
          </button>
          <button
            class="toggle-btn"
            :class="{ 'toggle-btn--active': propagationViewMode === 'list' }"
            @click="propagationViewMode = 'list'"
            title="List View"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="8" y1="6" x2="21" y2="6"></line>
              <line x1="8" y1="12" x2="21" y2="12"></line>
              <line x1="8" y1="18" x2="21" y2="18"></line>
              <line x1="3" y1="6" x2="3.01" y2="6"></line>
              <line x1="3" y1="12" x2="3.01" y2="12"></line>
              <line x1="3" y1="18" x2="3.01" y2="18"></line>
            </svg>
          </button>
          <button class="link-btn" @click="showPropagationDetails = !showPropagationDetails">
            {{ showPropagationDetails ? 'Hide' : 'Show' }}
          </button>
        </div>
      </div>

      <div class="propagation-summary">
        <div class="propagation-pill">
          <span class="propagation-pill__label">Rounds</span>
          <span class="propagation-pill__value">{{ propagationRounds }}</span>
        </div>
        <div class="propagation-pill">
          <span class="propagation-pill__label">Stop</span>
          <span class="propagation-pill__value">{{ formatStopReason(propagationStopReason) }}</span>
        </div>
        <div class="propagation-pill">
          <span class="propagation-pill__label">Confirmed</span>
          <span class="propagation-pill__value">{{ propagationConfirmed.length }}</span>
        </div>
        <div v-if="showReview" class="propagation-pill">
          <span class="propagation-pill__label">Review</span>
          <span class="propagation-pill__value">{{ propagationReview.length }}</span>
        </div>
      </div>

      <div v-if="showPropagationDetails" class="propagation-details">
        <div class="propagation-hint">
          These candidates were discovered by iterative 2-hop expansion (seed = Connected Objects). Evidence paths show
          why they are linked.
        </div>

        <!-- Timeline View -->
        <div v-if="propagationViewMode === 'timeline'" class="propagation-timeline">
          <!-- Seed (Round 0) - Connected Objects -->
          <div class="timeline-round">
            <div class="timeline-round__header">
              <div class="timeline-round__marker timeline-round__marker--seed">
                <span class="timeline-round__number">0</span>
              </div>
              <div class="timeline-round__info">
                <span class="timeline-round__title">Seed (Initial)</span>
                <span class="timeline-round__count">{{ connectedNodes.length }} connected objects</span>
              </div>
            </div>
            <div class="timeline-round__content">
              <div class="timeline-nodes timeline-nodes--seed">
                <div
                  v-for="node in connectedNodes.slice(0, 8)"
                  :key="node.id"
                  class="timeline-node"
                  :title="`${node.type}: ${node.name}`"
                >
                  <span class="timeline-node__icon">{{ formatNodeType(node.type) }}</span>
                  <span class="timeline-node__name">{{ node.name }}</span>
                </div>
                <div v-if="connectedNodes.length > 8" class="timeline-node timeline-node--more">
                  +{{ connectedNodes.length - 8 }} more
                </div>
              </div>
            </div>
            <div class="timeline-connector" v-if="confirmedByRound.length > 0 || (showReview && reviewByRound.length > 0)">
              <div class="timeline-connector__line"></div>
              <div class="timeline-connector__arrow">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 16l-6-6h12z" />
                </svg>
              </div>
            </div>
          </div>

          <!-- Propagation Rounds -->
          <template v-for="(group, groupIdx) in confirmedByRound" :key="'round-' + group.round">
            <div class="timeline-round">
              <div class="timeline-round__header">
                <div class="timeline-round__marker timeline-round__marker--confirmed">
                  <span class="timeline-round__number">{{ group.round }}</span>
                </div>
                <div class="timeline-round__info">
                  <span class="timeline-round__title">Round {{ group.round }}</span>
                  <span class="timeline-round__count">
                    <span class="timeline-count timeline-count--confirmed">{{ group.candidates.length }} confirmed</span>
                    <span
                      v-if="showReview && getRoundTotal(group.round).review > 0"
                      class="timeline-count timeline-count--review"
                    >
                      {{ getRoundTotal(group.round).review }} review
                    </span>
                  </span>
                </div>
              </div>
              <div class="timeline-round__content">
                <div class="timeline-nodes">
                  <div
                    v-for="c in group.candidates"
                    :key="c.id"
                    class="timeline-node timeline-node--confirmed"
                    :title="`${c.type}: ${c.name}\nConfidence: ${Math.round((c.confidence || 0) * 100)}%\n${c.reason || ''}`"
                  >
                    <span class="timeline-node__icon">{{ formatNodeType(c.type) }}</span>
                    <div class="timeline-node__details">
                      <span class="timeline-node__name">{{ c.name || c.id }}</span>
                      <div class="timeline-node__meta">
                        <span class="timeline-node__conf">{{ Math.round((c.confidence || 0) * 100) }}%</span>
                        <span class="timeline-node__action">{{ formatSuggestedType(c.suggested_change_type) }}</span>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Review candidates for this round -->
                <div v-if="showReview && getRoundTotal(group.round).review > 0" class="timeline-review-section">
                  <button class="timeline-review-toggle" @click="showPropagationReview = !showPropagationReview">
                    <span class="badge badge--warn badge--sm">REVIEW</span>
                    {{ showPropagationReview ? 'Hide' : 'Show' }} {{ getRoundTotal(group.round).review }} lower confidence
                  </button>
                  <div v-if="showPropagationReview" class="timeline-nodes timeline-nodes--review">
                    <div
                      v-for="c in propagationReview.filter(r => (r.round ?? 0) === group.round)"
                      :key="c.id"
                      class="timeline-node timeline-node--review"
                    >
                      <span class="timeline-node__icon">{{ formatNodeType(c.type) }}</span>
                      <div class="timeline-node__details">
                        <span class="timeline-node__name">{{ c.name || c.id }}</span>
                        <div class="timeline-node__meta">
                          <span class="timeline-node__conf timeline-node__conf--low">{{
                            Math.round((c.confidence || 0) * 100)
                          }}%</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <div class="timeline-connector" v-if="groupIdx < confirmedByRound.length - 1">
                <div class="timeline-connector__line"></div>
                <div class="timeline-connector__arrow">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 16l-6-6h12z" />
                  </svg>
                </div>
              </div>
            </div>
          </template>

          <div class="timeline-stop">
            <div class="timeline-stop__icon">🛑</div>
            <div class="timeline-stop__text">
              Stopped: <strong>{{ formatStopReason(propagationStopReason) }}</strong>
            </div>
          </div>
        </div>

        <!-- List View -->
        <div v-else class="propagation-list-view">
          <div class="propagation-block">
            <div class="propagation-block__title">
              <span class="badge badge--good">CONFIRMED</span>
              <span>Ready to consider for changes</span>
            </div>
            <div v-if="propagationConfirmed.length === 0" class="empty-muted">No confirmed candidates found.</div>
            <div v-else class="propagation-list">
              <div v-for="c in propagationConfirmed" :key="c.id" class="propagation-item">
                <div class="propagation-item__head">
                  <span class="round-badge">R{{ c.round ?? 0 }}</span>
                  <span class="node-item__icon">{{ formatNodeType(c.type) }}</span>
                  <span class="propagation-item__name">{{ c.name || c.id }}</span>
                  <span class="propagation-item__meta">
                    <span class="pill">ID: {{ c.id }}</span>
                    <span class="pill">BC: {{ c.bcName || 'Unknown' }}</span>
                    <span class="pill">conf: {{ Math.round((c.confidence || 0) * 100) }}%</span>
                    <span class="pill">suggest: {{ formatSuggestedType(c.suggested_change_type) }}</span>
                  </span>
                </div>
                <div v-if="c.reason" class="propagation-item__reason">{{ c.reason }}</div>
                <div v-if="c.evidence_paths && c.evidence_paths.length" class="propagation-item__evidence">
                  <div class="evidence-title">Evidence paths</div>
                  <div v-for="(p, idx) in c.evidence_paths.slice(0, 3)" :key="idx" class="evidence-path">
                    {{ p }}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="showReview" class="propagation-block">
            <div class="propagation-block__title section-title--row">
              <div>
                <span class="badge badge--warn">REVIEW</span>
                <span>Lower confidence (showing up to 20)</span>
              </div>
              <button class="link-btn" @click="showPropagationReview = !showPropagationReview">
                {{ showPropagationReview ? 'Hide' : 'Show' }}
              </button>
            </div>
            <div v-if="showPropagationReview" class="propagation-list">
              <div v-if="propagationReview.length === 0" class="empty-muted">No review candidates.</div>
              <div v-else>
                <div
                  v-for="c in propagationReview.slice(0, 20)"
                  :key="c.id"
                  class="propagation-item propagation-item--review"
                >
                  <div class="propagation-item__head">
                    <span class="round-badge round-badge--review">R{{ c.round ?? 0 }}</span>
                    <span class="node-item__icon">{{ formatNodeType(c.type) }}</span>
                    <span class="propagation-item__name">{{ c.name || c.id }}</span>
                    <span class="propagation-item__meta">
                      <span class="pill">ID: {{ c.id }}</span>
                      <span class="pill">BC: {{ c.bcName || 'Unknown' }}</span>
                      <span class="pill">conf: {{ Math.round((c.confidence || 0) * 100) }}%</span>
                      <span class="pill">suggest: {{ formatSuggestedType(c.suggested_change_type) }}</span>
                    </span>
                  </div>
                  <div v-if="c.reason" class="propagation-item__reason">{{ c.reason }}</div>
                  <div v-if="c.evidence_paths && c.evidence_paths.length" class="propagation-item__evidence">
                    <div class="evidence-title">Evidence paths</div>
                    <div v-for="(p, idx) in c.evidence_paths.slice(0, 2)" :key="idx" class="evidence-path">
                      {{ p }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.impact-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.impact-summary {
  background: linear-gradient(135deg, rgba(34, 139, 230, 0.1), rgba(32, 201, 151, 0.1));
  border: 1px solid rgba(34, 139, 230, 0.3);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.impact-summary__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-weight: 600;
  color: var(--color-text-bright);
  margin-bottom: var(--spacing-md);
}

.impact-summary__icon {
  font-size: 1.25rem;
}

.impact-stats {
  display: flex;
  gap: var(--spacing-lg);
}

.impact-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.impact-stat__value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--color-accent);
}

.impact-stat__label {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.section-title {
  font-size: 0.8rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--color-text-light);
  margin-bottom: var(--spacing-sm);
}

.section-title--row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.section-title__icon {
  margin-right: var(--spacing-xs);
}

.view-mode-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toggle-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--color-text-light);
  border-radius: 8px;
  cursor: pointer;
}

.toggle-btn--active {
  border-color: rgba(34, 139, 230, 0.35);
  color: var(--color-text-bright);
}

.link-btn {
  background: none;
  border: none;
  color: var(--color-accent);
  cursor: pointer;
  font-size: 0.8rem;
}

.propagation-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: var(--spacing-sm);
}

.propagation-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  font-size: 0.75rem;
}

.propagation-pill__label {
  color: var(--color-text-light);
  font-weight: 600;
}

.propagation-pill__value {
  color: var(--color-text-bright);
  font-weight: 700;
}

.propagation-details {
  margin-top: var(--spacing-sm);
}

.propagation-hint {
  font-size: 0.8rem;
  color: var(--color-text-light);
  margin-bottom: var(--spacing-sm);
}

.propagation-timeline {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.timeline-round {
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
}

.timeline-round__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.timeline-round__marker {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(34, 139, 230, 0.25);
  border: 1px solid rgba(34, 139, 230, 0.35);
}

.timeline-round__marker--seed {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.16);
}

.timeline-round__marker--confirmed {
  background: rgba(32, 201, 151, 0.18);
  border-color: rgba(32, 201, 151, 0.35);
}

.timeline-round__number {
  font-weight: 800;
  font-size: 0.8rem;
  color: var(--color-text-bright);
}

.timeline-round__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.timeline-round__title {
  font-weight: 700;
  color: var(--color-text-bright);
}

.timeline-round__count {
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.timeline-count {
  margin-right: 8px;
}

.timeline-count--confirmed {
  color: #20c997;
  font-weight: 700;
}

.timeline-count--review {
  color: #fcc419;
  font-weight: 700;
}

.timeline-nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.timeline-node {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 10px;
  max-width: 100%;
}

.timeline-node--confirmed {
  border-color: rgba(32, 201, 151, 0.25);
}

.timeline-node--review {
  border-color: rgba(252, 196, 25, 0.25);
}

.timeline-node--more {
  color: var(--color-text-light);
}

.timeline-node__icon {
  flex-shrink: 0;
}

.timeline-node__details {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.timeline-node__name {
  font-size: 0.8rem;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 240px;
}

.timeline-node__meta {
  display: flex;
  gap: 6px;
  font-size: 0.7rem;
  color: var(--color-text-light);
}

.timeline-node__conf {
  font-weight: 700;
  color: #20c997;
}

.timeline-node__conf--low {
  color: #fcc419;
}

.timeline-node__action {
  opacity: 0.9;
}

.timeline-connector {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--spacing-sm);
}

.timeline-connector__line {
  flex: 1;
  height: 1px;
  background: rgba(255, 255, 255, 0.1);
}

.timeline-connector__arrow {
  opacity: 0.7;
}

.timeline-review-section {
  margin-top: var(--spacing-sm);
}

.timeline-review-toggle {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--color-text);
  border-radius: 10px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 0.75rem;
}

.timeline-stop {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: var(--spacing-md);
  background: rgba(0, 0, 0, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
}

.timeline-stop__text {
  color: var(--color-text-light);
  font-size: 0.8rem;
}

.timeline-stop__text strong {
  color: var(--color-text-bright);
}

.propagation-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.propagation-block {
  margin-top: var(--spacing-md);
}

.propagation-block__title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: var(--spacing-sm);
}

.propagation-item {
  padding: var(--spacing-sm);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-md);
}

.propagation-item--review {
  border-color: rgba(252, 196, 25, 0.22);
}

.propagation-item__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.propagation-item__name {
  font-weight: 600;
  color: var(--color-text-bright);
}

.propagation-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  color: var(--color-text-light);
  font-size: 0.75rem;
}

.propagation-item__reason {
  margin-top: 6px;
  color: var(--color-text);
  font-size: 0.85rem;
}

.propagation-item__evidence {
  margin-top: 6px;
  font-size: 0.75rem;
  color: var(--color-text-light);
}

.evidence-title {
  font-weight: 700;
  margin-bottom: 4px;
}

.evidence-path {
  font-family: var(--font-mono);
}

.empty-muted {
  color: var(--color-text-light);
  font-size: 0.85rem;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 800;
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.badge--good {
  background: rgba(32, 201, 151, 0.16);
  color: #20c997;
}

.badge--warn {
  background: rgba(252, 196, 25, 0.16);
  color: #fcc419;
}

.badge--sm {
  padding: 1px 6px;
  font-size: 0.65rem;
}

.round-badge {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(34, 139, 230, 0.16);
  color: var(--color-text);
}

.round-badge--review {
  background: rgba(252, 196, 25, 0.16);
}

.pill {
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.node-item__icon {
  font-size: 1rem;
}
</style>


