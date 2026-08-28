# 기업 납품 — 완료 작업

> 대상: Robo Architect `enterprise-custom-p`
> 기준 소스: `local-msaez/platform/src/components/designer/modeling/DocumentTemplate.vue` (3,035 lines), `CodeGenerator.vue`, `run_healcheck_server.py`
> 검증 세션: Hybrid Ingestion `a149dfd5` (실데이터, 로컬 Backend `127.0.0.1:8000`)
> 최종 갱신: 2026-08-27
> 남은 작업: `enterprise-todo.md`

## 0. 요약

`local-msaez` `DocumentTemplate.vue`의 산출물을 Robo Architect로 옮겼다. 코드를 복사하지 않고 **섹션 구성·순서·데이터 계약은 기준 템플릿을 그대로 유지**하되 데이터 출처만 Robo Architect 그래프로 바꿨다.

| 작업 | ID |
|---|---|
| 문서 업로드 파이프라인 잠복 버그 수정 | — |
| 파이프라인 검증기 오판 수정 | — |
| Session 고정 Deliverable API | ENT-DOC-001 |
| 산출물 섹션 보완 (밸류 스트림·추적성·원문 근거) | ENT-DOC-002 (부분) |
| API 계약 규칙 도출 | ENT-DOC-002 |
| Aggregate JSON 내보내기 | — |
| DOCX 정본화 및 ECM 호환 판정 | ENT-DOC-003 (실변환 검증 대기) |
| 내보내기 형식 DOCX 단일화 | — |
| 인증 오류 즉시 중단 | ENT-AI-005 (부분) |
| POSCO SSO·P-GPT 설정 구조 (.env) | ENT-AUTH-001 (부분), ENT-AUTHZ-002 (부분) |

**커버리지 판정: 충족 3 / 부분 5 / 미충족 0** (작업 전: 충족 2 / 부분 4 / 미충족 2)

테스트 84개 신규, 프런트엔드 빌드 통과.

## 1. 문서 업로드 파이프라인 오류

산출물 작업 전에 문서 업로드가 실패하고 있었다. 원인이 두 가지 겹쳐 있었다.

### 1.1 OpenAI 401 Unauthorized (환경 문제)

모든 청크 추출이 401로 실패했다. 코드 문제가 아니라 API Key 상태 문제였고, 키 복구 후 파이프라인이 정상 완주했다.

### 1.2 청킹 경로 TypeError (잠복 버그)

```
normalize_and_dedup_user_stories() got an unexpected keyword argument 'is_analyzer'
```

`api/features/ingestion/workflow/phases/user_stories.py:797`

`is_analyzer` 파라미터는 **함수 정의에 존재한 적이 없다.** git 히스토리 200 커밋을 전수 확인했으나 호출부에만 있고 정의부에는 한 번도 없었다. 다른 3개 호출부는 정상이며, 이 줄은 `should_chunk=True`(content_tokens > 3000) 경로에서만 실행되므로 **큰 문서를 올릴 때만 터지는** 버그였다.

**조치:** 인자 제거 (다른 호출부와 동일 동작).

### 1.3 인증 오류가 "청크 실패"로 위장되던 문제 — ENT-AI-005 부분

`except Exception`이 인증 오류까지 삼키고 텍스트를 반씩 재귀 분할하며 재시도해서, 401 한 번이 로그상 수십 개의 무의미한 `chunk.failed`로 증폭되고 정작 원인은 드러나지 않았다.

**조치:** `_is_non_retryable_llm_error()` 추가. 401/403·인증 오류는 즉시 중단하고 `error_type`과 함께 로깅한다.

## 2. 파이프라인 검증기 오판 수정

`api/features/ingestion/hybrid/pipeline_verification.py`

### 2.1 발견한 결함

여러 MATCH를 `WITH`로 엮은 단일 쿼리 구조 때문에, 중간 MATCH가 0건이면 뒤 행이 통째로 사라져 나머지 지표까지 `None`이 됐다. **"0건"과 "측정 실패"를 구분할 수 없었다.**

| 증상 | 실제 상태 |
|---|---|
| `traceability_edges: {}` | PROMOTED_TO 19건, IMPLEMENTS 19건이 실재했으나 US→Rule이 0이라 전부 가려짐 |
| BpmActor 0 → `bpm_ok: false` | Process/Task가 있어도 실패 판정 |
| ReadModel 0 → `es_ok: false` | ES 승격이 정상인데 실패 판정 |

추가로, 사용자가 명시적으로 실행하는 **지연 단계를 필수 게이트로 잡고 있었다.** Rule↔Task 매핑(Agentic Retrieval)은 비용 최적화를 위해 자동 실행하지 않는다(`hybrid_workflow_runner.py:317-328`에 명시). 그런데 `mapping_ok`가 여기에 걸려 있고 `prd_ready`가 analyzer 전용 `SOURCED_FROM`에 걸려 있어, **문서 업로드 경로는 정상 완주해도 영원히 `pipeline_ready: false`**였다.

### 2.2 조치

- 지표별 독립 쿼리로 분리(`_scalar` 헬퍼). 항상 0 이상의 실수를 반환한다.
- 경로 자동 판별: 세션에 Rule이 없으면 `source_kind: "document"`, 있으면 `"analyzer"`.
- `mapping_applicable` 플래그 — 문서 경로에서는 Rule 매핑을 판정에서 제외.
- `grounding_ok` — analyzer는 US→Rule, 문서 경로는 BpmTask→DocumentPassage로 원문 근거를 판정.
- `traceability_edges`에 `task_passage`, `grounding` 블록 추가.

### 2.3 결과

`pipeline_ready: false` → **`true`**

```json
{
  "source_kind": "document",
  "summary": {"pipeline_ready": true, "bpm_ok": true, "mapping_ok": true,
              "mapping_applicable": false, "es_ok": true,
              "grounding_ok": true, "prd_ready": true},
  "traceability_edges": {"promoted_to": 19, "sourced_from": 0,
                         "implements_bc": 19, "task_passage": 38},
  "grounding": {"passages": 39, "grounded_tasks": 19, "ungrounded_tasks": 0}
}
```

## 3. Session 고정 Deliverable API — ENT-DOC-001

`api/features/deliverables/architecture_document.py`, `router.py`

```
GET /api/deliverables/architecture-document?sessionId={id}
```

### 3.1 왜 필요했나

기존 `ExportDocumentTemplate.vue`는 `/api/contexts` **전역**을 읽는다. 같은 Neo4j에 여러 분석 결과가 있으면 서로 다른 세션의 BC가 한 문서에 섞인다. 실제로 검증 그래프에는 analyzer 경로의 잔여 데이터(Table 7, Column 73, FUNCTION 21, Rule 145)가 함께 있었다.

### 3.2 섹션 구성 — 기준 템플릿과 동일

```
userScenario / valueStream / boundedContext / aggregateDesign /
eventStorming / apiSpecification / aggregateDetail / traceabilityMatrix
```

### 3.3 데이터 출처 대응표

| 기준 템플릿 | Robo Architect 출처 |
|---|---|
| `projectInfo.userStory` 원문 문단 | BpmTask의 DocumentPassage (page/heading/char offset/원문 전문) |
| `getValueStreamLinearPages` — `{name, displayName, actor}` 경로 배열 | BpmProcess별 `sequence_index` 정렬 BpmTask + BpmActor |
| BC / Aggregate / Command / Event / Policy / ReadModel | 기존 `build_context_full_tree` 재사용 (계약 변경 없음) |
| `traceabilityMatrixGroups` — `{groups, inferred, unmapped}` | `(UserStory)-[:IMPLEMENTS]->(element)` 직접 엣지 |

ES 계열 섹션은 `build_context_full_tree`를 그대로 재사용했다. 현재 내보내기 템플릿이 이미 이 구조를 렌더링하고 있어, 재구현하지 않고 **범위만 세션으로 좁히는 것**이 목적이다.

### 3.4 추적성 provenance 규칙 — 기준 템플릿 준수

| 값 | 의미 |
|---|---|
| `direct` | 요소에 US 직접 연결(IMPLEMENTS)이 있음 |
| `inferred` | 직접 연결은 없고 상위 Aggregate의 매핑을 상속 |
| (미매핑) | 근거를 찾지 못함 — 그대로 남김 |

기준 템플릿이 명시적으로 제거한 **'BC의 US union' fallback**(근거 없는 요소를 BC의 모든 스토리에 붙이는 대량 거짓 매핑)은 도입하지 않았다. "거짓보다 빈 값이 정직" 정책을 그대로 따른다.

## 4. API 계약 규칙 도출 — ENT-DOC-002

`api/features/deliverables/api_contract.py`

### 4.1 초기 판단 정정

작업 초기에 "API 명세는 유일하게 새 AI 생성 단계가 필요하다"고 판단했으나 **틀렸다.** Command 노드는 이미 필요한 입력을 모두 갖고 있다.

| 입력 | 실측 |
|---|---|
| `category` | Business Logic 12 / Create 2 / Update 2 / Process 3 / External Integration 3 |
| 소속 Aggregate 이름 | 전건 존재 |
| 요청 필드 | `properties` 22/22, `inputSchema` 22/22 |
| `description` | 전건 존재 (full-tree 투영에서 누락돼 있어 추가) |

경로와 메서드는 **결정적으로 계산 가능**하다. LLM을 쓰면 같은 입력에서 다른 경로가 나올 수 있어 납품 문서의 재현성이 오히려 나빠진다.

### 4.2 도출 규칙 — 기준 템플릿 관례 준수

`CommandDefinitionPanel.vue`의 경로 관례를 따랐다.

| category | Method | 경로 |
|---|---|---|
| Create | POST | `/{복수형}` |
| Update | PUT | `/{복수형}/{id}` |
| Delete | DELETE | `/{복수형}/{id}` |
| Business Logic · Process · 미지정 | POST | `/{복수형}/{id}/{commandName}` |
| **External Integration** | — | **제공 API 아님** (외부를 호출하는 방향) |
| ReadModel (단건) | GET | `/{복수형}/{id}` |
| ReadModel (list/collection) | GET | `/{복수형}` |

기준 구현이 커맨드 세그먼트를 `name.toLowerCase()`로 만들어 `composeguidancemessage`처럼 읽기 어려워지는 부분만 camelCase로 바꿨다.

### 4.3 판단이 필요했던 지점

- **External Integration 3건을 엔드포인트로 만들지 않았다.** 외부 인증기관·은행 조회 호출이라 경로와 메서드를 붙이면 "이 시스템이 제공하는 API"라는 거짓 문서가 된다. 목록에는 남기되 `direction: outbound`로 구분한다.
- **경로 충돌 자동 조정.** 한 Aggregate에 Update Command가 둘 이상이면 규칙상 둘 다 `PUT /{복수형}/{id}`가 된다. 실제로 2건 발생했다. 충돌 시 커맨드 이름을 경로에 덧붙여 분리하고(메서드 유지), `pathCollisionsResolved`로 건수를 보고한다.
- **파라미터는 `properties` 우선, `inputSchema` 보완.** "`inputSchema`만 파싱해서 Property만 있는 Command의 요청 필드가 빈 값으로 나오는" 문제를 여기서 정규화했다.
- **`provenance: "derived"` 표기.** 규칙 도출값이지 구현 확정이 아님을 문서가 구분할 수 있게 한다.

### 4.4 실측 결과

```
Command 22 → 제공 API 19 / 외부 연동 3
ReadModel 10 → 조회 API 10
파라미터 없는 Command 0 / 경로 충돌 조정 2

POST   /autoDebitApplications                                    자동납부 신청서 접수   [Create]
PUT    /autoDebitApplications/{id}/rejectAutoDebitApplication    자동납부 신청 거부     [Update·충돌조정]
POST   /autoDebitApplications/{id}/validateAutoDebitApplication  신청 정보 검증         [Business Logic]
GET    /autoDebitApplicationHistories                            자동납부 신청 이력     [목록]
GET    /autoDebitApplicationDetails/{id}                         자동납부 신청서 상세   [단건]
(외부연동)                                                        외부 본인확인 요청     [External Integration]
```

## 5. Aggregate 내보내기 (기준: CodeGenerator)

`api/features/deliverables/aggregate_export.py`

```
GET /api/deliverables/aggregates?sessionId={id}
```

기준 기능은 `CodeGenerator.vue`의 `exportAggregatesWord()`다. Aggregate 요소를 단순화한 JSON 배열로 만들어 내려받게 하며, 코드 생성기나 외부 도구가 소비하는 형태다.

### 5.1 payload 구조 — 기준 구현 키 유지

```json
{
  "id", "name", "displayName",
  "namePlural", "namePascalCase", "nameCamelCase",
  "boundedContextId", "boundedContextName",
  "aggregateRoot": { "fieldDescriptors": [...], "entities": [...] }
}
```

`fieldDescriptors`는 기준 구현 `_simplifyFieldDescriptors`의 allowedKeys 16개를 그대로 쓰고, 중복 제거 기준(`name::className::isKey`)과 빈 값 재귀 제거(`_omitEmptyValues`)도 동일하게 맞췄다.

| 기준 구현 | Robo Architect 출처 |
|---|---|
| `aggregateRoot.fieldDescriptors` | Aggregate `properties` (`isRequired` → `isNullable` 반전) |
| `entities` (isEnum) | `enumerations` — 항목 문자열을 `{name, value}` 양쪽에 채움 |
| `entities` (isVO) | `valueObjects` — `fields` → `fieldDescriptors` |
| `entities[].relations` | **해당 데이터 없음 — 생략** |

### 5.2 판단이 필요했던 지점

- **속성 타입 해석.** Aggregate Property의 `type`이 `Object`/`String` 같은 일반 타입으로만 저장돼 있어 그대로 내보내면 코드 생성기가 쓸 수 없다. 속성 이름을 PascalCase로 바꿔 **정확히 일치하는** VO/Enum이 있을 때만 연결한다(`paymentMethodInfo` → `PaymentMethodInfo`). 부분 일치나 유사도 추정은 하지 않는다 — `status` → `Status`는 `OrderStatus`와 일치하지 않으므로 그대로 둔다. 해석 건수는 `resolvedReferences`로 보고한다.
- **`False`와 `0`은 보존.** 빈 값 제거를 따르되 `isKey: false`는 남긴다. 지우면 소비자가 "키 여부 미상"과 "키 아님"을 구분할 수 없다.
- **entity `type` 미기재.** 기준 구현은 `org.uengine.uml.model.*` 같은 uengine 클래스명을 넣지만 Robo Architect에는 그 값이 없다. 지어내면 출처를 속이는 문서가 되므로 생략했다.
- **`invariants` / `exceptions` 추가.** 기준 구현에는 없으나 Robo Architect가 보유한 설계 정보이고 키 이름이 명확해 기존 소비자를 깨지 않는다.

### 5.3 실측 결과

```
Aggregate 3 / field 10 / 참조 해석 2
paymentMethodInfo: Object → PaymentMethodInfo (isVO, referenceClass)
```

### 5.4 출력 형식

기준 구현과 같이 JSON 문자열을 **DOCX 본문**에 텍스트로만 담는다. 서식 없이 한 줄 = 한 문단, Courier New 고정폭이라 들여쓰기가 유지된다. 파일명은 `Aggregate정의서-{날짜}.docx`.

Backend 엔드포인트는 JSON을 반환하고 DOCX로 감싸는 것은 클라이언트에서 한다(기준 구현과 동일한 분담). 코드 생성기처럼 원본 JSON이 필요한 소비자는 엔드포인트를 직접 호출하면 된다.

## 6. DOCX 정본화 및 ECM 호환 검증 — ENT-DOC-003

`api/features/deliverables/docx_normalize.py`

```
GET  /api/deliverables/docx-normalization/status     정본화 가능 여부
POST /api/deliverables/docx-normalization/inspect    ECM 호환성 판정
POST /api/deliverables/docx-normalization/normalize  LibreOffice 재직렬화
```

기준 구현: `run_healcheck_server.py`의 `/api/documents/normalize-docx` + `DocumentPreviewDialog.vue`의 `normalizeDocxViaBackend()`.

### 6.1 문제 — 실데이터로 확인함

브라우저에서 `docx` + `jszip`으로 만든 파일은 Word로는 열리지만 **정본 OOXML 패키지가 아니다.** Apache Tika 같은 엄격한 검출기는 이를 `application/zip`으로 판정하고, ECM은 "Word 문서가 아니다"라며 등록을 거부한다.

우리 exporter가 쓰는 것과 **동일한 `docx` 라이브러리로 파일을 생성해 판정기에 넣어본 결과**, 기준 구현이 지목한 두 결함이 그대로 재현됐다.

```json
{
  "ecmCompatible": false,
  "firstEntry": "word/",
  "contentTypesFirst": false,
  "hasDirectoryEntries": true,
  "entryCount": 22
}
```

즉 이 문제는 msaez 고유가 아니라 **현재 Robo Architect 산출물에도 그대로 존재한다.**

### 6.2 구현

| 함수 | 역할 | LibreOffice 필요 |
|---|---|---|
| `normalize_docx()` | soffice headless 재직렬화 | 필요 |
| `inspect_docx_package()` | ECM 호환성 판정 + 사유 | **불필요** |
| `compare_documents()` | 전후 유실 검증 | **불필요** |

기준 구현에서 그대로 가져온 것:

- `-env:UserInstallation`을 호출마다 분리. soffice는 프로필 단위로 싱글톤 락을 잡아, 프로필을 공유하면 동시 요청이 서로를 막는다.
- `HOME`을 임시 디렉토리로 격리 — non-root 컨테이너 대응.
- 빈 결과를 성공으로 반환하지 않음. 변환 실패가 "성공적으로 빈 문서"로 둔갑하면 ECM에 껍데기가 등록된다.

추가한 것:

- **LibreOffice 부재와 변환 실패를 구분.** 전자는 503(환경 설정 문제), 후자는 500(문서 문제).
- **`/status` 사전 조회.** 변환을 시도하기 전에 가능 여부를 알 수 있다.
- **`/inspect` 판정기.** LibreOffice 없이도 산출물이 등록 가능한 상태인지 확인할 수 있어, 정본화 도입 전에 문제를 실증할 수 있다.
- **전후 유실 검증.** 문단·표·행·이미지·본문 길이를 비교한다. LibreOffice는 문단을 재구성하므로 "동일"이 아니라 **감소**만 문제로 본다. 공백 정규화를 유실로 오판하지 않도록 본문은 공백 제거 후 비교하고 1% 미만 감소는 허용한다. 결과는 응답 헤더 `X-Docx-Lossless` / `X-Docx-Losses`로 전달한다(본문이 파일이라 JSON을 실을 수 없다).

### 6.3 프런트엔드 폴백 정책

기준 구현과 동일하게 **정본화 실패 시 원본으로 폴백**해 다운로드 자체는 되게 하고, ECM 등록이 거부될 수 있음을 알린다. Word 산출물과 Aggregate 정의서 양쪽에 같은 경로를 적용했다.

`captureExporter.exportToWord()`가 파일을 직접 저장하던 것을 **blob을 반환**하도록 바꿔, 저장 직전에 정본화를 끼워 넣을 수 있게 했다.

### 6.4 미검증 항목

**soffice 실제 변환은 미검증이다** — 개발 머신에 LibreOffice가 없다. 검증 절차는 `enterprise-todo.md` §2에 있다.

## 7. 내보내기 화면·문서 반영

| 파일 | 변경 |
|---|---|
| `ExportDocumentTemplate.vue` | 섹션 5개 → 7개. 밸류 스트림, 추적성 매트릭스, 사용자 스토리 원문 근거, API 명세에 Endpoint 계약 표 추가. 목차·섹션 번호 연동 |
| `ExportDocumentDialog.vue` | exporter 데이터 전달, Aggregate DOCX 내보내기, DOCX 외 경로 주석 처리, 정본화 삽입 |
| `exporters/captureExporter.js` | **실제 DOCX 경로.** 원문 근거·밸류 스트림·Endpoint 계약·추적성 3종 섹션 추가, blob 반환으로 변경 |
| `exporters/wordExporter.js` | 동일 섹션 추가 |

### 7.1 폴백 정책

활성 Hybrid Session이 있으면 Deliverable API로 로드하고, 세션이 없거나(수동 설계 등) 조회에 실패하면 **기존 전역 조회로 되돌아간다.** 기존 동작을 깨지 않는다.

### 7.2 범위 오염 차단

`allUserStories`가 Navigator의 전역 User Story 목록을 '미배정'으로 합치고 있었다. 세션 고정 모드에서는 다른 세션의 스토리가 딸려 들어오므로 차단했다.

### 7.3 내보내기 형식 DOCX 단일화

기업 납품 기준에 맞춰 산출물 내보내기를 **DOCX 하나로 고정**했다. 나머지 경로는 **삭제하지 않고 주석 처리**해 복구 가능한 상태로 남긴다.

| 경로 | 상태 |
|---|---|
| Word (.docx) | 유지 |
| Aggregate (.docx) | 유지 (신규) |
| PDF / PowerPoint / 정책서(.html) | 주석 처리 |

- 드롭다운 메뉴 항목과 함수(`exportToPDF` / `exportToPPT` / `exportToHTMLPolicy`)를 각각 주석 처리하고 사유를 한 줄 남겼다.
- PDF 전용 인쇄 스타일 `EXPORT_CSS`는 사용처가 없어졌지만 복구를 위해 남기고 주석으로 표시했다.
- `captureExporter.js`의 `exportToPPT` 구현은 그대로 둔다 — 호출부만 끊긴 상태다.

## 7.4 POSCO SSO·P-GPT 설정 구조 — ENT-AUTH-001 부분

기준 구현은 data-gateway 컨테이너의 `docker-compose.yml` 환경 블록에 값을 박았다. Robo Architect는 게이트웨이 컨테이너가 없고 FastAPI가 직접 요청을 받으므로 **같은 계약을 `.env`로 옮겼다.** 키 이름은 현장 운영자가 두 시스템을 오갈 수 있도록 기준 구현과 동일하게 유지했다.

### 7.4.1 임베딩 라우팅 분리 — P-GPT 필수 선행

`api/platform/embeddings.py`

P-GPT 같은 사내 게이트웨이는 OpenAI 호환이지만 **임베딩을 제공하지 않는다.** 그런데 `OpenAIEmbeddings()`가 `OPENAI_BASE_URL`을 그대로 읽으므로, Chat을 게이트웨이로 돌리면 임베딩까지 따라가 런타임에 깨진다.

호출 지점 2곳(`hybrid/mapper/embeddings.py`, `change_planning_runtime.py`)을 공통 팩토리로 모으고 자기 endpoint/key 쌍을 갖게 했다.

| 설정 | 동작 |
|---|---|
| `EMBEDDING_API_KEY` 설정 | 이 키로, `EMBEDDING_BASE_URL`(미설정 시 OpenAI 본점) |
| `EMBEDDING_API_KEY` 미설정 | `OPENAI_*`를 그대로 사용 — **기존 동작 불변** |

기준 구현의 키 이름 `OPENAI_EMBEDDING_API_KEY`도 별칭으로 인정한다.

**위험 조합 감지.** Chat이 게이트웨이로 가는데 임베딩 전용 설정이 없으면 조용히 깨진다. 이 상태를 기동 로그(`platform.embeddings.shared_endpoint`)와 진단 API로 드러낸다.

### 7.4.2 SWP(POSCO) SSO

`api/features/auth/`

OIDC가 아닌 **HTTP 인증 토큰 방식**이라 표준 OAuth 라이브러리를 쓸 수 없다.

```
1) 사용자를 redirect.jsp 로 보내 로그인
2) SWP 가 콜백으로 ssoToken 전달 (form POST, 환경에 따라 GET)
3) isValidSSO.jsp 에 Cookie(SWP-H-SESSION-ID) 로 재검증 → 사용자정보 CSV
```

```
GET      /api/auth/provider     현재 provider·임베딩 라우팅 상태 (진단)
GET      /api/auth/sso/init     SWP 로그인 URL 발급
GET|POST /api/auth/sso/valid    콜백 — ssoToken 검증
```

**현장 필드 드리프트 대응을 그대로 가져왔다.** 이게 이 로직의 핵심이라 CSV 파싱을 순수 함수로 분리해 네트워크 없이 검증할 수 있게 했다.

- 스펙 표 인덱스는 `0=iv-user, 1=sp_empno, 4=seealso, 8=displayname, 9=mail`이지만, 현장 피드가 한 칸 밀려 오는 사례가 있다.
- **이메일**은 `@`를 포함한 토큰을 직접 찾는다. **영문성명**은 그 앞 토큰을 쓰고 URL 디코드한다.
- 사번(1)과 로그인 ID(0)는 드리프트 지점 앞이라 인덱스 고정이 안전하다.
- 필드 인덱스는 재빌드 없이 `SWP_IDX_*`로 조정한다.

**판단이 필요했던 지점**

- **`AUTH_PROVIDER` 기본값 `none`.** 기존 `X-User-*` 헤더 동작을 그대로 유지한다. 설정하지 않으면 아무것도 바뀌지 않고, 비활성 상태에서 SSO 라우트는 404다.
- **콜백 허용 목록.** `callbackUrl`을 검증 없이 SWP로 실으면 Open Redirect가 된다(ENT-AUTHZ-002). `AUTH_CALLBACK_ALLOWLIST`로 Origin을 검증하고, 목록이 비면 loopback만 허용한다 — 기본값이 열려 있으면 안 된다.
- **식별자가 없으면 이메일로 대체하지 않는다.** 사번도 로그인 ID도 없으면 사용자를 특정할 수 없다. 불안정한 키로 계정을 만들면 나중에 병합 사고가 난다.
- **원문 응답을 로그에 남기지 않는다.** 기준 구현은 첫 연동 확인용으로 raw를 콘솔에 찍는다. 사용자 정보가 포함되므로 길이만 기록한다.

**제외한 범위** — 세션/JWT 발급과 승인 상태 판정은 사용자 저장소 설계가 선행돼야 해서 빼고 신원 확인까지만 담당한다(ENT-AUTH-002).

### 7.4.3 `.env` 계약

```
# Chat 라우팅
LLM_PROVIDER=openai
LLM_MODEL=<P-GPT 제공 모델명>
OPENAI_API_KEY=<P-GPT Key>
OPENAI_BASE_URL=http://aigpt.posco.net/gpgpta01-gpt/v1   # 운영계
LLM_MAX_OUTPUT_TOKENS=0

# 임베딩 — P-GPT 미지원이므로 반드시 분리
EMBEDDING_API_KEY=<실제 OpenAI Key>

# 인증
AUTH_PROVIDER=swp
AUTH_CALLBACK_ALLOWLIST=https://robo.posco.net
SWP_SSO_REDIRECT_URL / SWP_SSO_VALID_CHECK_URL / SWP_SSO_LOGIN_URL
SWP_IDX_ID / EMPNO / DISPLAYNAME / MAIL / DEPT
SWP_EMAIL_FALLBACK_DOMAIN=posco.local
```

P-GPT 개발계는 `http://taigpt.posco.net/gpgpta01-gpt/v1`이다.

## 8. 실측 결과 (세션 `a149dfd5`)

### 8.1 생성 데이터

```
BpmSession 1 / BpmProcess 2 / BpmActor 4 / BpmTask 19 / BpmGateway 4
DocumentPassage 39 / GlossaryTerm 18
UserStory 19 / BC 3 / Aggregate 3 / Command 22 / Event 40 / Policy 18 / ReadModel 10
```

### 8.2 완결성

| 항목 | 결과 |
|---|---|
| Command Event 미연결 | 0/22 |
| Command inputSchema 누락 | 0/22 |
| Aggregate property / invariant 누락 | 0/3, 0/3 |
| BpmTask Actor 배정 | 19/19 |
| BpmTask `source_section` | 19/19 |
| BpmTask `document_passages` | 19/19 (각 2건) |
| BpmTask ↔ Rule 매핑 | 0/19 (문서 경로 — 해당 없음) |

### 8.3 추적성 체인

```
DocumentPassage(39) ←SOURCED_FROM─ BpmTask(19) ─PROMOTED_TO→ UserStory(19)
                                                      │
                                                 IMPLEMENTS
                                                      ↓
                                    BC(3) → Aggregate(3) → Command/Event/Policy/ReadModel
```

| 지표 | 값 |
|---|---:|
| 추적 대상 요소 | 88 |
| 직접 매핑 | 48 |
| 추론 매핑 | 40 |
| 미매핑 | 0 |
| 매핑된 User Story | 19/19 |
| 직접 매핑률 | 54.6% |

## 9. 커버리지 판정 이력

| 영역 | 정적 검증(08-25) | 실측 후(08-27) |
|---|---|---|
| 이벤트 스토밍 모델 | 충족 | 충족 |
| Aggregate 상세 | 충족 | 충족 |
| **API 명세** | 부분 | **충족** — 규칙 도출로 경로·메서드 확보 |
| 사용자 시나리오 | 부분 | 부분 → 원문 근거 출력 완료, 서술형 시나리오는 미지원 |
| **Value Stream·프로세스** | **미충족** | 부분 → 데이터 완비, 출력 완료 |
| **추적성 매트릭스** | **미충족** | 부분 → 체인 연결 확인, 출력 완료 |
| Bounded Context 정의 | 부분 | 부분 (분해 근거 미영속화 — `enterprise-todo.md` ENT-DOC-002) |
| Aggregate 설계 | 부분 | 부분 (대안·선택 사유 없음 — 동일) |

**충족 3 / 부분 5 / 미충족 0** (이전: 충족 2 / 부분 4 / 미충족 2)

### 9.1 정적 검증에서 정정된 서술

2026-08-25 커버리지 리뷰는 코드 계약만 보고 작성돼 실데이터로 확인되지 않은 상태였다. 실측 결과 다음 세 가지가 사실과 달랐다.

- **"Backend에 BPM Task, User Story, Rule, BC 사이의 추적 관계가 존재한다"** — Rule 연결은 문서 업로드 경로에 존재하지 않는다. 세션 Rule 자체가 생성되지 않으며, 원문 근거는 DocumentPassage 경로가 담당한다.
- **"User Story 및 BPM Task 기준 설계 추적 API도 존재한다"** — 기존 `/api/graph/traceability/{node_id}`는 **코드 역추적용**(DDD Node → BC → US → BusinessLogic → Function → Table)이다. `_US_QUERIES`에 UserStory 진입점이 없어 문서→설계 정방향 매트릭스에는 쓸 수 없다.
- **Read Model 미생성 판단** — 정상 생성된다. 백엔드 응답 키는 `readmodels`(소문자 m)이고 exporter도 같은 키를 쓴다.

## 10. 검증

- 신규 테스트 84개 통과
  - `test_pipeline_verification.py` — 경로별 판정, 연쇄 MATCH 회귀, ReadModel 0 케이스, 빈 세션
  - `test_architecture_document.py` — 요소 중복 제거, direct/inferred/unmapped 분류, Task 정렬, 섹션 키 일치
  - `test_api_contract.py` — 복수화, category별 경로·메서드, 외부 연동 제외, 경로 충돌 조정, 파라미터 fallback, 깨진 스키마
  - `test_aggregate_export.py` — payload 구조, nullable 반전, 참조 해석(일치/불일치), 중복 제거, 빈 값 제거 시 `False` 보존
  - `test_docx_normalize.py` — ECM 호환성 판정(정본/비정본/디렉토리 엔트리/비-ZIP), 유실 비교(표·이미지·본문), LibreOffice 부재 오류
  - `auth/test_swp.py` — CSV 파싱(스펙 순서·필드 드리프트·이메일 합성), provider 별칭, 콜백 허용목록(부분 일치 도메인 차단)
  - `platform/tests/test_embeddings_routing.py` — 게이트웨이 위험 조합 감지, 전용 키 고정, 키 비노출
- 프런트엔드 빌드 성공 (5,268 modules)
- 라이브 엔드포인트 확인 — `architecture-document` 200, `aggregates` 200, `docx-normalization/status` 200, `normalize` 503(LibreOffice 부재, 의도된 경로)

## 11. 변경 파일 목록

### Backend

| 파일 | 구분 |
|---|---|
| `api/features/ingestion/workflow/phases/user_stories.py` | 수정 — TypeError, 비재시도 오류 처리 |
| `api/features/ingestion/hybrid/pipeline_verification.py` | 재작성 — 지표 분리, 경로별 판정 |
| `api/features/ingestion/hybrid/test_pipeline_verification.py` | 재작성 — 테스트 5개 |
| `api/features/deliverables/__init__.py` | 신규 |
| `api/features/deliverables/architecture_document.py` | 신규 — 스냅샷 빌더 |
| `api/features/deliverables/api_contract.py` | 신규 — API 계약 규칙 도출 |
| `api/features/deliverables/aggregate_export.py` | 신규 — Aggregate JSON payload 빌더 |
| `api/features/deliverables/docx_normalize.py` | 신규 — DOCX 정본화 / ECM 판정 |
| `api/features/deliverables/router.py` | 신규 — 조회·정본화 라우트 |
| `api/features/deliverables/test_architecture_document.py` | 신규 — 테스트 6개 |
| `api/features/deliverables/test_api_contract.py` | 신규 — 테스트 15개 |
| `api/features/deliverables/test_aggregate_export.py` | 신규 — 테스트 10개 |
| `api/features/deliverables/test_docx_normalize.py` | 신규 — 테스트 15개 |
| `api/platform/neo4j_helpers.py` | 수정 — full-tree Command 투영에 `description` 추가 |
| `api/main.py` | 수정 — 라우터 등록 |
| `api/features/auth/config.py` | 신규 — provider 전환·SWP 설정·콜백 허용목록 |
| `api/features/auth/swp.py` | 신규 — SWP 클라이언트·CSV 파서 |
| `api/features/auth/router.py` | 신규 — SSO 라우트·진단 |
| `api/features/auth/test_swp.py` | 신규 — 테스트 26개 |
| `api/platform/embeddings.py` | 신규 — 임베딩 라우팅 분리 |
| `api/platform/tests/test_embeddings_routing.py` | 신규 — 테스트 7개 |
| `api/platform/env.py` | 수정 — `env_list` 추가 |
| `api/features/ingestion/hybrid/mapper/embeddings.py` | 수정 — 공통 팩토리 사용 |
| `api/features/change_management/planning_agent/change_planning_runtime.py` | 수정 — 공통 팩토리 사용 |
| `.env.example` | 수정 — `LIBREOFFICE_BIN`, `DOCX_NORMALIZE_TIMEOUT_S`, POSCO SSO·P-GPT 섹션 |

### Frontend

| 파일 | 구분 |
|---|---|
| `features/exportDocument/ui/ExportDocumentTemplate.vue` | 수정 — 섹션 2개 추가, 세션 로딩, 범위 차단, Endpoint 계약 표 |
| `features/exportDocument/ui/ExportDocumentDialog.vue` | 수정 — exporter 데이터 전달, Aggregate DOCX, DOCX 단일화, 정본화 |
| `features/exportDocument/ui/exporters/captureExporter.js` | 수정 — DOCX 섹션 추가, blob 반환 |
| `features/exportDocument/ui/exporters/wordExporter.js` | 수정 — 동일 섹션 추가 |
