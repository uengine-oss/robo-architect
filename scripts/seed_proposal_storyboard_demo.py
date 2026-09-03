"""056 — 스토리보드 데모/테스트용 Proposal 시드.

Intent 단계 결과(strategicDiff + journeys)를 이미 가진 DRAFT Proposal 을 Neo4j 에
만든다(claude CLI 없이 재현 가능). stdout 마지막 줄에 proposal id 를 출력한다.

    uv run python scripts/seed_proposal_storyboard_demo.py [--id PRO-DEMO-SB]
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()  # api.main 과 같은 .env 해석 (스크립트 단독 실행용)

from api.platform.neo4j import get_session  # noqa: E402

STRATEGIC = {
    "version": 1,
    "epics": [{"op": "CREATE", "entityType": "epic", "tempId": "EP-order", "entityTitle": "배달 주문",
               "fields": {"classification": {"after": "core"}}}],
    "features": [{"op": "CREATE", "entityType": "feature", "tempId": "FT-order", "entityTitle": "음식 주문", "epicId": "EP-order"}],
    "userStories": [
        {"op": "CREATE", "entityType": "userStory", "tempId": "US-browse", "entityTitle": "메뉴 탐색", "featureId": "FT-order",
         "fields": {"role": {"after": "고객"}, "action": {"after": "가게의 메뉴를 카테고리별로 훑어보고 옵션을 확인한다"},
                    "benefit": {"after": "원하는 음식을 빠르게 고른다"},
                    "acceptanceCriteria": {"after": "메뉴 카드에 사진·가격·인기 배지가 보이고, 카드를 누르면 옵션 시트가 열린다"}}},
        {"op": "CREATE", "entityType": "userStory", "tempId": "US-cart", "entityTitle": "장바구니 담기", "featureId": "FT-order",
         "fields": {"role": {"after": "고객"}, "action": {"after": "옵션과 수량을 골라 장바구니에 담는다"},
                    "benefit": {"after": "여러 메뉴를 한 번에 주문한다"},
                    "acceptanceCriteria": {"after": "하단 고정 바에 총액과 '주문하기' 버튼이 보인다"}}},
        {"op": "CREATE", "entityType": "userStory", "tempId": "US-checkout", "entityTitle": "주문·결제", "featureId": "FT-order",
         "fields": {"role": {"after": "고객"}, "action": {"after": "배달 주소와 결제수단을 확인하고 주문을 확정한다"},
                    "benefit": {"after": "안전하게 결제를 마친다"},
                    "acceptanceCriteria": {"after": "주소·요청사항·결제수단·쿠폰 섹션과 최종 금액, '결제하기' 버튼"}}},
        {"op": "CREATE", "entityType": "userStory", "tempId": "US-track", "entityTitle": "배달 현황 확인", "featureId": "FT-order",
         "fields": {"role": {"after": "고객"}, "action": {"after": "주문 접수부터 배달 완료까지 단계를 실시간으로 본다"},
                    "benefit": {"after": "언제 도착할지 안다"},
                    "acceptanceCriteria": {"after": "타임라인(접수→조리→픽업→배달중→완료)과 예상 도착 시각, 라이더 위치 지도"}}},
    ],
    "processes": [],
}

JOURNEYS = [
    {"tempId": "JNY-order", "boundedContextId": "EP-order", "name": "음식 주문 여정",
     "description": "메뉴 탐색부터 배달 완료 확인까지",
     "steps": [
         {"tempId": "ST-browse", "name": "메뉴 탐색", "kind": "screen", "readModelRef": "RM-menu", "userStoryRef": "US-browse", "next": ["ST-cart"]},
         {"tempId": "ST-cart", "name": "장바구니", "kind": "screen", "commandRef": "CMD-add-cart", "userStoryRef": "US-cart", "next": ["ST-min"]},
         {"tempId": "ST-min", "name": "최소주문금액 충족?", "kind": "gateway", "condition": "장바구니 총액 ≥ 가게 최소주문금액", "next": ["ST-checkout"]},
         {"tempId": "ST-checkout", "name": "주문·결제", "kind": "screen", "commandRef": "CMD-place-order", "userStoryRef": "US-checkout", "next": ["ST-track"]},
         {"tempId": "ST-track", "name": "배달 현황", "kind": "screen", "readModelRef": "RM-delivery", "userStoryRef": "US-track", "next": []},
     ]},
]

PROMPT = "배달 앱에 음식 주문 기능을 추가한다. 고객은 가게 메뉴를 보고 장바구니에 담아 주소·결제수단을 확인한 뒤 주문하고, 배달 현황을 실시간으로 확인할 수 있어야 한다."


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default="PRO-DEMO-SB")
    ap.add_argument("--reset-storyboard", action="store_true", help="기존 storyboard 제거")
    args = ap.parse_args()
    now = datetime.now(timezone.utc).isoformat()
    with get_session() as session:
        session.run(
            """
            MERGE (p:Proposal {id: $id})
            ON CREATE SET p.createdAt = datetime($now), p.statusHistory = '[]', p.clarificationLog = '[]'
            SET p.title = $title, p.originalPrompt = $prompt, p.author = 'demo', p.status = 'DRAFT',
                p.decompositionMode = 'SIMPLIFIED', p.strategicDiff = $sd, p.journeys = $jny
            """,
            id=args.id, now=now, title="배달 앱 음식 주문 기능", prompt=PROMPT,
            sd=json.dumps(STRATEGIC, ensure_ascii=False), jny=json.dumps(JOURNEYS, ensure_ascii=False),
        )
        if args.reset_storyboard:
            session.run("MATCH (p:Proposal {id: $id}) REMOVE p.storyboard", id=args.id)
    print(args.id)


if __name__ == "__main__":
    main()
