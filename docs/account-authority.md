# 중앙 계정·관리자 권한 운영 (AUTH-1)

구현: 관리자/승인 정책 DB 저장, 최초 등록 명령, 중앙 계정·템플릿 API, PC 프록시.
검증: 임시 PostgreSQL에서 경쟁·감사 롤백·직접 SQL 거절·중앙 HTTP 경로 검사.
미검증: VM 배포, 실제 SWP, 두 PC, 제한된 그래프 runtime의 프로젝트 생성/공유 회귀.
기존 설치본·운영 DB는 변경하지 않았다. VM 준비 후 아래 이관 절차를 수행한다.

## 서버에서만 지정한다

`public.app_users.value.role`이 관리자 역할의 권위다. 로그인은 이름·부서 등 신원만
갱신한다. `ADMIN_EMPLOYEE_NOS`, `AUTH_APPROVAL_REQUIRED`는 더 이상 읽지 않는다.
승인 정책은 `app_auth_policy`, 변경 이력은 `app_account_audit`에 저장한다.
새 DB는 미초기화 상태여서 로그인할 수 없다. 첫 사용자가 관리자가 되지 않는다.

서버 운영용 DB 자격으로 실행한다. DSN은 서버의 환경/비밀 관리 경로로 공급하며
비밀번호를 명령 인자나 작업 기록에 넣지 않는다.

```powershell
python -m scripts.accounts_admin migrate
python -m scripts.accounts_admin grant --employee-no <실제사번> --reason "최초 관리자 지정"
python -m scripts.accounts_admin policy --approval-required true --reason "납품 승인 정책"
```

최초 grant는 기존 DB의 다른 admin을 member로 내리며 각각 감사 기록을 남긴다.
환경변수에서 승격된 계정을 자동으로 납품 관리자에 이관하지 않기 위한 동작이다.
반드시 백업하고 기존 역할 목록과 실제 담당자를 확인한 뒤 실행한다.
다른 관리자는 최초 관리자의 실제 SSO 로그인을 확인한 뒤 UI/API에서 지정한다.
grant 재실행은 이미 승인된 관리자라면 값을 다시 쓰지 않는다.

기존 API `POST /api/accounts/{uid}/role`, `POST /api/accounts/{uid}/status`를 사용한다.
body에 role 또는 status, 선택적으로 reason을 넣는다. 중앙 API가 변경자의 현재
역할·승인을 잠금 획득 후 다시 확인하며, 감사 기록과 같은 트랜잭션으로 저장한다.
자기 계정 변경은 거절한다. 마지막 승인된 관리자 제거는 운영 명령에서도 거절한다.

복구/담당자 교체:

```powershell
python -m scripts.accounts_admin grant --employee-no <새사번> --reason "관리자 복구"
python -m scripts.accounts_admin revoke --employee-no <옛사번> --reason "담당자 변경"
```

## DB 자격 분리

서버 운영자는 superuser를 사용하지만 API runtime과 PC 자격은 별도 제한된 역할로
미리 만든다. 그 비밀번호를 설정하는 작업은 서버 운영 경로에서 수행한다.
운영 자격으로 다음 명령을 실행한다.

```powershell
python -m scripts.accounts_admin configure-access --server-role <중앙API역할> --client-role <PC역할>
```

이 명령은 보호 표/시퀀스와 public 스키마의 PUBLIC·지정 역할 권한을 정리한다.
중앙 API에는 계정 변경·정책 행 잠금·감사 추가·템플릿 변경을 허용하고,
PC는 사용자/정책 조회만 허용한다. 감사 UPDATE/DELETE와 계정 DELETE API는 제공하지 않는다.
superuser/CREATEROLE/CREATEDB/BYPASSRLS, 상위 역할 멤버십, 보호 표 소유자가 있으면 거절한다.
두 역할만 대상으로 하는 명령이므로 **모든 PC/컨테이너의 실제 DB 자격**을 목록화하고
추가 역할의 직접/상속 권한과 보호 표 소유권을 별도로 확인해야 한다.

PC가 실행 가능한 SECURITY DEFINER 함수는 기본 거절한다. 예외는 검토한
Ontological 확장의 `public.og_build_view(int4,bool)` C 함수 하나다. 확장 소속,
라이브러리·심볼·인자까지 대조한다. 이 함수는 og_data의 security_invoker 뷰를
만든다. 다른 확장 버전/함수가 추가되면 다시 검토한다.

주의: 기존 PC의 프로젝트 생성/공유는 역할 생성·og_grant 등 별도 특권을 사용한다.
PC를 새 제한 역할로 바꾸면 이 흐름도 서버에서 처리하도록 정리해야 한다.
현재 configure-access는 **계정/템플릿 보호 범위**이며 그래프 서비스 자격의 전체 이관을
완료했다고 간주하지 않는다. 기존 robo superuser를 PC에 남긴 채 납품해서는 안 된다.
그 자격이 알려진 상태면 서버 전용으로 회수/교체하고 PC에 다시 배포하지 않는다.

## 중앙 API와 PC 연결

서버 API runtime에만 OG_PG_DSN, AUTH_JWT_SECRET, AUTH_PROVIDER=swp와 SWP 설정을 준다.
템플릿 출고 원본도 같은 릴리스의 templates 디렉터리를 제공한다.
서버에는 ROBO_AUTHORITY_URL을 설정하지 않는다.

```text
uvicorn api.authority:app --host 0.0.0.0 --port 59020
```

서버 전용 엔트리포인트는 인증 스위치가 꺼져 있어도 인증·DB 승인을 강제한다.
개발 로그인은 AUTH_DEV_LOGIN_ENABLED/internal-test 여부와 무관하게 항상 거절한다.
운영 topology는 별도 AP 서버를 두지 않는다. DB central과 이 gateway를 기존 DB 서버에서
함께 실행하고 59020을 사내망 인터페이스에 게시한다. 사용자 PC와 DB 서버가 같은 사내망에
있으므로 `http://<DB_SERVER_PRIVATE_IP>:59020`으로 직접 통신한다. 인터넷 노출은 방화벽과
접근 제어로 차단한다. 현재 릴리스의 `central-server/compose.yml`은 graph DB, Bolt와
이 API를 함께 기동·감독하며 Authority image도 같은 `robo-images.tar`에 포함한다.
서버에서는 `central-authority.env.example`을 `central-authority.env`로 복사한 뒤 제한
runtime DSN, 별도 project operator DSN, SWP 설정과 비밀을 채운다. 완성된 파일은 PC
설치본, Git, 배포 기록에 넣지 않는다.

초기화·복구 명령도 Authority image 안에 들어 있다. DB 운영자 DSN을 서버의 비밀 관리
경로에서 `OG_PG_DSN`으로 주입한 일회성 컨테이너에서 실행한다. Authority 상시 서비스에는
이 superuser DSN을 절대 설정하지 않는다.

```powershell
docker compose run --rm --no-deps authority python -m scripts.accounts_admin migrate
docker compose run --rm --no-deps authority python -m scripts.accounts_admin grant --employee-no <실제사번> --reason "최초 관리자 지정"
docker compose run --rm --no-deps authority python -m scripts.accounts_admin policy --approval-required true --reason "납품 승인 정책"
```

PC OS 환경에는 `ROBO_AUTHORITY_URL=http://<DB_SERVER_PRIVATE_IP>:59020`을 설정하고 앱을
다시 시작한다. HTTP는 loopback과 RFC1918/사설 IPv6 주소만 허용한다. 공인 IP·일반 hostname의
HTTP는 잘못된 외부 노출을 막기 위해 거절한다. 사내 DNS 이름을 사용해야 하는 환경은 HTTPS를
쓰거나 별도의 명시적 허용 정책을 추가한다.
PC는 /api/auth/*, /api/accounts/*, /api/projects/*, /api/code-templates/sets 경로를 중앙에 전달한다.
템플릿 모델 /context는 PC에서 처리한다. 사용자/역할/Neo4j/Forwarded 헤더는 중앙에 전달하지 않는다.
PC 토큰 검증은 중앙 /api/auth/introspect에서 최신 DB 상태를 확인한다.
중앙 연결 실패 시 로컬 서명/DB 쓰기로 대체하지 않는다. 중앙 서명 비밀은 PC에 넣지 않는다.
현재 이 동기 검증은 매 요청 중앙 HTTP를 호출하므로 VM에서 지연·동시 요청을 측정한다.

프로젝트 운영을 활성화하려면 서버에만 `ROBO_PROJECT_OPERATOR_DSN`과 32자 이상의
`AUTH_ROLE_SECRET`을 설정한다. 전자는 계정 runtime과 같은 DB의 별도 운영 역할이며
역할 생성·graph 생성·grant/revoke에 필요한 서버 전용 자격이다. PC에는 제공하지 않는다.
운영 migrate가 프로젝트 표까지 만든다. runtime 요청에서는 DDL을 실행하지 않는다.
중앙 승인 확인은 제한 역할로 먼저 하고, 통과한 프로젝트 경로만 요청별 ContextVar로
운영 DSN을 사용한다. 다른 동시 요청이나 계정 API로 특권 자격이 전파되지 않는다.
운영 DSN이 없으면 프로젝트 경로는 503이며 PC 로컬 실행으로 대체하지 않는다.
기존 graph adopt는 중앙 관리자만 허용한다. 기존 프로젝트의 공유 변경은 프로젝트 admin만 허용한다.
이 단계는 프로젝트 운영 경계 구현이다. PC ingestion/서비스의 관리자 Bolt 자격 제거는 아직 남아 있다.

기본 설치 구조에서는 `ROBO_INGESTION_URL`을 설정하지 않는다. 분석·파싱·Fabric과 함께
ingestion·탐색·승격도 사용자 PC에서 실행한다. Workspace 릴리스에는 authority origin만
포함한다. 중앙 ingestion 프록시는 별도 중앙 실행 서버가 있는 다른 배포 형태를 위한 선택
기능이며, 현재 사내 설치본에는 사용하지 않는다.

Figma 연결 코드 발급도 중앙으로 이동한다. 해당 경로의 프로젝트 권한 조회는 그래프
서비스 연동이 필요하므로 VM에서 별도로 회귀 검증해야 한다. 플러그인 토큰의 scope를 유지한다.

## 재현 가능한 검사

저장소 루트에서 실행한다.

```powershell
& .\scripts\test_account_authority.ps1
```

기존 Ontological 이미지로 `robo-auth-test-20261012` 임시 컨테이너를 만들고,
loopback 임의 포트와 tmpfs 데이터로만 검사한 뒤 finally에서 해당 컨테이너를 지운다.
기존 DB·볼륨은 사용하지 않는다. 기존 동명 컨테이너가 있으면 덮거나 지우지 않고 멈춘다.
검사 범위: 환경변수 우회, 초기화, 마지막 관리자·경쟁, 로그인 경쟁, 감사 롤백,
직접 SQL/DDL/역할 전환 거절, 중앙 인증 및 프록시, 기존 SWP·Figma·템플릿 회귀.

VM 준비 후 실제 SSO·서버 복구·두 PC의 권한 반영·프로젝트 생성/공유·템플릿 변경을
확인하고 최신 설치본으로 재검증한다. 그 전에는 AUTH-1 전체 완료로 기록하지 않는다.
