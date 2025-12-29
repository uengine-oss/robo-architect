아래는 지금 말씀하신 내용을 **그대로 제품 요구사항으로 정제**한
👉 **UI 중심 PRD (Navigator + Event Storming Canvas 방식)** 입니다.
(기술 스택: **Vue.js 3 + Vue Flow + Neo4j** 전제)

---

# PRD

## Product UI: Ontology-based Event Storming Navigator & Canvas

---

## 1. 목적 (Why)

기존 방식은
❌ **전체 요구사항 / 전체 이벤트 스토밍 다이어그램을 한 번에 펼쳐서 보는 방식** 이었음.

새로운 UI는
✅ **사용자가 “보고 싶은 객체만 선택”해서 그 관계만 집중적으로 탐색**하도록 한다.

> **전체를 보는 UI가 아니라,
> 선택한 객체들의 관계가 ‘드러나는 UI’**

---

## 2. 핵심 UX 컨셉

### 🎯 핵심 아이디어

* 좌측: **구조적 내비게이터 (Tree Navigator)**
* 우측: **동적 Event Storming Canvas**
* 사용자는:

  * 객체를 **열어보고**
  * **끌어다 놓고**
  * 그 결과로 **관계가 시각화된 Event Storming 다이어그램을 확인**

---

## 3. 전체 화면 레이아웃

```
+------------------------------------------------------+
| Top Bar (Project / View Mode / Filter)               |
+---------------------+--------------------------------+
| Left Navigator      | Right Canvas                   |
| (Tree Structure)    | (Event Storming Diagram)       |
|                     |                                |
| BC                  |  [Command] -> [Event]          |
|  └ Aggregate        |        ↑ Policy                |
|     └ Command       |                                |
|     └ Event         |                                |
|                     |                                |
+---------------------+--------------------------------+
```

---

## 4. Left Panel – Bounded Context Navigator

### 4.1 구조 (Tree Hierarchy)

좌측 내비게이터는 **Ontology 기반 트리 구조**를 가진다.

```
BoundedContext
 ├─ Aggregate
 │   ├─ Command
 │   ├─ Event
 │   └─ Policy (optional)
 └─ Aggregate
```

### 4.2 Tree Node 타입

| Node Type      | 설명           |
| -------------- | ------------ |
| BoundedContext | 최상위 도메인      |
| Aggregate      | BC 내부의 핵심 개념 |
| Command        | 행위           |
| Event          | 상태 변화        |
| Policy         | 이벤트-커맨드 연결   |

> ⚠️ **Label이 아니라 Type 기반 렌더링 필수**

---

### 4.3 Tree Interaction

| 동작    | 동작 결과      |
| ----- | ---------- |
| 클릭    | 노드 정보 미리보기 |
| 더블 클릭 | 캔버스에 추가    |
| 드래그   | 캔버스로 객체 이동 |
| 확장/접기 | 하위 구조 탐색   |

---

## 5. Right Panel – Event Storming Canvas

### 5.1 Canvas 역할

* **선택된 객체들만 포함하는 부분 Event Storming View**
* 전체 시스템이 아니라 **Contextual View** 제공

---

### 5.2 Canvas 기본 규칙

#### 1️⃣ 객체 단위 렌더링 규칙

| 끌어다 놓은 객체      | 캔버스 결과                                  |
| -------------- | --------------------------------------- |
| Aggregate      | 해당 Aggregate + 연결된 Command/Event/Policy |
| BoundedContext | BC 전체 Aggregate 구조                      |
| Command        | Command + 발생 Event                      |
| Event          | Event + Triggering Policy               |

---

#### 2️⃣ Event Storming 레이아웃 규칙

* **좌 → 우**

  * Command → Event
* **상 → 하**

  * Policy는 Command 위에 배치
* 동일 Aggregate는 시각적 Grouping

---

### 5.3 관계 자동 보완 (Auto-Completion)

캔버스에 이미 그려진 객체들 사이에
**Ontology Graph 상 Relation이 존재하면 자동으로 연결선 생성**

예:

* Policy → Event (TRIGGERS)
* Command → Event (EMITS)

> ❗ **“전체 그래프를 그리지 않고,
> 현재 캔버스에 존재하는 노드들 사이에서만 관계를 활성화”**

---

## 6. Drag & Drop 시나리오 예시

### 시나리오 1: Aggregate 단위 탐색

1. 좌측:

   ```
   Order BC
    └─ Order Aggregate
   ```
2. Order Aggregate를 우측으로 Drag
3. 결과:

   * Order Aggregate
   * OrderCommand
   * OrderPlacedEvent
   * 관련 Policy
   * Event Storming 형태로 자동 배치

---

### 시나리오 2: BC 단위 탐색

1. Inventory BC를 Drag
2. 결과:

   * Inventory BC 전체 Aggregate 구조 렌더링
3. 이미 캔버스에 Order BC가 있다면:

   * Policy / Event 간 Trigger 관계 자동 연결

---

## 7. Backend 연동 요구사항 (Neo4j)

### 7.1 기본 API 요구

| API                     | 설명             |
| ----------------------- | -------------- |
| GET /contexts           | BC 목록 조회       |
| GET /contexts/{id}/tree | BC 하위 트리       |
| GET /graph/subgraph     | 선택 노드 기준 서브그래프 |

---

### 7.2 서브그래프 조회 조건

* Input: Node IDs
* Output:

  * Nodes (Type, Name, Meta)
  * Relations (Type, Direction)

> ❗ **전체 그래프 조회 금지**
> 항상 “선택 기반 서브그래프”만 요청

---

## 8. 기술 스택 요구사항

### Frontend

* **Vue.js 3**
* **Vue Flow**

  * Custom Node Type
  * Custom Edge Type
* 상태 관리: Pinia
* Drag & Drop: HTML5 DnD or Vue Flow DnD

---

### Node Rendering

| Node Type | UI Style                   |
| --------- | -------------------------- |
| Command   | Blue Box (Left)            |
| Event     | Orange Box (Right)         |
| Policy    | Yellow Box (Above Command) |
| Aggregate | Container Group            |

---

## 9. Non-Functional Requirements

* 대규모 그래프에서도 **부분 렌더링 성능 유지**
* 캔버스는 **Stateless View**

  * 새로고침 시 다시 Drag 필요
* UI는 **편집기(Edit)보다 탐색기(Explorer)에 초점**

---

## 10. Out of Scope (이번 PRD 범위 제외)

* 실시간 협업
* 자동 레이아웃 최적화
* 전체 시스템 자동 렌더링
* 코드 생성 버튼

---

## 11. 성공 기준 (Acceptance Criteria)

* [ ] BC / Aggregate Tree 탐색 가능
* [ ] Drag 시 우측 Event Storming 자동 생성
* [ ] Policy / Event 관계 자동 연결
* [ ] 여러 BC를 동시에 캔버스에 배치 가능
* [ ] 사용자가 “이 관계가 왜 생겼는지” 직관적으로 이해 가능

---

## 12. 한 줄 요약 (UI 컨셉 문장)

> **“전체를 그리지 말고,
> 보고 싶은 것만 끌어다 놓아
> 관계를 드러내는 Event Storming UI”**

---

## 다음 단계로 바로 가능

원하시면 바로 이어서:

1. **Vue Flow Node / Edge 컴포넌트 설계**
2. **Neo4j Cypher (서브그래프 조회 쿼리)**
3. **Drag & Drop 이벤트 흐름 시퀀스 다이어그램**
4. **UX 와이어프레임 (텍스트 기반)**

👉 다음으로 어디까지 내려갈지 말씀 주세요.
