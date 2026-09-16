"""자체 호스팅 pdf2bpmn 이 **실제로 쓰이고 실제로 BPMN 을 내는가.**

사내망에서는 `https://pdf2bpmn.process-gpt.io` 호출이 막힌다. 그래서 그 서비스를
안에 올렸다 — `deploy/pdf2bpmn-selfhosted/`. 이 검사는 그것이 진짜 도는지 잰다.

**`/healthz` 는 아무것도 증명하지 않는다.** 실제로 그랬다 — compose 의
`command:` 가 ENTRYPOINT 를 안 덮어서 이미지의 자기 스택만 돌고 우리 앱은 안
떴는데, 컨테이너 상태는 `running` 이었다. 오류도 없었다.

재는 것 셋:

```
① facade 가 진짜 BPMN 을 낸다        task·gateway·flow 를 센다
② robo 의 Phase 1 이 그 길로 간다     source == "facade"
③ **그게 우리 컨테이너다**            컨테이너를 내리면 실패해야 한다
```

③ 이 핵심이다. `.env` 에 바깥 주소가 남아 있으면 ①②만으로는 **바깥으로 나가고도
통과한다.** 그래서 내렸다 올리며 가른다. docker 로그로는 못 가린다(접근 로그가
요약돼 안 보인다 — 한 번 헛짚었다).

    robo-architect/.venv/bin/python scripts/verify_pdf2bpmn_selfhosted.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
os.environ.setdefault("AUTH_JWT_SECRET", "verify-only-secret")
os.environ.setdefault("AUTH_ROLE_SECRET", "verify-only-role-secret")

PORT = os.getenv("PDF2BPMN_FACADE_PORT", "8610")
SELF = f"http://127.0.0.1:{PORT}"
COMPOSE_DIR = ROOT / "deploy" / "pdf2bpmn-selfhosted"
PDF = ROOT.parent / "input_resource" / "업무Flow_초안_자동납부_본인확인_요청처리.pdf"

# **이 프로세스에서만** 바꾼다. 돌고 있는 서버의 `.env` 를 검사가 건드리면 안 된다.
os.environ["PDF2BPMN_FACADE_URL"] = SELF
os.environ["PDF2BPMN_FACADE_KEY"] = os.getenv("PDF2BPMN_SELFHOSTED_KEY", "")
os.environ["HYBRID_USE_A2A"] = "false"  # 폴백이 결과를 가리지 않게

_fail: list[str] = []
_n = 0


def check(label: str, got, want) -> None:
    global _n
    _n += 1
    ok = got == want
    print(f"{'ok ' if ok else 'FAIL'} {label}" + ("" if ok else f"\n     got={got!r}\n     want={want!r}"))
    if not ok:
        _fail.append(label)


OUTLINE = """자동납부 신청 처리 절차.
1) 고객이 자동납부를 신청하면 신청서의 입력값을 검증한다.
2) 결제수단이 은행이면 은행 사전등록 여부를 확인하고, 카드이면 카드사 코드 정합성을 검증한다.
3) 검증에 통과하면 외부 인증기관에 실시간 계좌인증을 요청한다.
4) 인증에 성공하면 자동납부 신청을 확정하고 결과를 반환한다.
5) 인증에 실패하면 오류 사유를 기록하고 신청을 반려한다."""


def _compose(*args: str) -> None:
    subprocess.run(["docker", "compose", *args], cwd=COMPOSE_DIR,
                   capture_output=True, text=True, check=False)


def _healthy(timeout_s: float = 90.0) -> bool:
    end = time.time() + timeout_s
    while time.time() < end:
        try:
            with urllib.request.urlopen(f"{SELF}/healthz", timeout=3):
                return True
        except Exception:
            time.sleep(3)
    return False


def facade_bpmn() -> tuple[str, dict]:
    body = json.dumps({"process_name": "자동납부 신청", "consulting_outline": OUTLINE}).encode()
    req = urllib.request.Request(SELF + "/api/consulting-bpmn", data=body,
                                 headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        # **대소문자 구분 dict 로 만들면 안 된다.** HTTP 헤더는 대소문자를
        # 안 가리는데 dict 는 가린다 — 멀쩡한 응답을 "헤더가 없다"로 읽는다.
        return r.read().decode("utf-8", "replace"), {k.lower(): v for k, v in r.headers.items()}


async def phase1(pdf: Path):
    from api.features.ingestion.hybrid.document_to_bpm import extract_bpm_skeleton
    return await extract_bpm_skeleton(
        content="", session_id="zz-p2b-verify",
        pdf_path=str(pdf), source_pdf_name=pdf.name,
    )


def main() -> int:
    if not PDF.exists():
        print(f"검사용 PDF 가 없다: {PDF}")
        return 1

    print("\n── ① facade 가 진짜 BPMN 을 내는가 ────────────────────")
    check("컨테이너가 떠 있다", _healthy(), True)
    if _fail:
        print("  (먼저 띄운다: cd deploy/pdf2bpmn-selfhosted && docker compose up -d)")
        return 1
    xml, headers = facade_bpmn()
    check("XML 이다", xml.strip().startswith("<"), True)
    check("컨설팅 LLM 경로다", headers.get("x-bpmn-source"), "consulting-llm")
    tasks = len(re.findall(r"<bpmn:?(?:user|service)?[Tt]ask\b", xml))
    flows = len(re.findall(r"<bpmn:?sequenceFlow\b", xml))
    # 개수로 재는 이유 — XML 이 오기만 하고 **뼈대가 비는** 경우가 있다.
    check("task 가 셋 이상", tasks >= 3, True)
    check("흐름이 셋 이상", flows >= 3, True)

    print("\n── ② robo 의 Phase 1 이 그 길로 가는가 ────────────────")
    res = asyncio.run(phase1(PDF))
    check("source 가 facade", res.source, "facade")
    check("오류 없음", res.error, None)
    got_tasks = sum(len(s.tasks) for s in (res.bundle.processes if res.bundle else []))
    check("task 가 둘 이상", got_tasks >= 2, True)

    print("\n── ③ 그게 우리 컨테이너인가 ───────────────────────────")
    # **내려 보는 것이 유일한 확실한 방법이다.** 켜 둔 채로는 바깥으로 나가고도
    # 통과한다. docker 접근 로그로 가리려 했다가 한 번 헛짚었다.
    _compose("stop")
    try:
        down = asyncio.run(phase1(PDF))
        check("내리면 facade 로 못 간다", down.source != "facade", True)
        check("연결 실패가 이유로 남는다",
              "connection" in (down.error or "").lower(), True)
    finally:
        _compose("start")
        check("다시 올라온다", _healthy(), True)

    print(f"\n검사 {_n}종 — " + ("전부 통과" if not _fail else f"{len(_fail)}종 실패"))
    for f in _fail:
        print("  실패:", f)
    return 1 if _fail else 0


if __name__ == "__main__":
    sys.exit(main())
