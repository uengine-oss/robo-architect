from __future__ import annotations

from typing import Any


class ReadModelOps:
    # =========================================================================
    # ReadModel Operations
    # =========================================================================

    def create_readmodel(
        self,
        *,
        id: str,
        name: str,
        bc_id: str,
        description: str | None = None,
        provisioning_type: str = "CQRS",
    ) -> dict[str, Any]:
        """
        Create a ReadModel node and link it to a BoundedContext via HAS_READMODEL.

        NOTE:
        - provisioningType is used by the UI to decide CQRS config behavior.
        - We keep this idempotent (MERGE on id).
        """
        query = """
        MATCH (bc:BoundedContext {id: $bc_id})
        MERGE (rm:ReadModel {id: $id})
        SET rm.name = $name,
            rm.description = $description,
            rm.provisioningType = $provisioning_type,
            rm.createdAt = coalesce(rm.createdAt, datetime()),
            rm.updatedAt = datetime()
        MERGE (bc)-[:HAS_READMODEL]->(rm)
        RETURN rm {.id, .name, .description, .provisioningType} as readmodel
        """
        with self.session() as session:
            result = session.run(
                query,
                id=id,
                name=name,
                bc_id=bc_id,
                description=description,
                provisioning_type=provisioning_type,
            )
            return dict(result.single()["readmodel"])


