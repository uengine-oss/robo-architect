/**
 * REST client for Aggregate Invariants (feature 027).
 *
 * GWT editing reuses the existing `/api/graph/gwt` endpoints — the Invariant
 * editor calls `upsertGwt`/`getGwt` with `parentType="Invariant"` (own bundle)
 * or `parentType="Command"` (shared, edits propagate to that Command).
 */

const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function unwrap(res) {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch {}
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  if (res.status === 204) return null
  return res.json()
}

export const invariantsApi = {
  // ── Invariant CRUD ────────────────────────────────────────────────────
  listForAggregate(aggregateId) {
    return fetch(`/api/aggregates/${aggregateId}/invariants`).then(unwrap)
  },
  create(aggregateId, body) {
    return fetch(`/api/aggregates/${aggregateId}/invariants`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }).then(unwrap)
  },
  get(invariantId) {
    return fetch(`/api/invariants/${invariantId}`).then(unwrap)
  },
  update(invariantId, body) {
    return fetch(`/api/invariants/${invariantId}`, {
      method: 'PATCH',
      headers: JSON_HEADERS,
      body: JSON.stringify(body),
    }).then(unwrap)
  },
  remove(invariantId) {
    return fetch(`/api/invariants/${invariantId}`, { method: 'DELETE' }).then(unwrap)
  },

  // ── Shared-condition references (VERIFIED_BY) ─────────────────────────
  referenceCandidates(invariantId) {
    return fetch(`/api/invariants/${invariantId}/reference-candidates`).then(unwrap)
  },
  addReference(invariantId, commandId) {
    return fetch(`/api/invariants/${invariantId}/references`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ commandId }),
    }).then(unwrap)
  },
  removeReference(invariantId, commandId) {
    return fetch(`/api/invariants/${invariantId}/references/${commandId}`, {
      method: 'DELETE',
    }).then(unwrap)
  },

  // ── GWT bundle (shared with the Command GWT editor) ───────────────────
  getGwt(parentType, parentId) {
    return fetch(`/api/graph/gwt/${parentType}/${parentId}`).then(unwrap)
  },
  upsertGwt(payload) {
    return fetch('/api/graph/gwt/upsert', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }).then(unwrap)
  },

  // ── Aggregate exception domain-object catalog ─────────────────────────
  getExceptions(aggregateId) {
    return fetch(`/api/aggregates/${aggregateId}/exceptions`).then(unwrap)
  },
  putExceptions(aggregateId, exceptions) {
    return fetch(`/api/aggregates/${aggregateId}/exceptions`, {
      method: 'PUT',
      headers: JSON_HEADERS,
      body: JSON.stringify({ exceptions }),
    }).then(unwrap)
  },
}
