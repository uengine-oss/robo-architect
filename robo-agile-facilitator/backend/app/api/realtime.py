"""OpenAI Realtime API integration.

Based on: https://platform.openai.com/docs/guides/realtime-conversations
         https://platform.openai.com/docs/guides/realtime-webrtc

This module handles ephemeral token generation for client-side
WebRTC connections to OpenAI's Realtime API.
"""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
from ..config import get_settings
from ..ai.facilitator import get_session_instructions

router = APIRouter(prefix="/api/realtime", tags=["realtime"])


@router.post("/ephemeral-key")
async def get_ephemeral_key(request: Request):
    """
    Get an ephemeral API key for client-side WebRTC connection.
    
    The client uses this ephemeral key to connect directly to OpenAI
    via WebRTC for real-time voice conversations.
    
    Flow:
    1. Client requests ephemeral key from our backend
    2. Backend creates a session with OpenAI, gets ephemeral token
    3. Client uses token to establish WebRTC connection with OpenAI
    """
    settings = get_settings()
    
    body = await request.json() if request.headers.get('content-type') == 'application/json' else {}
    session_id = body.get("session_id")
    
    # Get session-specific instructions for the AI facilitator
    instructions = await get_session_instructions(session_id) if session_id else get_default_instructions()
    
    # Create session with OpenAI to get ephemeral token
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/realtime/sessions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-realtime-preview-2024-12-17",
                    "voice": "alloy",
                    "instructions": instructions,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500
                    },
                    "tools": get_facilitator_tools()
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                error_text = response.text
                print(f"OpenAI API error: {response.status_code} - {error_text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to create session: {error_text}"
                )
            
            result = response.json()
            
            return JSONResponse(content={
                "client_secret": result.get("client_secret", {}).get("value"),
                "session_id": result.get("id"),
                "expires_at": result.get("client_secret", {}).get("expires_at")
            })
            
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="OpenAI API timeout")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Connection error: {str(e)}")


@router.post("/session/{session_id}/update")
async def update_session_config(session_id: str, request: Request):
    """
    Update session configuration.
    
    This can be used to update instructions when the session phase changes.
    Note: Actual updates should be done via the WebRTC data channel
    using session.update events. This endpoint is for reference.
    """
    body = await request.json()
    phase = body.get("phase")
    
    if phase:
        instructions = await get_session_instructions(session_id)
        return JSONResponse(content={
            "instructions": instructions,
            "phase": phase
        })
    
    return JSONResponse(content={"status": "ok"})


def get_default_instructions() -> str:
    """Get default facilitator instructions."""
    return """당신은 이벤트 스토밍 워크숍의 AI 퍼실리테이터 "아리"입니다.

## 역할
- 참가자들이 이벤트 스토밍을 올바르게 수행하도록 안내
- 이벤트 규칙 위반 시 친절하게 교정
- 질문에 답변하고 개념 설명

## 이벤트 스토밍 규칙
1. **이벤트(주황색)**: 반드시 과거형으로 작성 (예: "주문이 생성되었다")
2. **커맨드(파란색)**: 이벤트를 트리거하는 행동 (예: "주문 생성")
3. **정책(보라색)**: "X가 발생하면 Y를 한다" 형식
4. **읽기 모델(초록색)**: 의사결정에 필요한 데이터 뷰
5. **외부 시스템(분홍색)**: 도메인 외부의 시스템

## 대화 스타일
- 한국어로 대화
- 친절하고 격려하는 톤
- 간결하게 핵심만 전달
- 잘못된 것은 즉시 교정하되 이유 설명
"""


def get_facilitator_tools() -> list:
    """Get tool definitions for the AI facilitator."""
    return [
        {
            "type": "function",
            "name": "validate_sticker",
            "description": "이벤트 스토밍 스티커가 규칙에 맞는지 검증합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "sticker_type": {
                        "type": "string",
                        "enum": ["event", "command", "policy", "read_model", "external_system"],
                        "description": "스티커 유형"
                    },
                    "text": {
                        "type": "string",
                        "description": "스티커에 적힌 텍스트"
                    },
                    "is_valid": {
                        "type": "boolean",
                        "description": "규칙에 맞는지 여부"
                    },
                    "issue": {
                        "type": "string",
                        "description": "문제가 있다면 그 이유"
                    },
                    "suggestion": {
                        "type": "string",
                        "description": "수정 제안"
                    }
                },
                "required": ["sticker_type", "text", "is_valid"]
            }
        },
        {
            "type": "function",
            "name": "announce_phase_change",
            "description": "세션 단계 변경을 안내합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_phase": {
                        "type": "string",
                        "description": "이전 단계"
                    },
                    "to_phase": {
                        "type": "string",
                        "enum": ["orientation", "event_elicitation", "event_refinement", "command_policy", "timeline_ordering", "summary"],
                        "description": "새 단계"
                    },
                    "announcement": {
                        "type": "string",
                        "description": "참가자에게 할 안내 메시지"
                    }
                },
                "required": ["to_phase", "announcement"]
            }
        },
        {
            "type": "function",
            "name": "provide_tip",
            "description": "이벤트 스토밍 팁을 제공합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "팁 주제 (예: event, command, policy)"
                    },
                    "tip": {
                        "type": "string",
                        "description": "팁 내용"
                    },
                    "example": {
                        "type": "string",
                        "description": "예시"
                    }
                },
                "required": ["topic", "tip"]
            }
        }
    ]
