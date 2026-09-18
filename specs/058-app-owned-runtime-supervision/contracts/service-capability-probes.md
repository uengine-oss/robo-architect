# 계약 — 서비스별 기능 프로브

**Feature**: 058 | **Date**: 2026-09-17

## 왜 이 계약이 있나

`compose up --wait` 가 8/8 healthy 를 보고한 상태에서 pdf2bpmn 이 502 를 냈다(실측).
healthcheck 는 **떴는지**만 본다. 이 계약은 **일할 수 있는지**를 무엇으로 볼지 정한다.

## 공통 규칙

```
싸다        LLM 을 부르지 않는다. 기본 제한 3초
진짜다      그 서비스가 실제로 쓰는 의존을 지난다 (자격증명·업스트림·저장소)
부작용 없다 쓰기를 하지 않는다. 남의 데이터를 안 건드린다
존재한다    **그 서비스가 실제로 가진 경로만 쓴다.** 지어내지 않는다
```

> 마지막 줄은 실측 사고에서 나왔다. 09-17 에 `/robo/health` 라는 없는 경로를 만들어
> 불렀다가 500 을 보고 게이트웨이 결함으로 오독했다.

**결과는 네 값이다** — `pass` · `fail` · `error` · `skipped`.
`error`(프로브가 못 돔)와 `fail`(돌았는데 못 맞춤)을 **절대 뭉치지 않는다.**

## 서비스별

### graph (저장소)

서비스 id 는 **`graph`** 다. `neo4j` 도 `ontological` 도 아니다 — **엔진 이름이 아니라
역할 이름**이어야 한다. 앱이 보는 것은 Neo4j **프로토콜**을 말하는 Bolt 게이트웨이이고,
그 뒤가 무엇인지는 앱의 관심사가 아니다. id 를 엔진에 묶으면 엔진을 바꿀 때마다 계약이
깨진다(실제로 2026-09-17 에 Neo4j → Ontological 로 바뀌었다).

```
health      bolt 포트가 열려 있다
capability  **설정된 graph 에 질의를 한 번 던진다**
```

**포트 열림으로 판정하면 안 되는 이유가 실측으로 있다.** bolt 핸드셰이크는 성공하는데
그 database 가 없으면 `Neo.ClientError.Database.DatabaseNotFound` 가 **나중에** 난다.
런처 연결 테스트가 통과하고 화면이 전부 500 이 되던 그 증상이다.

**건수는 판정에 안 쓴다.** 갓 만든 graph 는 0 건이 정상이다. 질의가 **돌았는지**가
판정이다 — 0 건을 실패로 보면 정상 부재를 고장으로 읽는다.

판정 표:

```
bolt 닫힘                health=fail · capability=skipped
자격증명·graph 이름 없음  capability=error   (재지 못했다)
드라이버 없음             capability=error   (재지 못했다)
인증 실패                 capability=fail
graph 없음                capability=fail    ← T022 의 인수 기준
질의 성공                 capability=pass
```

비밀번호는 **인자로 받지 않는다** — `ps` 와 셸 기록에 남는다. `ROBO_NEO4J_PASSWORD`
환경 변수로 받고, 상세 문자열에도 싣지 않는다.

`--compare-health` 가 보는 compose 컨테이너 이름은 서비스 id 와 다르다. 설치본은
`graph-bolt`, 되돌아간 Neo4j 구성은 `neo4j` 다 — **후보를 순서대로 본다.** 한 이름으로
못 박으면 다른 구성에서 조용히 "컨테이너 없음"이 되고 대조군이 통째로 무의미해진다.

### gateway

```
health      /actuator/health
capability  업스트림 왕복 — 직접 호출과 **같은 코드**가 오는가
```

**같은 코드 비교가 판정 기준이다.** 절대 코드로 보지 않는다.

```
/api/gateway/robo/health        404   analyzer 도달 (FastAPI 형식) — 정상
/api/gateway/antlr/             500   parser 직접도 500 — 정상
```

비교는 **같은 자리에서** 센다: 게이트웨이 경유 응답 코드 ↔ 컨테이너 안 직접 호출 코드.

### analyzer

```
health      GET /
capability  설정된 LLM 자격증명이 살아 있는가 (모델 목록 등 값싼 호출)
            + 대상 graph 에 붙을 수 있는가
```

분석 실행에는 `ROBO_LLM_CONFIG`·`ROBO_LLM_API_KEY` 가 필요하다. 없으면 **화면·API 는
뜨고 분석만 실패한다** — 그 실패를 기동 시점에 드러낸다.

### catalog · fabric

```
health      자기 health 경로
capability  graph 연결이 실제로 열리는가
```

### parser

```
health      GET /
capability  공유 데이터 루트(/data)에 쓸 수 있는가
```

파서는 작업 폴더를 **비우고 다시 쓴다.** 쓸 수 없으면 분석이 조용히 빈다.

### pdf2bpmn

```
health      GET /healthz        ← 이것만으로는 부족하다는 것이 R1 의 실측이다
capability  자격증명 유효성 — 설정된 LLM 엔드포인트에 값싼 인증 호출
```

**실제 BPMN 생성을 프로브로 쓰지 않는다** — 12.6초·비용.

### architect (호스트 프로세스)

```
health      GET /api/health
capability  graph 분리 판정 통과 + 설계 graph 읽기
```

## 주기와 시점

```
기동 시     전부 한 번 (의존 순서대로)
평상시      5초마다 health · 60초마다 capability
사건 발생시 컨테이너 exit / 백엔드 crash → 즉시
사용자 요청 "다시 시도" 를 누르면 즉시
```

**capability 를 5초마다 돌리지 않는다** — 자격증명 확인이라도 외부 호출이다.

## 실패를 화면 문장으로

프로브 실패는 **반드시** 셋을 만든다(FR-004).

```
무엇이    서비스 이름
무엇을 못 쓰게 되나   capability 목록
사용자가 할 수 있는 일  구체적 동작
```

예.

```
pdf2bpmn — 자격증명이 거부됐습니다 (401)
  못 쓰는 기능: 문서에서 업무흐름 생성
  할 수 있는 일: 모델 연결 설정을 확인하세요. 설계·분석은 계속 쓸 수 있습니다.
```

**비밀정보를 문장에 넣지 않는다**(FR-011). 키·비밀번호·토큰은 길이나 지문으로도 남기지
않는다.

## 검사 방법 (SC-008)

각 프로브는 **결함을 심어 무는 것**을 확인한 뒤에 "검증했다"고 쓴다.

```
자격증명을 깨뜨린다      → capability 가 fail, health 는 여전히 pass
컨테이너를 죽인다        → health 가 fail
프로브 의존을 없앤다     → error (fail 아님)  ← 이 구분이 무는지 반드시 본다
```

**파괴적 결함은 심지 않는다.** 실제 데이터를 지우는 경로에는 절대.
