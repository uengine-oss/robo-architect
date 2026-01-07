"""
Change Planning: Impact Propagation (facade)

This module keeps the import surface stable for the planning graph while the implementation
is organized by business capability (settings / context graph / prompting / engine).
"""

from __future__ import annotations

from .impact_propagation_engine import propagate_impacts_node

__all__ = ["propagate_impacts_node"]


