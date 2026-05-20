"""DDD-for-SDD artifact generation from the event-storming graph.

Project the Neo4j event-storming graph into the "DDD for SDD" artifact set
under ``specs/bounded-contexts/<bc-slug>/`` and ``specs/context-map.md``.
Read-only: the graph is the single source of truth — this feature never
mutates Neo4j and never calls the Figma API.

See ``specs/022-spec-generation-from-event-storming/`` for the feature plan.
"""
