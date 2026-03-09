from __future__ import annotations

import time

from api.platform.neo4j import get_session
from api.platform.observability.smart_logger import SmartLogger


def fetch_bc_data(bc_id: str) -> dict | None:
    t0 = time.perf_counter()
    query = """
    MATCH (bc:BoundedContext {id: $bc_id})
    
    // Step 1: Aggregate Properties and Additional Info
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(agg:Aggregate)
    WITH bc, agg
    OPTIONAL MATCH (agg)-[:HAS_PROPERTY]->(aggProp:Property)
    WITH bc, agg, collect(DISTINCT aggProp {.id, .name, .type, .isKey, .isForeignKey, .description, .fkTargetHint}) as aggProps
    
    // Step 2: Commands with Properties and Additional Info
    OPTIONAL MATCH (agg)-[:HAS_COMMAND]->(cmd:Command)
    WITH bc, agg, aggProps, cmd
    OPTIONAL MATCH (cmd)-[:HAS_PROPERTY]->(cmdProp:Property)
    WITH bc, agg, aggProps, cmd, collect(DISTINCT cmdProp {.id, .name, .type, .isRequired, .description}) as cmdProps
    WITH bc, agg, aggProps, cmd, cmdProps,
         cmd.category as cmdCategory,
         cmd.inputSchema as cmdInputSchema,
         cmd.description as cmdDescription
    
    // Step 3: Events with Properties and Additional Info
    OPTIONAL MATCH (cmd)-[:EMITS]->(evt:Event)
    WITH bc, agg, aggProps, cmd, cmdProps, cmdCategory, cmdInputSchema, cmdDescription, evt
    OPTIONAL MATCH (evt)-[:HAS_PROPERTY]->(evtProp:Property)
    WITH bc, agg, aggProps, cmd, cmdProps, cmdCategory, cmdInputSchema, cmdDescription, evt, 
         collect(DISTINCT evtProp {.id, .name, .type, .description}) as evtProps,
         evt.schema as evtSchema,
         evt.description as evtDescription
    
    // Step 4: Group Commands and Events by Aggregate
    WITH bc, agg, aggProps,
         collect(DISTINCT {
             id: cmd.id, 
             name: cmd.name, 
             actor: cmd.actor, 
             category: cmdCategory,
             inputSchema: cmdInputSchema,
             description: cmdDescription,
             properties: cmdProps
         }) as commands,
         collect(DISTINCT {
             id: evt.id, 
             name: evt.name, 
             version: evt.version, 
             schema: evtSchema,
             description: evtDescription,
             properties: evtProps
         }) as events
    WITH bc, collect(DISTINCT {
        id: agg.id,
        name: agg.name,
        rootEntity: agg.rootEntity,
        invariants: agg.invariants,
        enumerations: agg.enumerations,
        valueObjects: agg.valueObjects,
        properties: aggProps,
        commands: commands,
        events: events
    }) as aggData

    // Step 5: ReadModels with Properties and Additional Info
    OPTIONAL MATCH (bc)-[:HAS_READMODEL]->(rm:ReadModel)
    WITH bc, aggData, rm
    OPTIONAL MATCH (rm)-[:HAS_PROPERTY]->(rmProp:Property)
    WITH bc, aggData, rm, collect(DISTINCT rmProp {.id, .name, .type, .description}) as rmProps
    WITH bc, aggData, collect(DISTINCT {
        id: rm.id,
        name: rm.name,
        description: rm.description,
        provisioningType: rm.provisioningType,
        actor: rm.actor,
        isMultipleResult: rm.isMultipleResult,
        properties: rmProps
    }) as rmData

    // Step 6: Policies with Cross-BC Information
    OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol:Policy)
    WITH bc, aggData, rmData, pol
    OPTIONAL MATCH (triggerEvt:Event)-[:TRIGGERS]->(pol)
    OPTIONAL MATCH (triggerEvt)<-[:EMITS]-(:Command)<-[:HAS_COMMAND]-(:Aggregate)<-[:HAS_AGGREGATE]-(triggerEvtBC:BoundedContext)
    OPTIONAL MATCH (pol)-[:INVOKES]->(invokeCmd:Command)
    OPTIONAL MATCH (invokeCmd)<-[:HAS_COMMAND]-(:Aggregate)<-[:HAS_AGGREGATE]-(invokeCmdBC:BoundedContext)
    WITH bc, aggData, rmData, collect(DISTINCT {
        id: pol.id,
        name: pol.name,
        description: pol.description,
        triggerEventId: triggerEvt.id,
        triggerEventName: triggerEvt.name,
        triggerEventBCId: triggerEvtBC.id,
        triggerEventBCName: triggerEvtBC.name,
        invokeCommandId: invokeCmd.id,
        invokeCommandName: invokeCmd.name,
        invokeCommandBCId: invokeCmdBC.id,
        invokeCommandBCName: invokeCmdBC.name
    }) as polData

    // Step 7: UI Wireframes
    OPTIONAL MATCH (bc)-[:HAS_UI]->(ui:UI)
    WITH bc, aggData, rmData, polData, collect(DISTINCT ui {.id, .name, .description, .template, .attachedToId, .attachedToType, .attachedToName}) as uiData

    // Step 8: GWT
    OPTIONAL MATCH (bc)-[:HAS_AGGREGATE]->(:Aggregate)-[:HAS_COMMAND]->(cmd2:Command)-[:HAS_GWT]->(gwt:GWT)
    WITH bc, aggData, rmData, polData, uiData, collect(DISTINCT gwt {.id, .parentType, .parentId, .givenRef, .whenRef, .thenRef, .testCases}) as gwtData1
    OPTIONAL MATCH (bc)-[:HAS_POLICY]->(pol2:Policy)-[:HAS_GWT]->(gwt2:GWT)
    WITH bc, aggData, rmData, polData, uiData, gwtData1, collect(DISTINCT gwt2 {.id, .parentType, .parentId, .givenRef, .whenRef, .thenRef, .testCases}) as gwtData2
    WITH bc, aggData, rmData, polData, uiData, gwtData1 + gwtData2 as gwtData

    RETURN {
        id: bc.id,
        name: bc.name,
        description: bc.description,
        aggregates: [a IN aggData WHERE a.id IS NOT NULL],
        readmodels: [r IN rmData WHERE r.id IS NOT NULL],
        policies: [p IN polData WHERE p.id IS NOT NULL],
        uis: [u IN uiData WHERE u.id IS NOT NULL],
        gwts: [g IN gwtData WHERE g.id IS NOT NULL]
    } as bc_data
    """

    with get_session() as session:
        result = session.run(query, bc_id=bc_id)
        record = result.single()
        if record:
            bc_data = dict(record["bc_data"])
            SmartLogger.log(
                "INFO",
                "PRD: fetched BC data from Neo4j.",
                category="api.prd.neo4j.fetch_bc",
                params={
                    "bc_id": bc_id,
                    "duration_ms": int((time.perf_counter() - t0) * 1000),
                    # For reproducibility, log the resolved data (SmartLogger will offload to detail files
                    # when the payload is large).
                    "bc_data": bc_data,
                },
            )
            return bc_data
    SmartLogger.log(
        "WARNING",
        "PRD: BC not found while fetching data.",
        category="api.prd.neo4j.fetch_bc.not_found",
        params={"bc_id": bc_id, "duration_ms": int((time.perf_counter() - t0) * 1000)},
    )
    return None


def get_bcs_from_nodes(node_ids: list[str] | None = None) -> list[dict]:
    t0 = time.perf_counter()
    
    # If no node_ids provided, get all BCs
    if not node_ids or len(node_ids) == 0:
        query = """
        MATCH (bc:BoundedContext)
        RETURN collect(bc.id) as bc_ids
        """
        with get_session() as session:
            result = session.run(query)
            record = result.single()
            bc_ids: list[str] = record["bc_ids"] or [] if record else []
    else:
        query = """
        // Direct BC nodes
        UNWIND $node_ids as nodeId
        OPTIONAL MATCH (bc:BoundedContext {id: nodeId})
        WITH collect(DISTINCT bc.id) as directBCs

        // BCs containing the nodes
        UNWIND $node_ids as nodeId
        OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE|HAS_POLICY|HAS_READMODEL|HAS_UI*1..3]->(n {id: nodeId})
        WITH directBCs, collect(DISTINCT bc.id) as containingBCs

        // BCs for Commands (via Aggregate)
        UNWIND $node_ids as nodeId
        OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg:Aggregate)-[:HAS_COMMAND]->(cmd:Command {id: nodeId})
        WITH directBCs, containingBCs, collect(DISTINCT bc.id) as cmdBCs

        // BCs for Events (via Command)
        UNWIND $node_ids as nodeId
        OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg2:Aggregate)-[:HAS_COMMAND]->(cmd2:Command)-[:EMITS]->(evt:Event {id: nodeId})
        WITH directBCs, containingBCs, cmdBCs, collect(DISTINCT bc.id) as evtBCs

        // BCs for ReadModels
        UNWIND $node_ids as nodeId
        OPTIONAL MATCH (bc:BoundedContext)-[:HAS_READMODEL]->(rm:ReadModel {id: nodeId})
        WITH directBCs, containingBCs, cmdBCs, evtBCs, collect(DISTINCT bc.id) as rmBCs

        // BCs for Properties (via parent)
        UNWIND $node_ids as nodeId
        OPTIONAL MATCH (prop:Property {id: nodeId})
        OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg3:Aggregate)-[:HAS_PROPERTY]->(prop)
        OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg4:Aggregate)-[:HAS_COMMAND]->(cmd3:Command)-[:HAS_PROPERTY]->(prop)
        OPTIONAL MATCH (bc:BoundedContext)-[:HAS_AGGREGATE]->(agg5:Aggregate)-[:HAS_COMMAND]->(cmd4:Command)-[:EMITS]->(evt2:Event)-[:HAS_PROPERTY]->(prop)
        OPTIONAL MATCH (bc:BoundedContext)-[:HAS_READMODEL]->(rm2:ReadModel)-[:HAS_PROPERTY]->(prop)
        WITH directBCs, containingBCs, cmdBCs, evtBCs, rmBCs, collect(DISTINCT bc.id) as propBCs

        WITH directBCs + containingBCs + cmdBCs + evtBCs + rmBCs + propBCs as allBCIds
        UNWIND allBCIds as bcId
        WITH DISTINCT bcId WHERE bcId IS NOT NULL
        RETURN collect(bcId) as bc_ids
        """

        bc_ids: list[str] = []
        with get_session() as session:
            result = session.run(query, node_ids=node_ids)
            record = result.single()
            if record:
                bc_ids = record["bc_ids"] or []

    SmartLogger.log(
        "INFO",
        "PRD: resolved BC IDs from selected node IDs.",
        category="api.prd.neo4j.resolve_bcs",
        params={
            # For reproducibility, log full inputs; SmartLogger will offload large payloads to detail files.
            "inputs": {"node_ids": node_ids},
            "resolved_bc_ids": bc_ids,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        },
    )

    bcs: list[dict] = []
    for bc_id in bc_ids:
        bc_data = fetch_bc_data(bc_id)
        if bc_data:
            bcs.append(bc_data)
    return bcs


