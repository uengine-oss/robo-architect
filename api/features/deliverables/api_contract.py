"""Command / ReadModel 에서 REST 엔드포인트 계약을 규칙으로 도출한다.

새로운 AI 생성 단계를 두지 않는다. Command 는 이미 `category`(Create /
Update / Business Logic / Process / External Integration)와 소속 Aggregate 이름,
요청 필드(`properties` 또는 `inputSchema`)를 모두 갖고 있으므로, 경로와 메서드는
결정적으로 계산할 수 있다. LLM 을 쓰면 같은 입력에서 다른 경로가 나올 수 있어
납품 문서의 재현성이 깨진다.

경로 규칙은 기준 템플릿(local-msaez)의 CommandDefinitionPanel 관례를 따른다.

    isRestRepository (CRUD)  POST   /{aggregatePlural}
                             PUT    /{aggregatePlural}/{id}
                             DELETE /{aggregatePlural}/{id}
    custom controller        POST   /{aggregatePlural}/{id}/{commandName}

기준 구현이 커맨드 세그먼트를 `name.toLowerCase()` 로 만들어
`composeguidancemessage` 처럼 읽기 어려워지는 부분만 camelCase 로 바꿨다.
"""

from __future__ import annotations

import json
from typing import Any

# category → (HTTP method, 경로 형태)
#   collection  = /{plural}
#   item        = /{plural}/{id}
#   sub         = /{plural}/{id}/{command}
_CATEGORY_RULES = {
    "Create": ("POST", "collection"),
    "Update": ("PUT", "item"),
    "Delete": ("DELETE", "item"),
    "Business Logic": ("POST", "sub"),
    "Process": ("POST", "sub"),
}

# 인바운드 REST 엔드포인트가 아닌 category. 시스템이 외부를 호출하는 방향이라
# 경로·메서드를 붙이면 사실과 다른 문서가 된다. 목록에는 남기되 구분해 표기한다.
_OUTBOUND_CATEGORIES = {"External Integration"}

# category 가 비었거나 알 수 없을 때의 기본값. Event Storming 에서 Command 는
# 외부 트리거를 전제하므로 하위 리소스 POST 로 둔다.
_DEFAULT_RULE = ("POST", "sub")


def camel_case(name: str) -> str:
    """PascalCase 를 camelCase 로. 이미 camel 이거나 빈 값이면 그대로."""
    if not name:
        return ""
    return name[0].lower() + name[1:]


def pluralize(word: str) -> str:
    """경로 세그먼트용 단순 영어 복수화.

    도메인 이름은 대부분 규칙 복수형이라 사전 없이 처리한다. 불규칙 명사가
    필요해지면 예외 표를 여기에 추가한다.
    """
    if not word:
        return ""
    lower = word.lower()
    if lower.endswith("y") and len(word) > 1 and word[-2].lower() not in "aeiou":
        return word[:-1] + "ies"
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"


def _parameters(node: dict) -> list[dict]:
    """요청 파라미터를 뽑는다. `properties` 우선, 없으면 `inputSchema` 로 보완.

    커버리지 리뷰 §4.6 이 지적한 부분 — 템플릿이 `inputSchema` 만 파싱해서
    Property 만 있는 Command 의 요청 필드가 빈 값으로 나오던 문제를 여기서
    정규화한다.
    """
    props = node.get("properties") or []
    if props:
        return [
            {
                "name": p.get("name"),
                "type": p.get("type") or "String",
                "required": bool(p.get("isRequired")),
                "description": p.get("description") or "",
                "source": "properties",
            }
            for p in props
            if p.get("name")
        ]

    raw = node.get("inputSchema")
    if not raw:
        return []
    try:
        schema = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(schema, dict):
        return []

    params = []
    for key, spec in schema.items():
        if isinstance(spec, dict):
            type_name = spec.get("type") or "string"
        else:
            type_name = str(spec)
        params.append(
            {
                "name": key,
                "type": type_name,
                "required": False,
                "description": "",
                "source": "inputSchema",
            }
        )
    return params


def _command_endpoint(cmd: dict, aggregate_name: str) -> dict:
    category = (cmd.get("category") or "").strip()
    base = f"/{pluralize(camel_case(aggregate_name))}" if aggregate_name else ""
    name = cmd.get("name") or ""

    endpoint = {
        "commandId": cmd.get("id"),
        "commandName": name,
        "commandDisplayName": cmd.get("displayName") or name,
        "aggregate": aggregate_name,
        "category": category or "(미지정)",
        "description": cmd.get("description") or "",
        "parameters": _parameters(cmd),
        "emits": [e.get("displayName") or e.get("name") for e in (cmd.get("events") or [])],
        # 규칙으로 도출한 값이며 구현 확정이 아님을 문서가 표시할 수 있게 한다.
        "provenance": "derived",
    }

    if category in _OUTBOUND_CATEGORIES:
        # 외부 연동 호출 — 이 시스템이 제공하는 API 가 아니다.
        endpoint.update({"direction": "outbound", "method": "", "path": ""})
        return endpoint

    method, shape = _CATEGORY_RULES.get(category, _DEFAULT_RULE)
    if shape == "collection":
        path = base
    elif shape == "item":
        path = f"{base}/{{id}}"
    else:
        path = f"{base}/{{id}}/{camel_case(name)}"

    endpoint.update({"direction": "inbound", "method": method, "path": path})
    return endpoint


def _readmodel_endpoint(rm: dict) -> dict:
    name = rm.get("name") or ""
    base = f"/{pluralize(camel_case(name))}" if name else ""
    # 'list' / 'collection' 은 목록 조회, 그 외('single result')는 단건 조회.
    multiple = (rm.get("isMultipleResult") or "").strip().lower()
    is_list = multiple in ("list", "collection", "true", "multiple")

    return {
        "readModelId": rm.get("id"),
        "readModelName": name,
        "readModelDisplayName": rm.get("displayName") or name,
        "description": rm.get("description") or "",
        "method": "GET",
        "path": base if is_list else f"{base}/{{id}}",
        "resultType": "목록" if is_list else "단건",
        "actor": rm.get("actor") or "",
        "parameters": _parameters(rm),
        "direction": "inbound",
        "provenance": "derived",
    }


def _resolve_collisions(endpoints: list[dict]) -> int:
    """같은 (method, path) 로 겹친 엔드포인트를 하위 리소스 형태로 분리한다.

    한 Aggregate 에 Update 성격 Command 가 둘 이상이면 규칙상 모두
    `PUT /{복수형}/{id}` 가 되어 충돌한다. 이때는 커맨드 이름을 경로에 덧붙여
    구분한다(메서드는 유지). 문서에 같은 경로가 두 번 나와 어느 Command 를
    가리키는지 알 수 없게 두는 것보다 낫다.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for ep in endpoints:
        if ep["direction"] != "inbound":
            continue
        groups.setdefault((ep["method"], ep["path"]), []).append(ep)

    resolved = 0
    for (_, path), group in groups.items():
        if len(group) < 2:
            continue
        for ep in group:
            ep["path"] = f"{path}/{camel_case(ep['commandName'])}"
            ep["pathDisambiguated"] = True
            resolved += 1
    return resolved


def build_api_contracts(trees: list[dict]) -> dict[str, Any]:
    """BC full-tree 목록에서 API 명세를 조립한다.

    기준 템플릿의 API 명세 섹션이 요구하는 열(경로 / 메서드 / 연결 Command /
    설명 / 요청 파라미터)을 모두 채운다.
    """
    contexts = []
    total = inbound = outbound = queries = 0
    without_params = collisions = 0

    for tree in trees:
        command_endpoints = []
        for agg in tree.get("aggregates") or []:
            agg_name = agg.get("name") or ""
            for cmd in agg.get("commands") or []:
                ep = _command_endpoint(cmd, agg_name)
                command_endpoints.append(ep)
                total += 1
                if ep["direction"] == "outbound":
                    outbound += 1
                else:
                    inbound += 1
                if not ep["parameters"]:
                    without_params += 1

        collisions += _resolve_collisions(command_endpoints)

        query_endpoints = [_readmodel_endpoint(rm) for rm in (tree.get("readmodels") or [])]
        queries += len(query_endpoints)

        contexts.append(
            {
                "bcId": tree.get("id"),
                "bcName": tree.get("displayName") or tree.get("name"),
                "commandEndpoints": sorted(command_endpoints, key=lambda e: (e["aggregate"], e["commandName"])),
                "queryEndpoints": sorted(query_endpoints, key=lambda e: e["readModelName"]),
            }
        )

    return {
        "contexts": contexts,
        "convention": (
            "Command 의 category 와 소속 Aggregate 이름으로 도출한 규칙 기반 계약입니다. "
            "Create=POST /{복수형}, Update=PUT /{복수형}/{id}, "
            "그 외 Command=POST /{복수형}/{id}/{commandName}, "
            "ReadModel=GET /{복수형}[/{id}]. External Integration 은 외부 호출이라 "
            "제공 API 가 아닙니다."
        ),
        "summary": {
            "commands": total,
            "inboundCommands": inbound,
            "outboundCommands": outbound,
            "queries": queries,
            "commandsWithoutParameters": without_params,
            "pathCollisionsResolved": collisions,
        },
    }
