"""POSCO 표준항목 MCP 를 흉내 내는 가짜(로컬) — 단위 시험과 probe 시험이 같이 쓴다.

    python api/features/standard_items/tests/fake_mcp_server.py 18029          # SSE 응답
    python api/features/standard_items/tests/fake_mcp_server.py 18029 json     # JSON 응답

키워드별 응답:
  주문번호  → 정확히 같은 것 1건(사용) + 비슷한 것 1건
  고객명    → 정확히 같은 것 2건
  폐기항목  → 정확히 같은 것 1건, 상태 '폐기'
  없는항목  → 0건
  느림      → 3초 뒤 응답(시간 초과 시험)
"""

from __future__ import annotations

import socket
import sys
import threading
import time
from typing import Any


def _entry(name: str, eid: str, status: str | None = "사용", **kw: Any) -> dict[str, Any]:
    base = {
        "standardKoreanName": name,
        "standardEnglishId": eid,
        "stdItemValueType": "VARCHAR",
        "dataLength": 20,
        "decimalLength": None,
        "codeItem": "N",
        "mesUnitOfMeasure": None,
        "macroMicroItemType": None,
        "supervisoryDept": "정보기획",
        "standardItemStatus": status,
        "standardItemDefinitionContent": f"{name} 정의",
        "standardItemManagementMethodExplanation": None,
    }
    base.update(kw)
    return base


DATA: dict[str, list[dict[str, Any]]] = {
    "주문번호": [
        _entry("주문번호", "ORD_NO", dataLength=12),
        _entry("주문번호구분", "ORD_NO_TP", dataLength=2, codeItem="Y"),
    ],
    "고객명": [_entry("고객명", "CUST_NM"), _entry("고객명", "CUST_NAME")],
    "폐기항목": [_entry("폐기항목", "OLD_ITEM", status="폐기")],
    "없는항목": [],
}


def build_app(json_response: bool = False):
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("fake-posco-dd", stateless_http=True, json_response=json_response)

    @mcp.tool()
    def searchDataDictionary(keyword: str, languageCode: str = "KO") -> list[dict[str, Any]]:  # noqa: N802,N803
        """표준항목명 또는 표준항목ID 로 데이터 사전을 찾는다."""
        if keyword == "느림":
            time.sleep(3)
            return []
        return DATA.get(keyword, [])

    return mcp.streamable_http_app()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_in_thread(port: int | None = None, json_response: bool = False):
    """(서버, url) — 시험이 끝나면 server.should_exit = True."""
    import uvicorn

    port = port or free_port()
    config = uvicorn.Config(build_app(json_response), host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    return server, f"http://127.0.0.1:{port}/mcp"


if __name__ == "__main__":
    import uvicorn

    p = int(sys.argv[1]) if len(sys.argv) > 1 else 18029
    uvicorn.run(build_app(len(sys.argv) > 2 and sys.argv[2] == "json"), host="127.0.0.1", port=p)
