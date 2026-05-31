"""Tests for 034 — recoverable deletion (option B snapshot) contracts + wiring.

The snapshot/restore round-trip itself is verified end-to-end against a live
Neo4j (Epic/Feature/UserStory delete → :DeletionRecord → restore re-links the
subtree). These tests lock in the request/response schema defaults and that
the deletion-history routes are registered on the requirements router.
"""

from __future__ import annotations

from api.features.requirements.requirements_contracts import (
    BoundedContextDeleteRequest,
    BoundedContextDeleteResponse,
    DeletionRecordDTO,
    FeatureDeleteRequest,
    RestoreResponse,
    UserStoryDeleteRequest,
)
from api.features.requirements.router import router


def test_remove_design_defaults_off():
    """removeDesign is opt-in (user decision) across every delete scope."""
    assert BoundedContextDeleteRequest(boundedContextId="bc-1").removeDesign is False
    assert FeatureDeleteRequest(featureId="f-1").removeDesign is False
    assert UserStoryDeleteRequest(userStoryId="us-1").removeDesign is False
    # disposition still defaults to the non-destructive 'unassign'
    assert FeatureDeleteRequest(featureId="f-1").userStoryDisposition == "unassign"


def test_delete_responses_carry_restore_batch():
    resp = BoundedContextDeleteResponse(deleted=True, restoreBatchId="batch-1")
    assert resp.restoreBatchId == "batch-1"
    assert resp.affectedFeatureIds == [] and resp.affectedUserStoryIds == []


def test_record_and_restore_models():
    rec = DeletionRecordDTO(
        batchId="b", scope="epic", rootLabel="BoundedContext", createdAt="2026-05-31T00:00"
    )
    assert rec.restored is False and rec.nodeCount == 0
    assert RestoreResponse(restored=True, nodeCount=3, relinked=2).relinked == 2


def test_deletion_history_routes_registered():
    paths = {r.path for r in router.routes}
    assert "/api/requirements/deletion-records" in paths
    assert "/api/requirements/deletion-records/{batch_id}/restore" in paths
    # DELETE /bounded-context (Epic delete) is registered too
    methods = {(r.path, m) for r in router.routes for m in getattr(r, "methods", set())}
    assert ("/api/requirements/bounded-context", "DELETE") in methods
