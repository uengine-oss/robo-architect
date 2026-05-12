"""Deterministic topological sort for ``specs/frontend/ui-flow.md`` (research D8).

The frontend renderer needs to linearise a DAG of (BC, User Story, UI) nodes
connected by intra-story, intra-BC, and cross-BC edges. We use Kahn's
algorithm with a stable tiebreaker so two runs against the same graph
produce byte-identical output (SC-010).

The sequencer is a **pure algorithm**: opaque string keys + edge pairs + a
tiebreaker callable. The caller (``repository.load_frontend_composition``)
owns the graph walk and the per-node metadata.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable, Iterable


def sequence_topological(
    node_keys: Iterable[str],
    edges: Iterable[tuple[str, str]],
    tiebreaker: Callable[[str], tuple],
) -> tuple[list[str], list[tuple[str, str]]]:
    """Topologically sort ``node_keys`` honouring ``edges`` and ``tiebreaker``.

    Args:
        node_keys: all node identifiers.
        edges: directed edges as ``(src, dst)`` pairs. Edges referencing
            unknown nodes or self-loops are silently dropped. Duplicates are
            de-duped.
        tiebreaker: maps a node key to an orderable tuple. Used both for
            picking the next ready node (smallest first) and for choosing
            which back-edge to remove when breaking a cycle (largest on the
            destination, largest on the source among that destination's
            incoming edges).

    Returns:
        Tuple of:
        - ``ordered``: every node key in topological order. Cycles, if any,
          are broken by removing back-edges; nodes are never dropped.
        - ``cycle_broken``: the list of ``(src, dst)`` edges removed to
          linearise; one ``ui_flow_cycle_broken`` warning per entry.

    The algorithm is Kahn's with a deterministic tiebreaker (``sorted`` over
    ``ready`` is stable when the key is unique per node). For cycle
    breaking, see research D8 step 6.
    """
    nodes = list(node_keys)
    node_set = set(nodes)
    if not node_set:
        return [], []

    out_adj: dict[str, list[str]] = defaultdict(list)
    in_deg: dict[str, int] = {k: 0 for k in node_set}
    edge_set: set[tuple[str, str]] = set()
    for src, dst in edges:
        if src not in node_set or dst not in node_set or src == dst:
            continue
        if (src, dst) in edge_set:
            continue
        edge_set.add((src, dst))
        out_adj[src].append(dst)
        in_deg[dst] += 1

    ordered: list[str] = []
    cycle_broken: list[tuple[str, str]] = []
    remaining: set[str] = set(node_set)

    while remaining:
        ready = sorted(
            (k for k in remaining if in_deg[k] == 0),
            key=tiebreaker,
        )
        if ready:
            nxt = ready[0]
            ordered.append(nxt)
            remaining.discard(nxt)
            for dst in out_adj[nxt]:
                if dst in remaining:
                    in_deg[dst] -= 1
            continue

        # Cycle. Pick the destination with the largest tiebreaker among the
        # still-remaining nodes (whichever node "feels last" in the natural
        # ordering is the safest to receive an edge removal). Then drop the
        # incoming edge from the largest-tiebreaker source.
        cycle_dst = max(remaining, key=tiebreaker)
        candidates = [src for (src, dst) in edge_set if dst == cycle_dst and src in remaining]
        if not candidates:
            # Defensive: should never happen because in_deg > 0 implies at
            # least one incoming edge from `remaining`. Bail to avoid
            # spinning forever.
            break
        cycle_src = max(candidates, key=tiebreaker)
        edge_set.discard((cycle_src, cycle_dst))
        out_adj[cycle_src] = [k for k in out_adj[cycle_src] if k != cycle_dst]
        in_deg[cycle_dst] -= 1
        cycle_broken.append((cycle_src, cycle_dst))

    return ordered, cycle_broken


def _priority_index(priority: str | None) -> int:
    """Map User Story priority ``"P1"`` .. ``"P5"`` to a sortable integer.

    Unset priority sorts after every set priority (it loses every
    tiebreaker against P1..P5).
    """
    if not priority:
        return 99
    if priority.startswith("P") and priority[1:].isdigit():
        return int(priority[1:])
    return 99


def build_tiebreaker(
    bc_index: dict[str, int],
    story_index: dict[str, tuple[int, str | None]],
    ui_index: dict[str, int],
) -> Callable[[str], tuple]:
    """Build the per-node tiebreaker callable used by the sequencer.

    Tiebreaker tuple, per research D8 step 5:
    ``(bc_insertion_index, user_story_priority, user_story_insertion_index, ui_order_in_story)``.

    Node keys are ``"<bc_id>/<user_story_id>/<ui_id>"`` strings.

    Args:
        bc_index: ``bc_id -> insertion index``.
        story_index: ``story_id -> (insertion index within its BC, priority str)``.
        ui_index: per-story-and-ui composite key
            (``"<story_id>/<ui_id>"``) → index within the story's wireframe
            order.
    """

    def _key(node: str) -> tuple:
        parts = node.split("/", 2)
        if len(parts) != 3:
            # Defensive fallback.
            return (99, 99, 99, 99, node)
        bc_id, story_id, ui_id = parts
        story_insert_idx, priority = story_index.get(story_id, (99, None))
        return (
            bc_index.get(bc_id, 99),
            _priority_index(priority),
            story_insert_idx,
            ui_index.get(f"{story_id}/{ui_id}", 99),
            # Final stabiliser — keeps `sorted` total even if two stories
            # share every preceding key.
            node,
        )

    return _key
