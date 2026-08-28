"""Aggregate 구조를 기준 템플릿 호환 JSON 으로 내보낸다.

기준 기능: `local-msaez` `CodeGenerator.vue` 의 `exportAggregatesWord()`.
Aggregate 요소를 단순화한 JSON 배열로 만들어 내려받게 하는 기능으로, 코드
생성기나 외부 도구가 소비할 수 있는 형태다.

기준 구현의 payload 구조와 키 이름을 그대로 유지한다.

    {
      "id", "name", "displayName",
      "namePlural", "namePascalCase", "nameCamelCase",
      "boundedContextId", "boundedContextName",
      "aggregateRoot": {
        "fieldDescriptors": [...],
        "entities": [...]
      }
    }

기준 구현과 마찬가지로 빈 값은 재귀적으로 제거한다. 키가 없는 것과 값이 빈
것을 구분하지 않는 편이 소비자 쪽 분기를 단순하게 만든다.
"""

from __future__ import annotations

from typing import Any

from api.features.deliverables.api_contract import camel_case, pluralize

# 기준 구현 `_simplifyFieldDescriptors` 의 allowedKeys. 이 순서대로 채운다.
FIELD_KEYS = [
    "name",
    "className",
    "isKey",
    "isNullable",
    "isUnique",
    "defaultValue",
    "length",
    "precision",
    "scale",
    "description",
    "referenceClass",
    "isVO",
    "label",
    "isList",
    "classId",
    "displayName",
]

# 속성 타입이 이 값이면 구체 타입이 아니다. Value Object / Enumeration 이름과
# 맞춰볼 대상.
_GENERIC_TYPES = {"", "object", "string", "any"}


def omit_empty(value: Any) -> Any:
    """빈 값을 재귀적으로 제거한다 (기준 구현 `_omitEmptyValues` 대응).

    None, 빈 문자열, 빈 dict, 빈 list 를 버린다. `False` 와 `0` 은 의미 있는
    값이므로 남긴다 — `isKey: false` 를 지우면 소비자가 "키 여부 미상"과
    "키 아님"을 구분할 수 없다.
    """
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            reduced = omit_empty(item)
            if reduced is None:
                continue
            if isinstance(reduced, (dict, list)) and not reduced:
                continue
            if reduced == "":
                continue
            cleaned[key] = reduced
        return cleaned

    if isinstance(value, list):
        out = []
        for item in value:
            reduced = omit_empty(item)
            if reduced is None:
                continue
            if isinstance(reduced, (dict, list)) and not reduced:
                continue
            if reduced == "":
                continue
            out.append(reduced)
        return out

    return value


def _pascal(name: str) -> str:
    if not name:
        return ""
    return name[0].upper() + name[1:]


def _field(prop: dict, reference_class: str | None, is_vo: bool) -> dict:
    """Aggregate Property 를 기준 구현의 fieldDescriptor 로 변환한다.

    `isRequired` 는 `isNullable` 의 반대다 — 기준 구현이 nullable 기준으로
    표현하므로 뒤집어 맞춘다.
    """
    field = {
        "name": prop.get("name"),
        "className": reference_class or prop.get("type") or "String",
        "isKey": bool(prop.get("isKey")),
        "isNullable": not bool(prop.get("isRequired")),
        "description": prop.get("description"),
        "displayName": prop.get("displayName"),
    }
    if reference_class:
        field["referenceClass"] = reference_class
    if is_vo:
        field["isVO"] = True
    return {k: field[k] for k in FIELD_KEYS if k in field}


def _dedup_fields(fields: list[dict]) -> list[dict]:
    """기준 구현과 동일한 중복 제거 기준 — name::className::isKey."""
    seen = set()
    out = []
    for field in fields:
        key = f"{field.get('name') or ''}::{field.get('className') or ''}::{1 if field.get('isKey') else 0}"
        if key in seen:
            continue
        seen.add(key)
        out.append(field)
    return out


def _enum_entity(enum: dict) -> dict:
    """Enumeration → entity(isEnum).

    항목이 문자열 리스트이므로 `name` 과 `value` 를 같은 값으로 채운다. 소비자에
    따라 둘 중 하나만 읽기 때문에 양쪽을 모두 둔다.
    """
    items = [{"name": item, "value": item} for item in (enum.get("items") or []) if item]
    return {
        "name": enum.get("name"),
        "displayName": enum.get("displayName"),
        "isEnum": True,
        "items": items,
    }


def _vo_entity(vo: dict) -> dict:
    """Value Object → entity(isVO)."""
    fields = [
        {
            "name": f.get("name"),
            "className": f.get("type") or "String",
            "isNullable": True,
        }
        for f in (vo.get("fields") or [])
        if f.get("name")
    ]
    entity = {
        "name": vo.get("name"),
        "displayName": vo.get("displayName"),
        "isVO": True,
        "fieldDescriptors": _dedup_fields(fields),
    }
    # 다른 Aggregate 를 참조하는 VO 는 그 사실을 남긴다.
    if vo.get("referencedAggregateName"):
        entity["referenceClass"] = vo["referencedAggregateName"]
    return entity


def _resolve_reference(prop: dict, by_name: dict[str, str]) -> tuple[str | None, bool]:
    """구체 타입이 없는 속성을 같은 이름의 VO / Enumeration 에 연결한다.

    Aggregate Property 의 `type` 이 `Object` / `String` 같은 일반 타입으로만
    저장되는 경우가 있어, 그대로 내보내면 코드 생성기가 쓸 수 없다. 속성 이름을
    PascalCase 로 바꿔 **정확히 일치하는** VO/Enum 이 있을 때만 연결한다.
    부분 일치나 유사도 추정은 하지 않는다 — 틀린 연결을 만드는 쪽이 빈 값보다
    나쁘다.
    """
    type_name = (prop.get("type") or "").strip()
    if type_name.lower() not in _GENERIC_TYPES:
        # 이미 구체 타입이면 그대로 둔다.
        return (type_name if type_name in by_name else None, by_name.get(type_name) == "vo")

    candidate = _pascal(prop.get("name") or "")
    kind = by_name.get(candidate)
    if not kind:
        return None, False
    return candidate, kind == "vo"


def build_aggregate_payloads(trees: list[dict]) -> dict[str, Any]:
    """BC full-tree 목록에서 Aggregate JSON 배열을 만든다."""
    aggregates: list[dict] = []
    resolved_refs = 0
    total_fields = 0

    for tree in trees:
        bc_id = tree.get("id")
        bc_name = tree.get("displayName") or tree.get("name")

        for agg in tree.get("aggregates") or []:
            name = agg.get("name") or ""
            enums = agg.get("enumerations") or []
            vos = agg.get("valueObjects") or []

            # 이름 → 종류. 속성의 참조 타입 해석에 쓴다.
            by_name: dict[str, str] = {}
            for e in enums:
                if e.get("name"):
                    by_name[e["name"]] = "enum"
            for v in vos:
                if v.get("name"):
                    by_name[v["name"]] = "vo"

            fields = []
            for prop in agg.get("properties") or []:
                if not prop.get("name"):
                    continue
                reference_class, is_vo = _resolve_reference(prop, by_name)
                if reference_class:
                    resolved_refs += 1
                fields.append(_field(prop, reference_class, is_vo))
            fields = _dedup_fields(fields)
            total_fields += len(fields)

            entities = [_enum_entity(e) for e in enums if e.get("name")]
            entities += [_vo_entity(v) for v in vos if v.get("name")]

            payload = {
                "id": agg.get("id"),
                "name": name,
                "displayName": agg.get("displayName"),
                "namePlural": pluralize(camel_case(name)),
                "namePascalCase": _pascal(name),
                "nameCamelCase": camel_case(name),
                "boundedContextId": bc_id,
                "boundedContextName": bc_name,
                "aggregateRoot": {
                    "fieldDescriptors": fields,
                    "entities": entities,
                },
                # 기준 구현에는 없지만 Robo Architect 가 보유한 설계 정보.
                # 키 이름이 명확하므로 기존 소비자를 깨지 않는다.
                "invariants": [
                    inv.get("declaration") or inv.get("name")
                    for inv in (agg.get("invariants") or [])
                ],
                "exceptions": agg.get("exceptions") or [],
            }
            aggregates.append(omit_empty(payload))

    return {
        "aggregates": aggregates,
        "summary": {
            "aggregates": len(aggregates),
            "fields": total_fields,
            "resolvedReferences": resolved_refs,
        },
    }
