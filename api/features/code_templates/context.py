"""ES 모델을 템플릿이 기대하는 렌더 컨텍스트로 편다.

템플릿은 `forEach: BoundedContext | Aggregate | Command | Enumeration |
ValueObject | View` 로 반복 대상을 고른다. 여기서는 그 여섯 대상별 목록을
만들어 두고, 렌더러는 목록을 돌며 항목 하나를 컨텍스트로 삼는다.

이름 변형(`nameCamelCase` / `namePascalCase` / `namePlural`)은 템플릿이
경로와 클래스 이름을 짓는 데 쓰므로 **영문 이름에서** 만든다. 한글
`displayName` 은 표시용이고 자바 식별자가 될 수 없다.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from api.features.deliverables.aggregate_export import build_aggregate_payloads
from api.features.deliverables.architecture_document import fetch_session_trees

_NON_WORD = re.compile(r"[^0-9A-Za-z]+")

# 우리 모델의 타입 이름을 기준 템플릿이 아는 자바 이름으로 옮긴다.
#
# 템플릿의 `isPrimitive` 헬퍼는 String·Integer·Long·Double·Float·Boolean·Date
# 만 원시로 본다. 여기 없는 이름은 값 객체로 취급돼
# `import ….store.domain.vo.boolean;` 같은 구문 오류가 나온다. 소문자
# 원시형과 UUID 가 그렇게 샜다.
_JAVA_TYPES = {
    "boolean": "Boolean", "int": "Integer", "integer": "Integer",
    "long": "Long", "double": "Double", "float": "Float",
    "string": "String", "char": "String", "text": "String",
    # UUID 는 자바 표준 타입이지만 템플릿의 원시 목록에 없다. 식별자는
    # 문자열로 내보내는 편이 JPA·DTO 양쪽에서 문제가 없다.
    "uuid": "String",
    "date": "Date", "datetime": "Date", "localdate": "Date",
    "localdatetime": "Date", "timestamp": "Date",
    # BigDecimal 도 UUID 와 같은 이유로 내보낸다 — 자바 표준 타입이지만
    # 템플릿의 원시 목록에 없어서, 그대로 두면 값 객체로 취급돼
    # `import ….store.domain.vo.BigDecimal;` 이라는 없는 클래스를 부른다.
    # 정밀도는 잃지만 컴파일되지 않는 코드보다는 낫다.
    "bigdecimal": "Double", "decimal": "Double", "number": "Double",
}


def java_type(name: str | None) -> str:
    """선언된 타입 이름을 자바 이름으로. 모르는 이름은 그대로 둔다 —
    값 객체·열거형의 이름일 수 있고, 그건 템플릿이 import 해야 맞다."""
    raw = (name or "").strip()
    if not raw:
        return "String"
    # `List<Foo>` 는 안쪽만 바꾼다.
    m = re.fullmatch(r"(List|Set|Collection)<(.+)>", raw)
    if m:
        return f"{m.group(1)}<{java_type(m.group(2))}>"
    return _JAVA_TYPES.get(raw.lower(), raw)


def _words(name: str) -> list[str]:
    """이름을 단어로 쪼갠다. 구분자와 대소문자 경계를 모두 본다."""
    spaced = _NON_WORD.sub(" ", name or "")
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", spaced)
    return [w for w in spaced.split() if w]


def pascal_case(name: str) -> str:
    return "".join(w[:1].upper() + w[1:] for w in _words(name))


def camel_case(name: str) -> str:
    p = pascal_case(name)
    return p[:1].lower() + p[1:] if p else ""


def pluralize(name: str) -> str:
    """영어 복수형 — 템플릿이 REST 경로에 쓴다. 규칙만 다룬다."""
    if not name:
        return ""
    lower = name.lower()
    if lower.endswith("y") and not lower.endswith(("ay", "ey", "iy", "oy", "uy")):
        return name[:-1] + "ies"
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return name + "es"
    return name + "s"


def _names(name: str) -> dict[str, str]:
    pascal = pascal_case(name)
    camel = camel_case(name)
    return {
        "name": name,
        "namePascalCase": pascal,
        "nameCamelCase": camel,
        "namePlural": pluralize(camel),
    }


def build_context(session_id: str, *, service_id: str) -> dict[str, Any]:
    """세션 하나의 렌더 컨텍스트.

    `service_id` 는 자바 패키지의 한 마디가 된다
    (`com.poscodx.<serviceId>.<boundedContext>`). 호출자가 정한다 — 기본값은
    세션 이름이지만 사용자가 바꿀 수 있어야 하므로 여기서 추측하지 않는다.
    """
    trees = fetch_session_trees(session_id)
    if not trees:
        return {"boundedContexts": [], "options": {"serviceId": service_id}}

    # Aggregate 상세(fieldDescriptors·entities)는 산출물 쪽 변환을 그대로 쓴다 —
    # 기준 구현의 "Export Aggregates" 와 같은 형식이라 템플릿이 바로 먹는다.
    exported = {a["id"]: a for a in build_aggregate_payloads(trees)["aggregates"] if a.get("id")}

    now = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    options = {"serviceId": service_id}

    bounded_contexts: list[dict[str, Any]] = []
    for tree in trees:
        bc_names = _names(tree.get("name") or "")
        bc_ref = {**bc_names, "id": tree.get("id"), "displayName": tree.get("displayName")}

        # `{{#attached 'View' this}}` — 기준 헬퍼가 `_type.endsWith('View')` 로
        # 거른다. ReadModel 이 어느 Aggregate 소속인지는 그래프에 없으므로
        # BC 의 것을 그 BC 의 Aggregate 에 함께 붙인다.
        views = [
            {**_names(v.get("name") or ""), "id": v.get("id"), "_type": "View",
             "type": "View", "displayName": v.get("displayName"),
             "boundedContext": bc_ref,
             "queryParameters": _query_parameters(v),
             "isMultipleResult": (v.get("isMultipleResult") or "") != "single result"}
            for v in tree.get("readmodels") or [] if v.get("name")
        ]

        aggregates = []
        for agg in tree.get("aggregates") or []:
            detail = exported.get(agg.get("id")) or {}
            agg_names = _names(agg.get("name") or "")
            commands = [
                {
                    **_names(c.get("name") or ""),
                    "id": c.get("id"),
                    "_type": "Command",
                    # `{{#commands}}` 블록 안에서도 패키지 경로를 지어야 한다.
                    # Handlebars 는 상위 스코프를 타지 않으므로 직접 싣는다.
                    "boundedContext": bc_ref,
                    "displayName": c.get("displayName"),
                    "description": c.get("description"),
                    # 기준 템플릿은 REST 매핑을 controllerInfo 에서 읽는다.
                    "controllerInfo": {"method": _http_method(c.get("name") or "")},
                    "parameters": _parameters(c),
                    # `{{#outgoing 'Event' this}}` — 이 커맨드가 내는 이벤트.
                    # 기준 헬퍼가 `outgoingRelations[].target.type` 을 보므로
                    # 그 모양 그대로 만든다.
                    "outgoingRelations": [
                        {"target": {**_names(e.get("name") or ""), "type": "Event",
                                    "_type": "Event", "id": e.get("id"),
                                    "displayName": e.get("displayName")}}
                        for e in c.get("events") or [] if e.get("name")
                    ],
                }
                for c in agg.get("commands") or []
            ]
            # 기준 구현은 enum·VO 를 `aggregateRoot.entities` 아래에 둔다.
            root = _with_field_names(detail.get("aggregateRoot")
                                     or {"fieldDescriptors": [], "entities": []})
            entities = root.get("entities") or []
            aggregates.append({
                **agg_names,
                "id": agg.get("id"),
                "displayName": agg.get("displayName"),
                "description": agg.get("description"),
                "boundedContext": bc_ref,
                "aggregateRoot": root,
                "commands": commands,
                # 템플릿이 최상위에서도 읽는다.
                "fieldDescriptors": root.get("fieldDescriptors") or [],
                "entities": entities,
                "enumerations": [e for e in entities if e.get("isEnum")],
                "valueObjects": [e for e in entities if e.get("isVO")],
                "queryParameters": [],
                "attached": views,
            })

        bounded_contexts.append({
            **bc_names,
            "id": tree.get("id"),
            "displayName": tree.get("displayName"),
            "description": tree.get("description"),
            "aggregates": aggregates,
            "views": views,
        })

    return {
        "boundedContexts": bounded_contexts,
        "options": options,
        "currentTimestamp": now,
    }


# 커맨드 이름에서 HTTP 메서드를 도출한다. 기준 구현의 관례와 같다 —
# 그래프에 근거가 없는 값이라 이름으로 추론하는 것 말고는 방법이 없다.
_METHOD_PREFIXES = (
    ("Delete", "DELETE"), ("Remove", "DELETE"), ("Cancel", "DELETE"),
    ("Create", "POST"), ("Register", "POST"), ("Add", "POST"), ("Submit", "POST"),
    ("Update", "PUT"), ("Change", "PUT"), ("Modify", "PUT"), ("Set", "PUT"),
)


def _http_method(command_name: str) -> str:
    for prefix, method in _METHOD_PREFIXES:
        if command_name.startswith(prefix):
            return method
    return "POST"


def _parameters(command: dict) -> list[dict[str, Any]]:
    """커맨드 입력 스키마를 필드 목록으로 편다."""
    schema = command.get("inputSchema")
    props = command.get("properties") or []
    out = []
    for p in props:
        if not p.get("name"):
            continue
        out.append({
            "name": p["name"],
            "className": java_type(p.get("type")),
            "isKey": bool(p.get("isKey")),
            "displayName": p.get("displayName"),
        })
    if not out and isinstance(schema, dict):
        for key, spec in (schema.get("properties") or {}).items():
            out.append({"name": key,
                        "className": java_type((spec or {}).get("type")),
                        "isKey": False, "displayName": None})
    return out


def _query_parameters(view: dict) -> list[dict[str, Any]]:
    """ReadModel 속성을 조회 파라미터로 편다 — View DTO 가 이것으로 만들어진다."""
    out = []
    for p in view.get("properties") or []:
        if not p.get("name"):
            continue
        out.append({
            **_names(p["name"]),
            "className": java_type(p.get("type")),
            "isKey": bool(p.get("isKey")),
            "displayName": p.get("displayName"),
        })
    return out


def _with_field_names(root: dict) -> dict:
    """fieldDescriptor 에 이름 변형을 얹는다.

    산출물 export 는 `name` 만 준다 — 그쪽 계약은 다른 소비자도 쓰므로 넓히지
    않고, 템플릿이 요구하는 `nameCamelCase`/`namePascalCase` 는 여기서 붙인다.
    없으면 `checkEntityField` 가 이름 자리에 `undefined` 를 찍는다.
    """
    def enrich(fields: list) -> list:
        out = []
        for f in fields or []:
            if not isinstance(f, dict):
                continue
            out.append({**_names(f.get("name") or ""), **f,
                        "className": java_type(f.get("className")),
                        "namePascalCase": pascal_case(f.get("name") or ""),
                        "nameCamelCase": camel_case(f.get("name") or "")})
        return out

    entities = []
    for e in root.get("entities") or []:
        entities.append({**e,
                         **_names(e.get("name") or ""),
                         "fieldDescriptors": enrich(e.get("fieldDescriptors") or []),
                         "items": [{**i, **_names(i.get("name") or "")}
                                   for i in (e.get("items") or []) if isinstance(i, dict)]})
    return {**root,
            "fieldDescriptors": enrich(root.get("fieldDescriptors") or []),
            "entities": entities}
