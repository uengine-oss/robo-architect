"""
Event Storming Nodes: initialization + loading user stories

개선 사항 (backend-generators 노하우 반영):
- User Story 품질 검증 (validate_user_stories 참고)
- 중복 제거 및 정제
- 우선순위 및 상태 검증
- 필수 필드 완전성 체크
"""

from __future__ import annotations

from typing import Any, Dict, List
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from api.platform.observability.smart_logger import SmartLogger

from .neo4j_client import get_neo4j_client
from .prompts import SYSTEM_PROMPT
from .state import EventStormingState, WorkflowPhase, format_user_story


def init_node(state: EventStormingState) -> Dict[str, Any]:
    """Initialize the workflow."""
    return {
        "phase": WorkflowPhase.LOAD_USER_STORIES,
        "messages": [SystemMessage(content=SYSTEM_PROMPT)],
    }


def load_user_stories_node(state: EventStormingState) -> Dict[str, Any]:
    """
    Load and validate user stories from Neo4j.
    
    개선 사항 (backend-generators의 user_story_generator.py 참고):
    1. User Story 품질 검증 (validate_user_stories 메서드 참고)
    2. 중복 제거 및 정제
    3. 우선순위 및 상태 검증
    4. 필수 필드 완전성 체크 (role, action, benefit)
    """
    client = get_neo4j_client()

    # First try to get unprocessed stories
    user_stories = client.get_unprocessed_user_stories()

    # If none, get all stories for demo purposes
    if not user_stories:
        user_stories = client.get_all_user_stories()

    if not user_stories:
        return {
            "phase": WorkflowPhase.COMPLETE,
            "error": "No user stories found in Neo4j. Please load sample data first.",
        }

    # ========================================================================
    # User Story 검증 및 정제 (backend-generators의 validate_user_stories 참고)
    # ========================================================================
    
    validated_stories, validation_issues = _validate_and_clean_user_stories(user_stories)
    
    if validation_issues:
        SmartLogger.log(
            "WARN",
            f"User story validation found {len(validation_issues)} issues",
            category="event_storming.load_user_stories.validation",
            params={
                "total_stories": len(user_stories),
                "validated_stories": len(validated_stories),
                "issues": validation_issues[:10],  # 최대 10개만 로그
            }
        )

    if not validated_stories:
        return {
            "phase": WorkflowPhase.COMPLETE,
            "error": "No valid user stories found after validation. Please check user story data quality.",
        }

    # Format stories for display
    stories_text = "\n".join([f"- [{us['id']}] {format_user_story(us)}" for us in validated_stories])

    SmartLogger.log(
        "INFO",
        f"Loaded and validated {len(validated_stories)}/{len(user_stories)} user stories",
        category="event_storming.load_user_stories.complete",
        params={
            "total_loaded": len(user_stories),
            "validated": len(validated_stories),
            "filtered": len(user_stories) - len(validated_stories),
        }
    )

    return {
        "user_stories": validated_stories,
        "total_user_stories": len(validated_stories),
        "phase": WorkflowPhase.IDENTIFY_BC,
        "messages": [
            HumanMessage(
                content=f"Loaded and validated {len(validated_stories)}/{len(user_stories)} user stories:\n{stories_text}"
            )
        ],
    }


def _validate_and_clean_user_stories(user_stories: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    User Story 검증 및 정제
    
    backend-generators의 user_story_generator.py의 validate_user_stories 메서드 참고:
    - 필수 필드 확인 (role, action, benefit)
    - 중복 제거
    - 우선순위 및 상태 검증
    
    Returns:
        (validated_stories, validation_issues)
    """
    validated_stories = []
    validation_issues = []
    seen_stories = set()  # 중복 제거용
    
    for story in user_stories:
        story_id = story.get("id", "unknown")
        
        # 1. 필수 필드 확인 (backend-generators의 validate_user_stories 참고)
        # Event Storming에서는 role, action, benefit이 필수
        required_fields = ["role", "action"]
        missing_fields = [f for f in required_fields if f not in story or not story.get(f)]
        
        if missing_fields:
            validation_issues.append({
                "story_id": story_id,
                "issue": f"Missing required fields: {', '.join(missing_fields)}",
                "severity": "error"
            })
            continue
        
        # 2. 필드 값 검증 (빈 문자열 체크)
        role = story.get("role", "").strip()
        action = story.get("action", "").strip()
        benefit = story.get("benefit", "").strip() if story.get("benefit") else ""
        
        if not role:
            validation_issues.append({
                "story_id": story_id,
                "issue": "Role field is empty",
                "severity": "error"
            })
            continue
        
        if not action:
            validation_issues.append({
                "story_id": story_id,
                "issue": "Action field is empty",
                "severity": "error"
            })
            continue
        
        # 3. 중복 제거 (동일한 role + action 조합)
        # backend-generators의 중복 방지 로직 참고
        story_key = f"{role.lower()}|{action.lower()}"
        if story_key in seen_stories:
            validation_issues.append({
                "story_id": story_id,
                "issue": f"Duplicate user story: role='{role}', action='{action}'",
                "severity": "warning"
            })
            continue
        
        seen_stories.add(story_key)
        
        # 4. 우선순위 검증 (backend-generators의 priority 검증 참고)
        priority = story.get("priority", "medium")
        valid_priorities = ["low", "medium", "high", "critical"]
        if priority not in valid_priorities:
            validation_issues.append({
                "story_id": story_id,
                "issue": f"Invalid priority '{priority}'. Valid values: {', '.join(valid_priorities)}",
                "severity": "warning"
            })
            # 우선순위가 잘못되어도 기본값으로 설정하고 계속 진행
            story["priority"] = "medium"
        
        # 5. 상태 검증
        status = story.get("status", "draft")
        valid_statuses = ["draft", "approved", "implemented", "archived"]
        if status not in valid_statuses:
            validation_issues.append({
                "story_id": story_id,
                "issue": f"Invalid status '{status}'. Valid values: {', '.join(valid_statuses)}",
                "severity": "warning"
            })
            # 상태가 잘못되어도 기본값으로 설정하고 계속 진행
            story["status"] = "draft"
        
        # 6. 정제된 User Story 추가
        validated_story = {
            "id": story_id,
            "role": role,
            "action": action,
            "benefit": benefit if benefit else None,  # None으로 통일
            "priority": story.get("priority", "medium"),
            "status": story.get("status", "draft"),
            "uiDescription": story.get("uiDescription", ""),
        }
        
        validated_stories.append(validated_story)
    
    return validated_stories, validation_issues


