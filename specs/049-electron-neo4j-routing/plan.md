# Implementation Plan: Electron 선택 Neo4j 연결 전파

## Flow

`Launcher active connection → preload bridge → same-origin fetch headers → app protocol proxy → Architect API middleware → request ContextVar → Neo4j session`

## Design

- renderer fetch interceptor 한 곳에서 identity와 Neo4j headers를 합성한다.
- protocol proxy는 headers를 그대로 전달하고 URI/database 존재만 진단한다.
- API middleware가 요청 시작에 override를 설정하고 종료 시 해제한다.
- driver cache key는 uri/user/password이며 database는 session 단위로 선택한다.
- Analyzer graph 소비자는 explicit `owner_id`와 `name`만 사용하고 id를 분해하지 않는다.
- service repository 구성은 Data Fabric을 canonical submodule로 선언한다.

## Verification

- Python compile/import와 ContextVar 격리 단위 확인.
- Architect frontend production build.
- Electron 실제 연결 두 개를 번갈아 선택해 DB 격리 확인.
