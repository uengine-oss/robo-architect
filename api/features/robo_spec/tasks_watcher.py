"""watchfiles-based watcher over <workspace>/specs/**/tasks.md.

Parses the `<!-- @robo elementId=... -->` markers on each checkbox, diffs
checkbox state against last-known state, and publishes per-element
progress events onto the in-process SSE bus. Skeleton populated by
T027..T028 in a subsequent /speckit-implement pass (US2).
"""

from __future__ import annotations
