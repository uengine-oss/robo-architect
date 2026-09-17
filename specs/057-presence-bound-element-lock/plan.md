# Implementation Plan: 선점 잠금을 접속에 묶는다

**Spec**: [spec.md](spec.md) · **Date**: 2026-09-17 · **Branch**: `enterprise-custom-p`

## Summary

`LOCK_TTL_SECONDS = 60` 을 지우고, 잠금의 생사를 **보유자의 `app_presence` 행**으로
판정한다. 갱신 주기가 아니라 **붙어 있음**이 기준이 된다. 정리는 숨기는 것이 아니라
행을 지우는 것으로 하고, 스트림 한 바퀴와 **기동 시**에 돈다.

화면은 **끊긴 것을 말한다** — 지금은 끊겨도 아무 말이 없어서 사람이 잃을 글자를 계속 친다.

## Technical Context

```
Language     Python 3.11 (FastAPI) · Vue 3 + Pinia
Storage      Postgres (Ontological 컨테이너 안) — public.app_element_locks · public.app_presence
             **설계 graph 가 아니다.** 분석기가 graph 를 통째로 비우는 자리라 여기 두면 안 된다
Testing      Playwright (창 둘 · 두 사람) · pytest (api/features/collab/tests)
Constraint   납품 브랜치에서 이어 간다. Desktop/robo 문서는 커밋하지 않는다
```

## 무엇이 어디서 바뀌나

### 서버 — `api/features/collab/store.py`

```
LOCK_TTL_SECONDS = 60                 지운다
LOCK_ABSENT_GRACE_SECONDS = 25        PRESENCE_TTL(15) + 10. FR-002 로 검사가 지킨다
_LIVE_HOLDER_SQL                      "보유자가 붙어 있나"를 **한 곳에서만** 적는다.
                                      locks() · acquire_lock() · can_write() 가 같은 조각을 쓴다
sweep_absent_locks(graph=None)        보유자 없는 행을 **지운다**. graph 없으면 전부
acquire_lock()                        만료 조건을 presence 로 바꾼다 + 같은 문장에서 presence 를 올린다
```

**한 문장으로 유지한다.** "지우고 → 넣는다"로 나누면 그 사이에 둘이 들어온다
(done-v2 §56 의 실측: 안 잠긴 것을 16명이 집으면 아홉이 다 잡았다고 믿는다).

### 서버 — `api/features/collab/router.py`

```
/lock                 heartbeat 를 같이 친다 (FR-003)
/stream 한 바퀴       sweep_absent_locks(graph)
기동                  ensure_schema() 뒤 sweep_absent_locks() 1회 (FR-004)
```

### 화면 — `frontend/src/features/collab/`

```
collab.store.js       disconnectedSince — 끊긴 시각. connected 는 이미 있는데
                      **얼마나 끊겼는지**가 없어서 화면이 판단을 못 한다
useElementLock.js     atRisk = held && !connected && 끊긴 지 GRACE 의 절반 이상
LockBanner.vue        변종 하나 추가: "연결이 끊겼습니다 — 다른 사람이 가져갈 수 있습니다"
                      (남이 잡았을 때의 배너와 **다른 문장이어야 한다** — 원인이 다르다)
```

**입력칸은 안 잠근다.** 끊긴 것은 아직 뺏긴 것이 아니다. 잠그면 잠깐 끊겼다 붙는
흔한 경우에 편집을 방해한다. 정말 뺏겼을 때(`other`)만 잠근다 — 그 경로는 이미 있다.

## 어떻게 잴 것인가 — 부품이 아니라 화면

| 무엇 | 어떻게 | 왜 이 방법인가 |
|---|---|---|
| US1 붙어 있으면 안 풀린다 | Inspector 를 열어 두고 **90초** 기다린 뒤 저장 | 60초 벽이 있으면 여기서 409 가 난다 |
| US2 정상 종료 | `page.close()` 뒤 다른 창에서 즉시 집기 | 스트림 `finally` 경로 |
| US2 강제 종료 | `context.close()` 없이 **브라우저 프로세스 kill** | `finally` 가 안 도는 갈래 |
| US2 백엔드 재시작 | 잠금을 남긴 채 백엔드만 재시작 → 기동 sweep | 붙은 창이 없어 한 바퀴도 안 돈다 |
| US3 끊김 표시 | 라우트 가로채기로 `/api/collab/stream` 을 끊는다 | 절전·프록시를 코드 안 고치고 흉내 |
| US4 챗 차단 | bob 이 잡은 요소를 alice 가 **챗에서 고른다** | LLM 전에 막히는지 |
| US4 칩 id == 잠금 id | **앱이 만든 두 값을 읽어 맞댄다.** 심지 않는다 | STATUS §4.27 이 못 잰 자리 |
| US4 챗 왕복 | 프롬프트 → 초안 → 승인 클릭 | 인수조건 중 마지막 미충족분 |
| US5 상호 반영 | 두 창에서 각각 확인 | |

**시간이 걸리는 것을 줄이지 않는다.** US1 의 90초를 30초로 줄이면 60초 벽이 있어도
통과한다 — 그러면 이 스펙이 재려던 것을 안 재는 검사가 된다.

## Constitution Check

```
화면 경로로 잰다                    ✓ 전부 Playwright 두 창
막는 것과 여는 것을 같이 잰다        ✓ US1(잡은 사람은 된다) ↔ US4-1(남은 막힌다)
0건의 이유를 가른다                  ✓ FR-011
실 데이터 되돌리기                   ✓ edit-actions.spec.ts 의 되돌리기 패턴을 따른다
파괴적 결함 금지                     ✓ 결함은 상수·조건절만 건드린다
```

## 위험

```
LLM 왕복이 느리거나 키가 없다   → US4-3 이 못 돌 수 있다. 그러면 **"안 쟀다"** 라고
                                 적는다. 건너뛰고 통과시키지 않는다
브라우저 kill 이 CI 에서 다르다  → 로컬 실측만 주장한다
presence 가 REST 전용 클라이언트  → FR-003 으로 /lock 이 presence 를 올린다.
에게는 안 올라간다                  안 하면 API 로만 잡은 잠금이 25초 만에 죽는다
```
