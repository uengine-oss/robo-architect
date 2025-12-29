"""Session export API routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from ..db.neo4j import db
from ..ai.facilitator import get_session_instructions
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from ..config import get_settings

router = APIRouter(prefix="/api/sessions", tags=["export"])


@router.get("/{session_id}/export/json")
async def export_json(session_id: str):
    """Export session data as JSON."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    stickers = await db.get_stickers(session_id)
    connections = await db.get_connections(session_id)
    
    return JSONResponse(content={
        "session": {
            "id": session.id,
            "title": session.title,
            "description": session.description,
            "phase": session.phase.value,
            "created_at": session.created_at.isoformat(),
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None
        },
        "stickers": [
            {
                "id": s.id,
                "type": s.type.value,
                "text": s.text,
                "position": {"x": s.position.x, "y": s.position.y},
                "author": s.author
            }
            for s in stickers
        ],
        "connections": [
            {
                "id": c.id,
                "source_id": c.source_id,
                "target_id": c.target_id,
                "label": c.label
            }
            for c in connections
        ]
    })


@router.get("/{session_id}/export/mermaid")
async def export_mermaid(session_id: str):
    """Export session as Mermaid diagram."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    stickers = await db.get_stickers(session_id)
    connections = await db.get_connections(session_id)
    
    # Build Mermaid flowchart
    lines = ["flowchart LR"]
    
    # Define node styles by type
    style_classes = """
    classDef event fill:#ff9800,stroke:#f57c00,color:#000
    classDef command fill:#2196f3,stroke:#1976d2,color:#fff
    classDef policy fill:#9c27b0,stroke:#7b1fa2,color:#fff
    classDef read_model fill:#4caf50,stroke:#388e3c,color:#fff
    classDef external_system fill:#e91e63,stroke:#c2185b,color:#fff
    """
    
    # Create nodes
    sticker_map = {}
    for i, s in enumerate(stickers):
        node_id = f"n{i}"
        sticker_map[s.id] = node_id
        # Escape text for Mermaid
        text = s.text.replace('"', "'").replace('\n', ' ')[:50]
        lines.append(f'    {node_id}["{text}"]:::{s.type.value}')
    
    # Create connections
    for c in connections:
        source = sticker_map.get(c.source_id)
        target = sticker_map.get(c.target_id)
        if source and target:
            label = c.label or ""
            if label:
                lines.append(f'    {source} -->|"{label}"| {target}')
            else:
                lines.append(f'    {source} --> {target}')
    
    lines.append(style_classes)
    
    return JSONResponse(content={
        "mermaid": "\n".join(lines),
        "session_title": session.title
    })


@router.get("/{session_id}/export/summary")
async def export_summary(session_id: str):
    """Generate AI summary of the session."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    stickers = await db.get_stickers(session_id)
    connections = await db.get_connections(session_id)
    
    if not stickers:
        return JSONResponse(content={
            "summary": "세션에 스티커가 없습니다.",
            "events": [],
            "commands": [],
            "policies": []
        })
    
    # Group stickers by type
    events = [s for s in stickers if s.type.value == "event"]
    commands = [s for s in stickers if s.type.value == "command"]
    policies = [s for s in stickers if s.type.value == "policy"]
    read_models = [s for s in stickers if s.type.value == "read_model"]
    external_systems = [s for s in stickers if s.type.value == "external_system"]
    
    # Build context for AI
    context = f"""
세션 제목: {session.title}
설명: {session.description or "없음"}

이벤트 ({len(events)}개):
{chr(10).join(f"- {e.text}" for e in events)}

커맨드 ({len(commands)}개):
{chr(10).join(f"- {c.text}" for c in commands)}

정책 ({len(policies)}개):
{chr(10).join(f"- {p.text}" for p in policies)}

읽기 모델 ({len(read_models)}개):
{chr(10).join(f"- {r.text}" for r in read_models)}

외부 시스템 ({len(external_systems)}개):
{chr(10).join(f"- {e.text}" for e in external_systems)}

연결 ({len(connections)}개):
{chr(10).join(f"- {c.source_id} -> {c.target_id}" for c in connections)}
"""
    
    # Generate summary with AI
    settings = get_settings()
    llm = ChatOpenAI(
        model="gpt-4",
        temperature=0.3,
        api_key=settings.openai_api_key
    )
    
    messages = [
        SystemMessage(content="""당신은 이벤트 스토밍 세션을 분석하는 전문가입니다.
주어진 세션 데이터를 분석하고 다음을 포함하는 요약을 작성하세요:

1. 전체 요약 (2-3문장)
2. 주요 도메인 이벤트 흐름
3. 발견된 중요 비즈니스 정책
4. 식별된 외부 시스템 의존성
5. 추가 탐색이 필요한 영역

한국어로 작성하세요."""),
        HumanMessage(content=context)
    ]
    
    try:
        response = await llm.ainvoke(messages)
        summary_text = response.content
    except Exception as e:
        summary_text = f"AI 요약 생성 중 오류가 발생했습니다: {str(e)}"
    
    return JSONResponse(content={
        "summary": summary_text,
        "statistics": {
            "total_stickers": len(stickers),
            "events": len(events),
            "commands": len(commands),
            "policies": len(policies),
            "read_models": len(read_models),
            "external_systems": len(external_systems),
            "connections": len(connections)
        },
        "events": [{"id": e.id, "text": e.text, "author": e.author} for e in events],
        "commands": [{"id": c.id, "text": c.text} for c in commands],
        "policies": [{"id": p.id, "text": p.text} for p in policies]
    })


@router.post("/{session_id}/end")
async def end_session(session_id: str):
    """Mark session as ended."""
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update session in Neo4j
    async with db._driver.session() as neo_session:
        await neo_session.run("""
            MATCH (s:Session {id: $id})
            SET s.ended_at = datetime()
            RETURN s
        """, {"id": session_id})
    
    return {"status": "ended", "session_id": session_id}


