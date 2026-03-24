# Figma Storyboard Ingestion

Figma에 설계된 스토리보드(화면 프레임)를 복사하여 붙여넣기만으로 Event Storming 모델을 자동 생성하는 파이프라인.

---

## 1. 개요

기존 Ingestion은 텍스트 기반 요구사항(RFP, Confluence, 레거시 보고서)을 입력으로 받았다.
Figma Ingestion은 **UI 화면 구성요소 자체를 요구사항으로** 취급하여, 화면에 보이는 버튼·입력필드·테이블·네비게이션 등에서 User Story를 추론하고, 이후 동일한 Event Storming 워크플로우에 합류한다.

### 입력 → 출력

```
Figma 화면 복사 (Ctrl+C)
  → 브라우저 클립보드 (fig-kiwi binary in HTML)
    → nodeChanges[] 파싱
      → LLM으로 User Story 추출 (화면별 청킹)
        → Bounded Context → Aggregate → Command → Event → ...
          → UI Wireframe 생성 시 원본 Figma 화면 참조
```

---

## 2. 전체 아키텍처

### 2.1 프론트엔드 (Vue 3)

```
RequirementsIngestionModal.vue
├── inputMode = 'figma' 탭
├── handleFigmaPaste(e)          ← 클립보드 paste 이벤트
│   ├── readClipboardHTML(html)  ← fig-kiwi 바이너리 디코딩
│   │   ├── parseHTMLClipboard() ← HTML에서 figmeta + figma base64 추출
│   │   ├── parseArchive()       ← fig-kiwi 아카이브 파싱
│   │   └── decompressAuto()     ← zstd 또는 zlib 자동 감지 해제
│   ├── message.nodeChanges[]    ← Figma 노드 트리
│   └── simplified JSON 변환     ← type, name, text, size, parentId 등
├── startIngestion()
│   └── POST /api/ingest/upload/figma (JSON body)
└── connectToStream(session_id)  ← SSE로 진행률 수신
```

### 2.2 백엔드 (FastAPI)

```
POST /api/ingest/upload/figma
  body: { figma_nodes: [...], source_type: "figma", display_language: "ko" }
  → session.content = JSON.stringify(figma_nodes)
  → session.source_type = "figma"

GET /api/ingest/stream/{session_id}
  → run_ingestion_workflow(session, content)
    → parsing_phase          ("Figma UI 요소 파싱 중...")
    → extract_user_stories_phase  ← Figma 전용 분기
    → identify_bounded_contexts_phase
    → extract_aggregates_phase
    → extract_commands_phase
    → extract_events_phase
    → ... (기존 워크플로우 동일)
    → generate_ui_wireframes_phase  ← Figma 화면 참조 주입
```

---

## 3. Figma 클립보드 파싱

### 3.1 fig-kiwi 바이너리 포맷

Figma에서 요소를 복사하면 클립보드에 `text/html` MIME으로 데이터가 저장된다:

```html
<span data-metadata="<!--(figmeta)BASE64(/figmeta)-->"></span>
<span data-buffer="<!--(figma)BASE64(/figma)-->"></span>
```

- **figmeta**: JSON (파일 키, 페이스트 ID 등 메타데이터)
- **figma**: fig-kiwi 아카이브 (바이너리)

### 3.2 fig-kiwi 아카이브 구조

```
[fig-kiwi prelude (8 bytes)] [version (4 bytes, uint32 LE)]
[file1_size (4 bytes)] [file1_data ...]
[file2_size (4 bytes)] [file2_data ...]
```

- **file1**: 압축된 Kiwi Schema (메시지 구조 정의)
- **file2**: 압축된 메시지 데이터 (nodeChanges)

### 3.3 압축 방식 자동 감지

최신 Figma는 zstd 압축을 사용하는 경우가 있어, 첫 4바이트로 구분:

| Magic Bytes | 압축 방식 | 라이브러리 |
|-------------|-----------|-----------|
| `28 B5 2F FD` | zstd | `fzstd` |
| 기타 | zlib (deflate raw) | `pako` |

```typescript
// figkiwi.ts
function decompressAuto(buf: Uint8Array): Uint8Array {
  if (isZstd(buf)) return zstdDecompress(buf)
  return inflateRaw(buf)
}
```

### 3.4 nodeChanges 구조

디코딩된 메시지에서 `nodeChanges` 배열을 추출하며, 각 노드는:

| 필드 | 설명 | 예시 |
|------|------|------|
| `guid` | Figma 고유 ID | `{sessionID: 312, localID: 105}` |
| `type` | 노드 타입 | `FRAME`, `TEXT`, `RECTANGLE`, `ELLIPSE` |
| `name` | 컴포넌트/레이어 이름 | `"주문 목록 화면"`, `"로그인 버튼"` |
| `size` | 크기 (px) | `{x: 1440, y: 900}` |
| `parentIndex.guid` | 부모 노드 참조 | `{sessionID: 312, localID: 100}` |
| `textData.characters` | 텍스트 내용 | `"검색"`, `"저장하기"` |
| `fillPaints` | 배경색 | `[{type: 'SOLID', color: {r,g,b,a}}]` |
| `stackMode` | 레이아웃 방향 | `"VERTICAL"`, `"HORIZONTAL"` |

### 3.5 프론트엔드 간소화

API 전송 시 필요한 정보만 추출하여 페이로드를 줄인다:

```javascript
const simplified = nodeChanges.map(n => ({
  type: n.type,
  name: n.name || '',
  text: n.textData?.characters || '',
  width: n.size?.x || 0,
  height: n.size?.y || 0,
  parentId: n.parentIndex?.guid
    ? `${n.parentIndex.guid.sessionID}-${n.parentIndex.guid.localID}`
    : null,
  id: n.guid
    ? `${n.guid.sessionID}-${n.guid.localID}`
    : null,
  stackMode: n.stackMode || null,
  visible: n.visible !== false,
}))
```

---

## 4. User Story 추출 (화면별 청킹)

### 4.1 화면 단위 청킹

32개 화면, 1105개 요소와 같은 대규모 스토리보드는 단일 LLM 호출로 처리할 수 없다.
**최상위 FRAME(화면)** 단위로 청킹하여 병렬 처리한다.

| 설정 | 값 | 설명 |
|------|----|------|
| `MAX_SCREENS_PER_CHUNK` | 5 | 화면/청크 |
| `MAX_CONCURRENT_CHUNKS` | 3 | 동시 LLM 호출 수 |

```
32개 화면 → 7개 청크 (5, 5, 5, 5, 5, 5, 2)
  → semaphore(3)으로 최대 3개 동시 처리
  → 각 청크 완료 시 SSE 진행률 이벤트
  → 전체 merge → normalize_and_dedup → 순차 ID 재부여
```

### 4.2 노드 → 텍스트 요약

LLM에 전달하기 위해 노드 트리를 사람이 읽을 수 있는 텍스트로 변환:

```
## 화면: 주문 목록
- [FRAME] "주문 목록" (1440x900)
  - [FRAME] "App Bar" (1440x64)
    - [TEXT] "주문 관리" (텍스트: "주문 관리")
    - [FRAME] "검색 영역" (400x40)
      - [TEXT] "Placeholder" (텍스트: "주문번호로 검색...")
    - [FRAME] "버튼 그룹"
      - [TEXT] "새 주문" (텍스트: "새 주문")
      - [TEXT] "내보내기" (텍스트: "내보내기")
  - [FRAME] "테이블" (1400x700)
    - [TEXT] "주문번호" ...
    - [TEXT] "주문일시" ...
```

### 4.3 Figma 전용 시스템 프롬프트

일반 RFP 프롬프트와 다르게, UI 요소에서 기능을 추론하도록 지시:

- 버튼 텍스트 → 주요 액션 식별
- 입력 필드 / 폼 → 데이터 입력/수정 기능
- 테이블 / 리스트 → 조회/목록 기능
- 네비게이션 → 화면 간 이동, 메뉴 구조

### 4.4 source_screen_name 추적

각 User Story에 **어떤 Figma 화면에서 파생되었는지** 기록:

```python
class GeneratedUserStory(BaseModel):
    id: str
    role: str
    action: str
    benefit: str
    ui_description: str = ""
    source_screen_name: Optional[str] = None  # ← Figma 화면 이름
```

프롬프트에서 LLM이 `source_screen_name`을 직접 출력하도록 지시한다.

---

## 5. Figma 화면 → UI Wireframe 연결

### 5.1 문제

Ingestion 워크플로우의 UI 생성 phase(`generating_ui`)에서 LLM이 wireframe HTML을 생성할 때,
Figma에 이미 설계된 원본 화면이 있음에도 이를 참고하지 못하는 문제.

### 5.2 연결 체인

```
ctx.figma_screens["주문 목록"] = "- [FRAME] 주문 목록 ..."  (노드 구조 텍스트)
    ↑ user_stories.py에서 파싱 시 저장

User Story (source_screen_name = "주문 목록")
    ↑ LLM이 Figma US 추출 시 태깅

Command (user_story_ids = ["US-003"])
    ↑ identify_bounded_contexts → extract_commands에서 연결

UI Wireframe 생성 프롬프트
    ↑ _create_command_ui()에서 source_screen_name 조회
      → ctx.figma_screens[source_screen_name] 을 프롬프트에 주입
```

### 5.3 프롬프트 주입 예시

기존 UI 생성 프롬프트에 다음이 추가된다:

```
★ Figma 원본 화면 참조 ('주문 목록'):
이 Command의 UI는 아래 Figma 화면 구조를 충실히 반영하여 생성하세요.
- [FRAME] "주문 목록" (1440x900)
  - [FRAME] "App Bar" (1440x64)
    - [TEXT] "주문 관리"
    - [FRAME] "검색 영역" (400x40)
      ...
```

이를 통해 LLM은 원본 Figma 화면의 레이아웃, 컴포넌트 구성, 텍스트 라벨을 참고하여 wireframe HTML을 생성한다.

### 5.4 적용 범위

| 대상 | 매핑 | Figma 참조 |
|------|------|-----------|
| Command UI | Command → user_story_ids → US → source_screen_name | O |
| ReadModel UI | ReadModel → user_story_ids → US → source_screen_name | O |
| Policy-invoked Command | UI 생성 스킵 (기존과 동일) | - |

---

## 6. 데이터 흐름 상세

### 6.1 IngestionWorkflowContext 확장

```python
@dataclass
class IngestionWorkflowContext:
    ...
    source_type: str = "rfp"        # "rfp" | "legacy_report" | "figma"
    figma_screens: Dict[str, str]   # 화면이름 → 노드구조 텍스트 (figma일 때만)
```

### 6.2 Phase별 동작 차이 (source_type = "figma")

| Phase | 기존 (RFP) | Figma |
|-------|-----------|-------|
| parsing | 문서 텍스트 파싱 | "Figma UI 요소 파싱 중..." (validation only) |
| extracting_user_stories | 텍스트 → US (청킹) | nodeChanges → 화면별 요약 → LLM (화면 청킹) |
| identifying_bc ~ generating_gwt | 동일 | 동일 (US 이후 워크플로우 공유) |
| generating_ui | LLM이 ui_description으로 생성 | LLM이 ui_description + **Figma 원본 화면** 참조하여 생성 |

---

## 7. 파일 구조

### 프론트엔드

```
frontend/src/features/
├── canvas/ui/figma/
│   ├── figkiwi.ts              ← fig-kiwi 바이너리 파싱 (zstd/zlib 자동 감지)
│   ├── types.ts                ← WireframeElement 타입
│   ├── nodes.ts                ← NodeChange 인터페이스
│   ├── converter.ts            ← WireframeElement → Figma 변환 (export용)
│   ├── htmlParser.ts           ← HTML → WireframeElement (export용)
│   └── index.ts                ← readClipboardHTML 등 re-export
└── requirementsIngestion/ui/
    └── RequirementsIngestionModal.vue  ← Figma 탭, handleFigmaPaste()
```

### 백엔드

```
api/features/ingestion/
├── router.py                           ← POST /api/ingest/upload/figma
├── figma_to_user_stories.py            ← Figma 전용 US 추출 (청킹, 프롬프트)
├── ingestion_contracts.py              ← GeneratedUserStory.source_screen_name
├── ingestion_workflow_runner.py         ← source_type 분기
└── workflow/
    ├── ingestion_workflow_context.py    ← figma_screens 맵
    └── phases/
        ├── parsing.py                  ← Figma 메시지 분기
        ├── user_stories.py             ← Figma 청킹 처리 + figma_screens 저장
        └── ui_wireframes.py            ← Figma 화면 참조 프롬프트 주입
```

---

## 8. 설정 값

| 항목 | 값 | 위치 |
|------|----|------|
| 화면/청크 | 5 | `figma_to_user_stories.MAX_SCREENS_PER_CHUNK` |
| 동시 LLM 호출 | 3 | `figma_to_user_stories.MAX_CONCURRENT_CHUNKS` |
| LLM max_tokens | 32,768 | `_extract_from_summary()` |
| LLM 타임아웃 (UI) | 300초 | `ui_wireframes._llm_invoke_to_html()` |

---

## 9. 제약 사항 및 향후 개선

### 현재 제약

- Figma 클립보드 데이터에 **이미지/에셋**은 포함되지 않음 (노드 구조만 전달)
- 컴포넌트 variants/overrides, 프로토타입 인터랙션 데이터는 파싱하지 않음
- `source_screen_name` 매핑은 LLM이 추론하므로, 화면 이름이 모호하면 오매핑 가능

### 향후 개선 가능

- 화면 이름 유사도 기반 fuzzy matching으로 매핑 보정
- Figma 화면 스크린샷(이미지)을 멀티모달 LLM에 전달하여 더 정확한 분석
- 화면 간 네비게이션 흐름 분석으로 Policy/Event 연결 자동화
- Figma API 직접 연동 (클립보드 대신 파일 URL로 접근)
