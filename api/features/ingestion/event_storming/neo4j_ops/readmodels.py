from __future__ import annotations

from typing import Any

from api.platform.keys import readmodel_key


class ReadModelOps:
    # =========================================================================
    # ReadModel Operations
    # =========================================================================

    def create_readmodel(
        self,
        *,
        name: str,
        bc_id: str,
        key: str | None = None,
        description: str | None = None,
        provisioning_type: str = "CQRS",
        actor: str | None = None,
        is_multiple_result: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a ReadModel node and link it to a BoundedContext via HAS_READMODEL.

        NOTE:
        - provisioningType is used by the UI to decide CQRS config behavior.
        - We keep this idempotent (MERGE on key).
        """
        display_name = display_name or name
        with self.session() as session:
            bc_rec = session.run("MATCH (bc:BoundedContext {id: $id}) RETURN bc.key as key", id=bc_id).single()
            bc_key_value = (bc_rec or {}).get("key") or ""
            if not bc_key_value:
                raise ValueError(f"BoundedContext not found or missing key: {bc_id}")
            key = key or readmodel_key(bc_key_value, name)

            query = """
            MATCH (bc:BoundedContext {id: $bc_id})
            MERGE (rm:ReadModel {key: $key})
            ON CREATE SET rm.id = randomUUID(),
                          rm.createdAt = datetime()
            SET rm.key = $key,
                rm.name = $name,
                rm.displayName = $display_name,
                rm.description = $description,
                rm.provisioningType = $provisioning_type,
                rm.actor = $actor,
                rm.isMultipleResult = $is_multiple_result,
                rm.updatedAt = datetime()
            MERGE (bc)-[:HAS_READMODEL]->(rm)
            RETURN rm {.id, .key, .name, .displayName, .description, .provisioningType, .actor, .isMultipleResult} as readmodel
            """
            result = session.run(
                query,
                key=key,
                name=name,
                display_name=display_name,
                bc_id=bc_id,
                description=description,
                provisioning_type=provisioning_type,
                actor=actor,
                is_multiple_result=is_multiple_result,
            )
            return dict(result.single()["readmodel"])


