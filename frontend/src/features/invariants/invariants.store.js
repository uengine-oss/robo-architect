import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { invariantsApi } from './invariants.api'

/**
 * Pinia store for Aggregate Invariants (feature 027).
 *
 * Holds the per-Aggregate invariant lists shown in the design tree's
 * "Invariants" group. The first load of an Aggregate triggers the backend's
 * lazy legacy-text migration.
 *
 * Invariant *editing* happens in the right-side property panel
 * (`InspectorPanel` → `InvariantEditor`), reached via the `inspectorRequest`
 * store — so this store no longer carries any modal state.
 */
export const useInvariantsStore = defineStore('invariants', () => {
  // { [aggregateId]: { loading, loaded, error, items: InvariantSummary[] } }
  const byAggregate = reactive({})

  function _slot(aggregateId) {
    if (!byAggregate[aggregateId]) {
      byAggregate[aggregateId] = { loading: false, loaded: false, error: null, items: [] }
    }
    return byAggregate[aggregateId]
  }

  function itemsFor(aggregateId) {
    return byAggregate[aggregateId]?.items || []
  }

  async function reload(aggregateId) {
    const slot = _slot(aggregateId)
    slot.loading = true
    slot.error = null
    try {
      const res = await invariantsApi.listForAggregate(aggregateId)
      slot.items = res.invariants || []
      slot.loaded = true
    } catch (e) {
      slot.error = e.message || String(e)
    } finally {
      slot.loading = false
    }
  }

  async function ensureLoaded(aggregateId) {
    const slot = _slot(aggregateId)
    if (!slot.loaded && !slot.loading) await reload(aggregateId)
  }

  async function create(aggregateId, declaration, name = null, description = null) {
    const created = await invariantsApi.create(aggregateId, { declaration, name, description })
    await reload(aggregateId)
    return created
  }

  return {
    byAggregate,
    itemsFor,
    reload,
    ensureLoaded,
    create,
  }
})
