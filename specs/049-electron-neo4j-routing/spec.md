# Feature Specification: Electron 선택 Neo4j 연결 전파

**Created**: 2026-07-14
**Status**: Implementing

## Problem

Electron 런처가 선택한 Neo4j 연결은 화면 진입까지만 사용되고, Architect API와 Analyzer remote의
후속 요청은 각 서비스 `.env` 연결을 사용했다. 따라서 사용자가 선택한 DB와 실제 조회·저장 DB가
달라질 수 있었다. DB만 다른 연결의 자동 label도 같아 중복 연결로 오인될 수 있었다.

## Requirements

- Electron renderer의 동일 출처 backend 요청은 활성 연결을 `X-Neo4j-*` 헤더로 전달한다.
- 비밀번호는 외부 출처 요청이나 로그에 노출하지 않는다.
- Architect API는 요청별 ContextVar에서 override를 읽고, 헤더가 없으면 `.env`로 폴백한다.
- 연결별 Neo4j driver를 재사용하되 요청 간 연결 정보가 섞이지 않는다.
- DB가 다른 연결의 기본 label에는 database를 포함한다.
- Analyzer/Catalog/Frontend/Fabric은 canonical sibling repository를 사용하며 Text2SQL submodule은 Fabric으로 교체한다.
- function의 module은 id 문자열 분해가 아니라 Analyzer의 `owner_id` 속성으로 소비한다.

## Acceptance

1. Electron에서 선택한 database로 Architect API 요청이 실행된다.
2. 웹 모드와 테스트는 헤더 없이 기존 환경설정 연결을 사용한다.
3. URI/user가 같고 database만 다른 두 연결을 별도로 저장할 수 있다.
4. 함수-모듈 연결은 opaque id 형식이 바뀌어도 유지된다.
5. password가 Electron protocol diagnostic log에 남지 않는다.
