"""Robo Spec — MCP bridge + HTTP routes for the /robo-* Claude Code skill suite.

See specs/029-robo-spec-skills/ for the full design. This package ships:
- An in-process MCP server mounted at /mcp (streamable-HTTP transport).
- HTTP routes E2..E6 (the E1 extension lives in api/features/claude_code/).
- A watchfiles-based watcher that pushes per-element progress over SSE.
- Neo4j CRUD for :ImplementationFile nodes + [:IMPLEMENTED_IN] relationships.
"""
