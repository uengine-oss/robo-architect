"""
Ingestion workflow phases (feature-local).

Each phase is an async generator that yields `ProgressEvent` objects and mutates
`IngestionWorkflowContext` with artifacts needed by downstream phases.
"""


