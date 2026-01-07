from __future__ import annotations

from typing import Any


class GraphAnalysisOps:
    # =========================================================================
    # Graph Traversal & Analysis
    # =========================================================================

    def get_full_event_chain(self) -> list[dict[str, Any]]:
        """Get the full event chain: Command -> Event -> Policy -> Command."""
        query = """
        MATCH (cmd1:Command)-[:EMITS]->(evt:Event)-[:TRIGGERS]->(pol:Policy)-[:INVOKES]->(cmd2:Command)
        MATCH (bc1:BoundedContext)-[:HAS_AGGREGATE]->(agg1:Aggregate)-[:HAS_COMMAND]->(cmd1)
        MATCH (bc2:BoundedContext)-[:HAS_POLICY]->(pol)
        RETURN {
            source_bc: bc1.name,
            source_command: cmd1.name,
            event: evt.name,
            target_bc: bc2.name,
            policy: pol.name,
            target_command: cmd2.name
        } as chain
        """
        with self.session() as session:
            result = session.run(query)
            return [dict(record["chain"]) for record in result]

    def get_impact_analysis(self, event_name: str) -> dict[str, Any]:
        """Analyze the impact of changing a specific event."""
        query = """
        MATCH (evt:Event {name: $event_name})-[:TRIGGERS]->(pol:Policy)<-[:HAS_POLICY]-(bc:BoundedContext)
        MATCH (pol)-[:INVOKES]->(cmd:Command)
        WITH evt, collect({bc: bc.name, policy: pol.name, command: cmd.name}) as impacts
        RETURN {
            event: evt.name,
            version: evt.version,
            affected_count: size(impacts),
            impacts: impacts
        } as analysis
        """
        with self.session() as session:
            result = session.run(query, event_name=event_name)
            record = result.single()
            return dict(record["analysis"]) if record else {}

    def get_graph_statistics(self) -> dict[str, int]:
        """Get statistics about the current graph."""
        query = """
        MATCH (n)
        WITH labels(n)[0] as label, count(n) as count
        RETURN collect({label: label, count: count}) as nodes
        """
        with self.session() as session:
            result = session.run(query)
            nodes = result.single()["nodes"]
            return {item["label"]: item["count"] for item in nodes}


