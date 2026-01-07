"""
Change Planning Workflow (facade)

Business capability: generate and revise change plans for user story edits.

This module is intentionally thin and re-exports the feature entry point(s).
"""

from __future__ import annotations

from .change_planning_api import run_change_planning

__all__ = ["run_change_planning"]


