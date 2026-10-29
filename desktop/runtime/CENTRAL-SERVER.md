# Robo Architect 중앙 DB·권한 서버

이 디렉터리는 사용자 PC용 설치본과 같은 릴리스에서 생성된 서버 묶음이다.
`runtime-manifest.json`의 image tag/ID와 `SHA256SUMS`를 먼저 대조한다.

## 0. 먼저 — `robo-central.sh` 한 파일로 끝낸다

아래 1~3절을 손으로 하지 않는다. 같은 디렉터리의 `robo-central.sh`를 열어
맨 위 `[고치는 곳]`의 값 둘(`SERVER_IP`, `ADMIN_EMPNO`)만 채우고 돌린다.

```bash
vi robo-central.sh
sudo bash robo-central.sh
```

이 한 번이 이미지 적재, 비밀 다섯 생성, `.env`·`central-authority.env` 작성(600),
DB 기동, 역할 둘, `migrate`→`grant`→`policy`, 확인, 그리고 사용자 PC에 줄
`pc-central-setup.ps1`까지 순서대로 처리한다. **다시 돌려도 안전하다** — 이미
만든 비밀은 그대로 두고 이어간다.

```bash
sudo bash robo-central.sh check     # 상태와 값 길이만 본다(변경 없음)
sudo bash robo-central.sh rebind    # 서버 IP·포트가 바뀌었을 때
sudo bash robo-central.sh migrate   # 새 릴리스로 올린 뒤 표 구조만 맞출 때
sudo bash robo-central.sh down      # 컨테이너만 내린다(볼륨은 남긴다)
```

자세한 설명과 현장에서 물렸던 자리는 `docs/가이드/관리자-DB올리기.md`에 있다.

아래 1~3절은 **스크립트를 쓸 수 없을 때의 손 작업 기록**이다. 스크립트가 하는
일과 순서가 같다.

## 1. 이미지와 설정 준비

```bash
docker load --input ../robo-images.tar
cp central-authority.env.example central-authority.env
```

`central-authority.env`에는 제한된 Authority runtime DSN, 별도 project operator DSN,
SWP 설정과 32자 이상의 서로 다른 JWT/role 비밀을 입력한다. 완성된 파일의 권한은
운영 계정만 읽을 수 있게 하고 Git·메일·메신저로 전달하지 않는다.

compose 치환값은 같은 디렉터리의 `.env`에 둔다. 이미지 이름은 매니페스트와 같아야 한다.

```dotenv
ROBO_IMAGE_GRAPH_DB=uengine/ontological-db:<release-id>
ROBO_IMAGE_GRAPH_BOLT=uengine/ontological-bolt:<release-id>
ROBO_IMAGE_AUTHORITY=uengine/robo-authority:<release-id>
ROBO_GRAPH_USER=<db-owner-role>
ROBO_GRAPH_PASSWORD=<db-owner-password>
ROBO_GRAPH_DESIGN=robo
ROBO_GRAPH_ANALYSIS=analyzer_run
ROBO_GRAPH_BIND=<db-server-private-ip>
ROBO_AUTHORITY_BIND=<db-server-private-ip>
```

## 2. 최초 초기화

먼저 DB만 기동한다.

```bash
docker compose up -d --wait graph-db graph-bolt
```

DB 운영자는 서로 다른 제한 LOGIN 역할 두 개를 미리 만들고 비밀번호를 안전하게 설정한다.
그 다음 Authority image의 운영 CLI에 운영자 DSN을 일회성으로 주입해 스키마와 권한을 만든다.

```bash
docker compose run --rm --no-deps -e OG_PG_DSN authority \
  python -m scripts.accounts_admin migrate
docker compose run --rm --no-deps -e OG_PG_DSN authority \
  python -m scripts.accounts_admin configure-access \
  --server-role <authority-runtime-role> --client-role <pc-db-role>
docker compose run --rm --no-deps -e OG_PG_DSN authority \
  python -m scripts.accounts_admin grant --employee-no <actual-employee-no> \
  --reason "initial administrator"
docker compose run --rm --no-deps -e OG_PG_DSN authority \
  python -m scripts.accounts_admin policy --approval-required true \
  --reason "delivery approval policy"
```

위 명령의 `OG_PG_DSN`은 서버 셸의 비밀 관리 경로에서 전달한다. 명령행에 DSN 값을
직접 적지 않는다. 상시 `authority` 서비스에는 이 운영자/superuser DSN을 절대 넣지 않는다.

## 3. 상시 서비스 기동과 확인

```bash
docker compose up -d --wait
curl http://<db-server-private-ip>:59020/healthz
docker compose ps
```

사용자 PC에는 `ROBO_GRAPH_HOST=<db-server-private-ip>`와
`ROBO_AUTHORITY_URL=http://<db-server-private-ip>:59020`을 설정한다. 공개 인터넷으로
포트를 열지 않고 사내 사용자 PC 대역만 방화벽에서 허용한다.

## 운영 중 확인할 항목

- 마지막 승인 관리자는 제거되지 않아야 한다.
- 승인·역할 변경은 설정의 사용자 관리에서 수행하고 감사 이력을 확인한다.
- `central-authority.env`, DB volume과 감사 테이블을 정기 백업한다.
- 업그레이드 때 installer가 아니라 같은 release ID의 server 묶음과 image archive를 쓴다.
