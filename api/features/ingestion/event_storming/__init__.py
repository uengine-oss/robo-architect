"""
Event Storming LangGraph Agent

A LangGraph-based workflow for generating Event Storming models from User Stories.

Workflow:
1. Load User Stories from Neo4j
2. Identify Bounded Context candidates (one by one)
3. Break down User Stories within each Bounded Context
4. Extract Aggregates from breakdown
5. Extract Commands from Aggregates
6. Extract Events from Commands
7. Identify Policies for cross-BC communication

Human-in-the-loop checkpoints are provided for review and approval.

## 왜 `.graph` 를 **지금** 가져오지 않는가 (2026-10-07, DEAD-1 ①)

이 패키지에서 앱이 실제로 쓰는 것은 다섯이다 — `neo4j_client` · `neo4j_ops` ·
`prompts` · `state` · `structured_outputs`. 그런데 `__init__` 이 `.graph` 를 즉시
가져오고, `.graph` 가 `.nodes`(파사드)를, 파사드가 `nodes_*` 열넷을 끌고 왔다.
그래서 **`structured_outputs` 에서 한 이름만 가져와도** 앱에서 돌지 않는 2,819줄이
같이 올라왔다 — 패키지 `__init__` 은 어느 하위 모듈을 가져와도 먼저 실행된다.

`PEP 562` 의 모듈 `__getattr__` 로 **부를 때** 가져온다. `from … import
create_event_storming_graph` 는 그대로 동작하므로 **밖에서 보이는 모양은 같다**
(지금 저장소 안에 그 호출자는 cli 뿐이고, 그 cli 는 앱이 부르지 않는다).

고치기 전에 셌고 고친 뒤 다시 셌다 — `phases.aggregates` 하나를 가져올 때
올라오는 `event_storming.*` 모듈 수로 잰다.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 타입 검사와 편집기에는 그대로 보인다
    from .graph import create_event_storming_graph
    from .state import EventStormingState

__all__ = ["create_event_storming_graph", "EventStormingState"]

_LAZY = {
    "create_event_storming_graph": ".graph",
    "EventStormingState": ".state",
}


def __getattr__(name: str) -> Any:
    """부를 때 가져온다. **없는 이름은 평소처럼 `AttributeError`** 다."""
    module_name = _LAZY.get(name)
    if module_name is None:
        raise AttributeError("module %r has no attribute %r" % (__name__, name))
    from importlib import import_module

    return getattr(import_module(module_name, __name__), name)


def __dir__() -> list[str]:
    return sorted(__all__)
