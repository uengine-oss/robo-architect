# Step 1: User Story 로드 및 검증 개선 - 개선 로그

## 개선 목표
Event Storming 워크플로우의 User Story 로드 단계에서 backend-generators의 노하우를 활용하여 품질 검증 및 정제 로직을 추가합니다.

---

## 참고한 backend-generators 코드

**중요**: 이 개선은 `user_story_generator.py`의 검증 로직을 참고했습니다. `requirements_validator.py`는 Event 추출(Step 8)에 사용되며, User Story 검증과는 별개의 목적입니다.

### 1. `user_story_generator.py` - `validate_user_stories` 메서드
**위치**: `backend-generators/src/project_generator/workflows/user_story/user_story_generator.py` (라인 368-434)

**참고한 내용:**
- 필수 필드 검증 로직 (`as`, `iWant`, `soThat` 필드 확인)
- 검증 이슈 수집 및 로깅
- 검증된 User Story만 반환하는 구조

**적용 사항:**
- Event Storming에 맞게 필수 필드를 `role`, `action`, `benefit`으로 변경
- 검증 이슈를 구조화하여 로깅
- 검증 실패한 User Story는 제외하고 계속 진행

**참고: `requirements_validator.py`와의 차이**
- `requirements_validator.py`: 요구사항에서 Event와 Actor를 추출하는 용도 (Step 8에서 사용 예정)
- `user_story_generator.py`: User Story 생성 및 검증 용도 (Step 1에서 사용)

### 2. `user_story_generator.py` - `_format_existing_data` 메서드
**위치**: `backend-generators/src/project_generator/workflows/user_story/user_story_generator.py` (라인 481-521)

**참고한 내용:**
- 중복 방지 로직 (기존 데이터와의 중복 체크)
- Title 기반 중복 감지

**적용 사항:**
- `role` + `action` 조합으로 중복 User Story 감지
- 중복된 User Story는 경고로 기록하고 제외

### 3. `user_story_generator.py` - 전체 구조
**위치**: `backend-generators/src/project_generator/workflows/user_story/user_story_generator.py`

**참고한 내용:**
- 검증 단계를 별도 메서드로 분리
- 검증 이슈를 구조화하여 관리
- 로깅 및 에러 처리 패턴

**적용 사항:**
- `_validate_and_clean_user_stories` 함수로 검증 로직 분리
- 검증 이슈를 딕셔너리 리스트로 구조화
- SmartLogger를 활용한 구조화된 로깅

---

## 구현 내용

### 1. 필수 필드 검증
```python
required_fields = ["role", "action"]
missing_fields = [f for f in required_fields if f not in story or not story.get(f)]
```
- `role`과 `action` 필드가 존재하고 비어있지 않은지 확인
- `benefit`은 선택 필드로 처리

### 2. 필드 값 검증
- 빈 문자열 체크 (`.strip()` 후 검증)
- `role`과 `action`이 실제로 값이 있는지 확인

### 3. 중복 제거
```python
story_key = f"{role.lower()}|{action.lower()}"
if story_key in seen_stories:
    # 중복 감지 및 제외
```
- `role` + `action` 조합으로 중복 감지
- 대소문자 구분 없이 비교

### 4. 우선순위 및 상태 검증
- 우선순위: `["low", "medium", "high", "critical"]`
- 상태: `["draft", "approved", "implemented", "archived"]`
- 잘못된 값이면 기본값으로 설정하고 경고 기록

### 5. 정제된 User Story 반환
- 검증을 통과한 User Story만 반환
- `benefit`이 없으면 `None`으로 통일
- 기본값 설정 (priority: "medium", status: "draft")

---

## 개선 효과

### Before (기존)
- User Story를 단순 로드만 수행
- 검증 로직 없음
- 중복 제거 없음
- 잘못된 데이터도 그대로 사용

### After (개선 후)
- 필수 필드 검증으로 불완전한 User Story 제외
- 중복 제거로 중복된 User Story 제외
- 우선순위 및 상태 검증으로 데이터 품질 향상
- 검증 이슈를 로깅하여 문제 추적 가능

---

## 로깅 개선

### SmartLogger 활용
```python
SmartLogger.log(
    "WARN",
    f"User story validation found {len(validation_issues)} issues",
    category="event_storming.load_user_stories.validation",
    params={
        "total_stories": len(user_stories),
        "validated_stories": len(validated_stories),
        "issues": validation_issues[:10],
    }
)
```

- 구조화된 로깅으로 검증 이슈 추적
- 카테고리별 로깅으로 디버깅 용이

---

## 다음 단계

### 참고: RAG 기반 검색에 대해
**RAG는 User Story 생성 단계에서 사용됩니다**, 현재 `load_user_stories_node`는 이미 생성된 User Story를 Neo4j에서 로드하는 단계이므로 RAG가 필요하지 않습니다.

- **backend-generators의 `user_story_generator.py`**: 
  - `retrieve_rag_context` 메서드에서 RAG를 사용하여 User Story 생성 시 참고할 패턴을 검색
  - 유사 프로젝트, User Story 패턴, 도메인 용어 등을 검색하여 생성 품질 향상
- **Event Storming의 `load_user_stories_node`**:
  - 이미 생성되어 Neo4j에 저장된 User Story를 로드하는 단계
  - 생성 단계가 아니므로 RAG 검색이 필요하지 않음

### 향후 개선 가능 사항
1. **품질 점수 계산**
   - User Story의 완전성 점수 계산
   - 우선순위 기반 정렬

2. **자동 수정 제안**
   - 검증 이슈에 대한 자동 수정 제안
   - LLM을 활용한 개선 제안

---

## 테스트 시나리오

### 1. 정상 케이스
- 모든 필수 필드가 있는 User Story
- 중복이 없는 User Story
- 올바른 우선순위 및 상태

### 2. 검증 실패 케이스
- `role` 또는 `action` 필드가 없는 경우
- 빈 문자열인 경우
- 중복된 User Story

### 3. 경고 케이스
- 잘못된 우선순위 (기본값으로 수정)
- 잘못된 상태 (기본값으로 수정)

---

## 참고 파일

### 수정된 파일
- `api/features/ingestion/event_storming/nodes_init.py`
  - `load_user_stories_node` 함수 개선
  - `_validate_and_clean_user_stories` 함수 추가

### 참고한 backend-generators 파일
- `backend-generators/src/project_generator/workflows/user_story/user_story_generator.py`
  - `validate_user_stories` 메서드 (라인 368-434)
  - `_format_existing_data` 메서드 (라인 481-521)
