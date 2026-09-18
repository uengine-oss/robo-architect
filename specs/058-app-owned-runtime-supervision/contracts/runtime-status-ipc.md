# 계약 — 런타임 상태 IPC

**Feature**: 058 | **Date**: 2026-09-17

렌더러가 런타임을 보는 유일한 창구. 지금은 `app:getRuntimeState` 와
`app:onBackendStatus` 둘뿐이고, **`frontend/src` 에서 후자의 구독이 0건**이다.

## 하위 호환 원칙

기존 채널과 필드를 **지우지 않는다.** `ClaudeCodeTerminal.vue` 와
`workspace.api.js` 가 `getRuntimeState().backendPort` 를 쓰고 있다.

```
app:getRuntimeState      유지 — 반환 객체에 필드가 늘어난다
app:onBackendStatus      유지 — 계속 보낸다 (파생 status)
runtime:*                신규
```

## 채널

### `app:getRuntimeState` (수정)

반환값에 `services` · `capabilities` · `releaseId` · `dockerAvailable` ·
`graphGuard` 가 더해진다. 기존 필드는 그대로. `status` 는 `services` 에서 파생.

### `runtime:onStatus` (신규 · push)

상태가 **바뀔 때만** 보낸다. 주기 전송이 아니다 — 5초마다 같은 값을 밀면 렌더러가
쓸데없이 다시 그린다.

```
payload: { services, capabilities, graphGuard, changedServiceIds }
```

`changedServiceIds` 가 있는 이유: 화면이 **무엇이 바뀌었는지** 알아야 알림을 한 번만
띄운다. 없으면 전체 비교를 렌더러가 다시 한다.

### `runtime:retryService` (신규 · invoke)

```
in:  { serviceId }
out: { ok: true } | IpcHandlerError
```

되살리기를 **사용자가 직접** 요청한다. 자동 재기동이 한계에 도달해 `stopped` 가 된
뒤에도 이 길은 열려 있다(FR-018).

### `runtime:stopEngine` (신규 · invoke)

```
in:  { confirm: true }
out: { ok: true, stoppedServiceIds }
```

앱이 소유한 컨테이너만 내린다. **사용자 데이터는 보존한다** — `docker compose stop`
이고 named volume 을 지우지 않는다(FR-015 · `054` 계약).

`confirm` 을 요구하는 이유: 실수로 부르면 남의 화면에서 서비스가 사라진다.

### `runtime:openDiagnostics` (신규 · invoke)

로그 위치를 연다. 기존 `logs:reveal` 을 감싸고 **어느 서비스의 로그인지**를 받는다.

## 상태 푸시의 시점

```
기동 중        단계가 바뀔 때마다 (starting-db → starting-backend → …)
평상시         프로브 결과가 **바뀔 때만**
사건           컨테이너 exit · 백엔드 crash → 즉시
포트 재확보    바뀐 endpoint 를 실어서 (FR-016)
```

## 화면이 지켜야 할 것

### 기동 중과 고장을 가른다

```
starting   진행 중. 단계 이름과 함께 보인다. **무한 대기 금지**
failed     한계 시간 안에 실패로 결론난다 (FR-019)
```

기동에 수 분이 걸리는 것은 정상이다(2GB tar 적재). **오래 걸리는 것과 멎은 것을
화면에서 구분**해야 한다 — 마지막 진전 시각을 보여주는 것으로 충분하다.

### 준비 안 된 기능을 열지 않는다

`capabilities[].state !== 'available'` 이면 그 진입점은 **누르면 이유를 말하거나
비활성**이다(FR-006). 조용히 빈 화면을 주지 않는다.

### 빈 결과를 세 가지로 가른다

```
정상적인 데이터 부재   "아직 없습니다"
처리 실패              "만들다가 실패했습니다 — 무엇이"
조회 실패              "읽어오지 못했습니다 — 무엇이"
```

FR-021. **이 셋을 뭉치면 이 프로젝트에서 제일 흔한 고장 모양이 된다.**

## 비밀정보

`stateReason` · `detail` · 로그 · 진단 출력 어디에도 키·비밀번호·토큰을 넣지 않는다.
**길이나 지문으로도 남기지 않는다**(FR-011).

## 검사 방법 (SC-008)

```
서비스를 하나씩 죽인다      → 그 서비스만 failed, 나머지 available 유지
자격증명을 깨뜨린다         → degraded, health 는 pass 유지
컨테이너 환경을 내린다      → dockerAvailable false + 준비 안내
포트를 남이 쥔다            → 재확보 + 바뀐 endpoint 푸시
stopEngine 을 부른다        → 컨테이너 멈춤 + **볼륨 보존 확인** (데이터 되읽기)
```

마지막 줄은 **개수가 아니라 내용으로** 확인한다 — 내리기 전에 심은 값을 다시 읽어
같은지 본다.
