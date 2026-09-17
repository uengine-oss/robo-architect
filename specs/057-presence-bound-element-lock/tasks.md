# Tasks: 선점 잠금을 접속에 묶는다

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

## T0 — 먼저 실패를 본다

- [x] T001 US1 검사를 **고치기 전에** 돌려 60초 벽에서 실패하는 것을 본다
- [x] T002 지금 유령 잠금이 남는 갈래 둘(브라우저 강제 종료 · 백엔드 재시작)을 실측한다

## T1 — 서버: 수명을 접속에 묶는다

- [x] T003 `store.py` — `LOCK_TTL_SECONDS` 제거, `LOCK_ABSENT_GRACE_SECONDS` 도입
- [x] T004 `store.py` — `_LIVE_HOLDER_SQL` 한 곳. `locks()` · `acquire_lock()` · `can_write()` 가 공유
- [x] T005 `store.py` — `sweep_absent_locks()` (행을 지운다)
- [x] T006 `store.py` — `acquire_lock()` 이 같은 자리에서 presence 를 올린다 (FR-003)
- [x] T007 `router.py` — `/lock` heartbeat · 스트림 한 바퀴마다 sweep · 기동 시 1회 sweep
- [x] T008 pytest — 접속이 살아 있으면 안 만료 / 사라지면 만료 / 동시 취득은 하나만

## T2 — 화면: 끊긴 것을 말한다

- [x] T009 `collab.store.js` — `disconnectedSince`
- [x] T010 `useElementLock.js` — `atRisk`
- [x] T011 `LockBanner.vue` — 끊김 변종 (남이 잡았을 때와 **다른 문장**)

## T3 — 화면 검사 (창 둘 · 두 사람)

- [x] T012 US1 90초 보유 후 저장이 통과한다
- [x] T013 US2-1 창을 닫으면 즉시 · US2-2 강제 종료 → grace 안에 · US2-3 백엔드 재시작
- [x] T014 US3 끊김 배너 · 복귀 시 되집기 · 뺏겼으면 누구인지
- [x] T015 US4-1 챗이 LLM 전에 막힌다 · US4-2 패널 전환에도 유지
- [x] T016 US4 **칩 id == 잠금 id** — 앱이 만든 값끼리 맞댄다 (STATUS §4.27)
- [x] T017 US4-3 챗 왕복: 프롬프트 → 초안 → 승인 → 그래프 확인
- [x] T018 US5 두 경로의 변경이 상대 창에 나타난다

## T5 — 매뉴얼

- [x] T022 `manual/` — 사용자 매뉴얼. **캡처는 Playwright 가 두 사람을 띄워 찍는다**
      (`frontend/tests/collab-manual-capture.spec.ts` → `manual/images/`).
      손으로 그린 그림은 화면이 바뀌면 조용히 거짓말을 하고, 그 거짓말은 고객이 먼저 본다

## T4 — 검증의 검증

- [x] T019 검사마다 결함을 심어 무는 것을 확인 (상수·조건절만. 파괴적 결함 금지)
- [x] T020 무회귀: collab 세 파일 + 백엔드 + 단위 + 빌드
- [x] T021 문서 — `STATUS.md` · `enterprise-todo.md` · `enterprise-done-v2.md` 같은 회차에

## 무엇이 달라졌나 — 계획과 실제

```
계획      "60초 벽이 활성 편집자를 친다"
실제      **벽까지 갈 일이 없었다.** 스트림이 끊기는 그 순간 `finally` 가 놓았다.
          실측으로 끊고 10초 안에 사라진다 (T001)

계획      잠금을 사람(uid)에 묶는다
실제      **창(session)에 묶어야 했다.** 사람에만 묶으니 창을 둘 연 사람이
          편집하던 창을 닫아도 다른 창이 살아 있다는 이유로 잠금이 남았다

계획      서버 스트림 고리가 세션을 갱신한다
실제      **서버가 제 손으로 창을 살려 놨다.** 창이 완전히 끊긴 뒤에도 고리가
          "붙어 있다"를 찍어 선점이 안 풀렸다. 붙어 있다는 사실은 **창이 실제로
          보낸 요청**으로만 안다
```

## 안 한 것

```
살아 있는 보유자에게서 뺏는 강제 이어받기   비목표로 적었다 (spec)
필드 단위 잠금 · 편집 병합                  범위 밖
edit-actions.spec.ts 의 실패               **내 변경 전부터 실패한다** —
                                            같은 검사를 pristine 트리에서 돌려 확인했다
```
