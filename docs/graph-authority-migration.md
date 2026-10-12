# 그래프 권한 서버 이관 — 2026-10-12 조사

현재 설치 앱의 두 계정 프로젝트 격리는 검증됐지만, PC에 관리자 DB 자격이 있으므로
클라이언트 자체 변조까지 막는 AUTH-1 배포 구조는 아직 완성되지 않았다.

## 현재 특권 호출

| 경로 | 사용 특권/비밀 | 이관 대상 |
|---|---|---|
| projects/roles.py ensure_role | CREATE/ALTER ROLE, AUTH_ROLE_SECRET | 서버 사용자 역할 운영 |
| projects/store.py create_project/adopt_graph | og_create_graph, og_grant | 서버 프로젝트 운영 |
| projects/store.py share/unshare/set_analyzer_graph | og_grant/og_revoke | 서버 공유 및 분석 그래프 선택 |
| identity/connection_binding.py resolve_for_request | 쓰기 사용자를 NEO4J_USER/PASSWORD 관리자 자격으로 연결 | 서버가 프로젝트·사용자를 확인한 쓰기 실행 |
| projects/store.py 그래프 복사/권한 회수 | 관리자 Bolt, 권한 함수 | 서버 운영 경로 |
| desktop runtime 컨테이너 analyzer/catalog/fabric | 공유 그래프 사용자·비밀번호 | 서비스별 범위 제한 자격 또는 서버 실행 |

## 단순 프로젝트 API 프록시만으로 완료되지 않는 이유

중앙 계정 API는 CREATEROLE이 없는 제한 역할로 시작한다. 현재 프로젝트 저장소를 그대로
include_router하면 역할 생성에서 실패한다. 별도의 서버 전용 특권 운영 경계가 필요하다.
또한 프로젝트 API만 이전해도 PC의 ingestion은 새 라벨·뷰 생성에 관리자 자격을 사용한다.
PC에 공용 관리자 비밀번호와 AUTH_ROLE_SECRET을 남기면 다른 계정 역할을 유도하거나
권한 표를 바꾸는 경로가 남는다. 계정 표 ACL만으로 해결되지 않는다.

## 구현 순서와 인수 조건

1. 서버 전용 프로젝트 운영 경계에 최신 계정 승인과 프로젝트 admin 권한 검사를 둔다.
   운영 비밀은 PC에 제공하지 않고, 사용자별 DB 역할 생성 및 공유 변경을 서버에서만 한다.
2. 현재 Ontological 버전에서 범위 제한 역할의 라벨/뷰 생성·ingestion 쓰기를 격리 DB로 확인한다.
   부족한 특권은 범용 SQL·Cypher 관리자 프록시를 만들지 않고 서버 측 프로젝트 고정 실행으로 처리한다.
3. 비동기 ingestion·탐색·승격 및 analyzer/catalog/fabric의 실제 자격을 같은 경계로 전환한다.
   프로젝트는 클라이언트가 보낸 값만 믿지 않고 승인·현재 공유 권한을 확인해 고정한다.
4. 모든 PC/서비스의 실제 자격을 회수한 뒤 공용 관리자 DB 비밀번호와 역할 유도 비밀을 교체한다.
5. 계정 환경변수 변조, 직접 SQL, 역할 전환, 다른 프로젝트 graph 지정, 회수 후 기존 작업/토큰,
   일반 사용자 ingestion 정상 동작을 확인하고 설치본으로 검증한다.

현재 VM과 설치 앱은 사용자 시험용으로 그대로 유지한다. 이 조사는 서버 이관 구현 완료가 아니다.
실제 SWP·사내 HTTPS 인증서/네트워크는 현장에서 확인하며, 격리 구현 검증은 여기서 진행 가능하다.

## 후속 구현 — 프로젝트 운영 경계

PC `/api/projects` 경로의 중앙 전달과 중앙 서버 라우터를 구현했다.
계정 승인 확인은 제한 DB 자격, 프로젝트 운영은 서버 전용
`ROBO_PROJECT_OPERATOR_DSN`을 요청별 ContextVar 범위로 사용한다.
동시 요청 간 범위 분리와 예외 후 복원, 승인 거절 시 특권 미사용, 설정 부재 시 503,
실제 격리 DB의 프로젝트 생성·목록 분리·타인 멤버 조회 거절을 검증했다.
기존 graph adopt는 중앙 관리자 전용이며 runtime DDL은 제거했다.
통합 격리 검사 135개 통과. VM 배포·설치본 반영 전이며 위 순서 2~5는 남아 있다.
