from __future__ import annotations

from typing import Any, Dict


def extract_json_from_llm_text(text: str) -> str:
    """
    Extract JSON payload from an LLM response that may contain markdown fences.
    """
    if not text:
        return ""
    content = text
    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0]
    return content.strip()


def format_subgraph_for_prompt(center_id: str, subgraph: Dict[str, Any], max_nodes: int = 60, max_rels: int = 120) -> str:
    nodes = subgraph.get("nodes") or []
    rels = subgraph.get("relationships") or []
    nodes = nodes[:max_nodes]
    rels = rels[:max_rels]

    node_lines = []
    for n in nodes:
        node_lines.append(
            f"- {n.get('type','?')} [{n.get('id','?')}]: {n.get('name','')} (BC: {n.get('bcName') or 'Unknown'})"
        )

    rel_lines = []
    for r in rels:
        rel_lines.append(f"- {r.get('source')} -{r.get('type')}-> {r.get('target')}")

    return (
        f"### Center: {center_id}\n"
        f"Nodes ({len(nodes)}):\n" + ("\n".join(node_lines) if node_lines else "None") + "\n\n"
        f"Relationships ({len(rels)}):\n" + ("\n".join(rel_lines) if rel_lines else "None")
    )


def propagation_prompt(
    *,
    edited_user_story: Dict[str, Any],
    change_description: str,
    centers_context_text: str,
    max_new: int,
) -> str:
    return f"""You are acting as a graph-based impact propagation engine for an Event Storming model.

Your job is to identify additional impacted nodes (2nd~N-th order) caused by the modified User Story.
You MUST only propose candidates that exist in the provided context subgraphs (by id).

## Modified User Story
Role: {edited_user_story.get('role', 'user')}
Action: {edited_user_story.get('action', '')}
Benefit: {edited_user_story.get('benefit', '')}
Change description: {change_description}

## Context subgraphs (2-hop, whitelist relationships, includes BC context)
{centers_context_text}

## Rules
- Propose at most {max_new} NEW candidates (ids not already seen) this round.
- For each candidate, include a confidence in [0,1].
- Provide at least 1 evidence path string using relationship types, e.g.:
  CMD-X -EMITS-> EVT-Y -TRIGGERS-> POL-Z
- If evidence is weak or the candidate is speculative, set lower confidence (<0.70).
- suggested_change_type should be one of: rename, update, create, connect, delete, unknown.

## Output JSON (exactly this shape)
{{
  "candidates": [
    {{
      "id": "NODE-ID",
      "type": "Command|Event|Policy|Aggregate|BoundedContext|UserStory|...",
      "name": "Node name",
      "confidence": 0.0,
      "reason": "Why this node is impacted",
      "evidence_paths": ["..."],
      "suggested_change_type": "update"
    }}
  ]
}}
"""


