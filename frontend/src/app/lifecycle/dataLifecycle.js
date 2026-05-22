/**
 * Data-lifecycle bus.
 *
 * A single window CustomEvent (`robo:data-changed`) signals that the graph
 * data underneath every tab has changed — fired when an ingestion completes
 * or when data is cleared. Each tab's navigator/canvas subscribes via
 * `useDataRefresh()` and re-fetches, so no tab is left showing stale data.
 *
 * Window events (not a Pinia store) keep producer and consumers decoupled —
 * the producer needn't import every consumer's store — and match the existing
 * `robo:*` window-event style (`robo:switch-tab`, `robo:hybrid-promote`).
 */
import { onMounted, onUnmounted } from 'vue'

const EVENT = 'robo:data-changed'

/** Announce that graph data changed. `reason`: 'ingestion-complete' | 'cleared'. */
export function emitDataChanged(reason = 'unknown') {
  window.dispatchEvent(new CustomEvent(EVENT, { detail: { reason } }))
}

/**
 * Re-run `refreshFn` whenever graph data changes. Registers the listener on
 * mount and removes it on unmount — call once at `<script setup>` top level.
 */
export function useDataRefresh(refreshFn) {
  const handler = (e) => {
    try {
      refreshFn(e?.detail?.reason)
    } catch (err) {
      console.error('[dataLifecycle] refresh failed:', err)
    }
  }
  onMounted(() => window.addEventListener(EVENT, handler))
  onUnmounted(() => window.removeEventListener(EVENT, handler))
}
