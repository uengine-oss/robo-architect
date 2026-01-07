from __future__ import annotations

import json
from typing import Any, Dict


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    event_data = {"type": event_type, **data}
    return f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"


