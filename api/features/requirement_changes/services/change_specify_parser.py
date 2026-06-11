from __future__ import annotations

import json

from api.features.requirement_changes.services.effect_analyzer import create_effects_from_analysis
from api.platform.observability.smart_logger import SmartLogger


def parse_and_apply_specify_output(change_id: str, stdout: str) -> int:
    """robo-change-specify 출력 JSON을 파싱하여 EFFECT 관계를 생성한다. 생성된 관계 수 반환."""
    try:
        # JSON 블록만 추출 (```json ... ``` 또는 순수 JSON)
        text = stdout.strip()
        if "```" in text:
            start = text.find("{", text.find("```"))
            end = text.rfind("}") + 1
            text = text[start:end]

        data = json.loads(text)
        effects = data.get("effects", [])
        create_effects_from_analysis(change_id, effects)
        SmartLogger.log(
            "INFO",
            f"EFFECT relations created for {change_id}: {len(effects)}",
            category="requirement_changes.effect.created",
            params={"changeId": change_id, "count": len(effects)},
        )
        return len(effects)
    except Exception as e:
        SmartLogger.log(
            "WARN",
            f"Failed to parse robo-change-specify output for {change_id}: {e}",
            category="requirement_changes.effect.parse_error",
            params={"changeId": change_id, "error": str(e)},
        )
        return 0
