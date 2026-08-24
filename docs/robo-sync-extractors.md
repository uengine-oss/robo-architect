# robo-sync 구조 추출기

`robo-sync`와 Proposal 검증은 구현 파일을 언어별 추출기로 정규화한 뒤 Tactical
Diff와 비교한다. 추출기는 소스 파일을 수정하거나 실행하지 않는다.

| 언어/형식 | 명령 | 추출 정보 | 구현 방식 |
|---|---|---|---|
| TypeScript | `node ts_extract.mjs <file>` | class 필드 | 경량 소스 파서 |
| Python | `python python_extract.py <file>` | 미구현 | 스켈레톤 |
| Java | `python java_extract.py <file>` | 타입, 필드, 메서드·파라미터, 발행 이벤트명, enum | 의존성 없는 보수적 소스 파서 |
| Avro | `python avro_extract.py <file.avsc>` | record명, namespace, 필드 타입·필수 여부·기본값 | JSON 파서 |

추출기는 `skills/robo-spec/robo-sync/extractors/`에 있으며 Proposal 검증 프롬프트는
이 디렉터리의 절대 경로를 `EXTRACTOR_ROOT`로 전달한다. 따라서 이미 만들어진
샌드박스에도 추출기를 다시 복사하지 않고 최신 버전을 사용할 수 있다.

## Java 판정 규칙

- `domain/`의 최상위 타입은 기본적으로 `Aggregate`로 분류한다.
- `application/`의 서비스 타입은 `Command` 컨테이너로 분류한다. Tactical Command
  이름은 컨테이너 클래스명이 아니라 `methods[].name`과 비교한다.
- `publisher.publish(..., "EventName", ...)`의 첫 PascalCase 문자열을
  `emittedEvents[]`로 추출해 Tactical Event와 비교한다.
- record의 헤더 컴포넌트는 `fields[]`로 추출한다.
- 중첩 enum은 상태 이름과 값 목록을 추출한다.

## 제한 사항

Java 추출기는 컴파일러나 완전한 Java AST가 아니다. 외부 파서 의존성 없이 생성 코드의
일반적인 구조를 결정론적으로 비교하기 위한 보수적 파서다. 다음 형태는 직접 소스 검토나
향후 JavaParser 기반 추출기가 필요할 수 있다.

- annotation processor가 생성하는 필드·메서드
- 여러 최상위 타입이 들어 있는 한 파일
- 문자열 리터럴이 아닌 동적 이벤트 이름
- 상속·제네릭 해석이 필요한 의미 비교
- 메서드 내부의 데이터 흐름 및 런타임 동작

추출 실패는 PASS로 간주하지 않는다. 지원 언어의 파일을 찾았지만 파싱할 수 없으면
`SKIPPED`와 구체적인 실패 사유를 남긴다.

## 출력 예시

```json
{
  "kind": "Command",
  "name": "PaymentCommandService",
  "fields": [{"name": "repository", "type": "PaymentRepository"}],
  "methods": [{
    "name": "schedule",
    "returnType": "UUID",
    "parameters": [{"name": "orderId", "type": "UUID"}]
  }],
  "emittedEvents": ["PaymentScheduled", "PaymentOutcomeRecorded"],
  "enums": []
}
```
