# Integration Test — robo-architect

여러 브랜치(speckit/SDD)로 들어온 기능들을 **탭 단위**로 하나씩 통합 검증하고 안정화하기 위한 문서 모음.

- 검증 단위: App.vue의 **탭**(사용자에게 보이는 View mode)
- 각 탭 문서: `tabs/<tab>.md` — 그 탭이 보유한 기능, 관련 스펙, 검증 시나리오, 결과
- 템플릿: [`_TEMPLATE.md`](_TEMPLATE.md)
- **후속·미구현 정리**: [`FOLLOW-UPS.md`](FOLLOW-UPS.md) — 탭 범위를 넘거나 신규 feature·미구현이라 **이후 탭/세션에서 이어받을** 항목(대상 탭별 그룹핑)

## 탭 구조 (App.vue / TopBar.vue 기준)

사용자 노출 탭 순서: **Proposals · Analysis · Stories · Process · Design · Data · Code**
(`Process` 탭은 내부적으로 BPM(`Process`) ⇄ Event Modeling(`Processes`) 서브토글로 분기. `Changes`는 컴포넌트는 유지하되 상단바에서 숨김.)

| 탭 (노출) | activeTab 값 | 패널 컴포넌트 | 핵심 관련 스펙 |
|---|---|---|---|
| **Stories** | `Stories` | `RequirementsPanel` | 001, 008, 019, 026, 030, 031, 033, 034 |
| **Process** (BPM) | `Process` | `BpmnPanel` | 011, 022, 036, 042, 043 |
| **Process** (Event Modeling) | `Processes` | `EventModelingPanel` | 006, 010, 012, 025, 042, 043 |
| **Design** | `Design` | `CanvasWorkspace` | 002, 003, 004, 005, 027, 035 |
| **Data** | `Data` | `AggregatePanel` | 027, 028 |
| **Code** | `Code` | `ClaudeCodeWorkspace` | 015, 021, 029 |
| **Proposals** | `Proposals` | `ProposalsPanel` | 039, 040, 041 |
| **Analysis** | `Analysis` | `AnalysisPanel` | robo-analyzer (Module Federation) |
| **Changes** (숨김) | `Changes` | `ChangesRootPanel` | 038 |

> 매핑은 스펙 폴더명·CLAUDE.md 히스토리 기준 초안. 탭별 검증을 진행하며 실제 코드로 확정.

### 탭에 직접 매이지 않는 횡단(cross-cutting) 스펙

| 스펙 | 영역 | 비고 |
|---|---|---|
| 007 | PRD 생성/익스포트 | Stories/문서 |
| 009, 016, 020, 024 | Figma 동기화/바인딩/와이어프레임 | Design/외부연동 |
| 013 | Confluence 인제스천 | 입력 |
| 014 | 문서 익스포트 템플릿 | 횡단 |
| 017, 018 | 인제스천 토큰/서스펜드/배치 영속 | 입력 파이프라인 |
| 023 | Electron 데스크탑 / HTML policy | 셸 |
| 032 | 데스크탑 시작 피커 | 셸 |

## 진행 현황

상태: ⬜ 미시작 · 🟡 진행중 · ✅ 통과 · ❌ 이슈있음

| 탭 | 문서 | 상태 | 비고 |
|---|---|---|---|
| Stories | [tabs/stories.md](tabs/stories.md) | ✅ 완료 | S1~S15 전 시나리오 라이브 검증. 버그 **36건 수정**(I1~I36: 명확화 I8~I16·DDD마법사 I21~I31·삭제 I33·설계반영 I34/35·궤적 I36 등), 후속 3건(I7·I22·I32) |
| Process (BPM) | [tabs/process-bpm.md](tabs/process-bpm.md) | 🟢 거의완료 | **S1·S2·S3·S5·S6·S7 ✅** 라이브(인제스천→렌더→PDF콘텐츠 19/19 정합·Inspector·Rule탐색SSE·move/unassign·전체탐색+arbitration·ES승격 BC3/Cmd21/Evt37/RM11/UI26/US19). **수정 9건**(B1·C1·C2·D1·B3·B4·B5·B6·E3), E1철회·E2정상. **B2/B2+ 미해결(보류 — 정밀도는 정확, 리콜갭은 미매핑풀서 수동보완 가능·손실없음)**. 남은 S4·S8=EM 교차 |
| Process (Event Modeling) | [tabs/process-event-modeling.md](tabs/process-event-modeling.md) | ✅ 완료 | **S1~S9 ✅** + **수동 편집(자유좌표/연결) 심화**. **수정 18건**(EM1~EM9 + EM10 자유좌표저장·EM11 RM3분류 시각구분·EM12 UI연결 Ui≠UI/방향역전·EM13 Design부착 attachedToId·EM14 드롭열 off-by-one(round→floor)·EM15 연결 카디널리티 거부+알림·EM16 **재승격 idempotency**(clear후생성). loose X드래그·배너자동숨김·독립노드토스트 포함). 자유좌표=관계파생 레이아웃에 stored sequence 도입, 연결은 Connect모드 수동. |
| Design | [tabs/design.md](tabs/design.md) | ⬜ | |
| Data | [tabs/data.md](tabs/data.md) | ⬜ | |
| Code | [tabs/code.md](tabs/code.md) | 🟡 진행중 | 인벤토리 작성(015 터미널·021 3-pane IDE·029 MCP/슬래시). S0~S6 설계. C11(pty_backend env)·C6/C7·I14/I16 이월 확인 대상 |
| Proposals | [tabs/proposals.md](tabs/proposals.md) | ✅ 완료 | 생애주기 **S1~S10 전 시나리오 ✅**. 버그 **14건 수정**(I3·I5·I6·I7·I8·I9·I10·I11·I13·I17·I18A·I19+S9안내), 후속/백로그 6건(I4·I12·I14·I16·I18C·I20). 041 미구현 |
| Analysis | [tabs/analysis.md](tabs/analysis.md) | ⬜ | |
| Changes | [tabs/changes.md](tabs/changes.md) | 🟡 초안 | 인벤토리 완료(038 RequirementChange/CHG-NNN·EFFECT·ChangeSet·상태전이·구현PTY·회귀). **숨김 탭이라 접근경로(S0) 먼저 확정 필요**. 038→039(Proposal) 진화로 deprecated 경로 가능성 — 실제 동작 여부부터 확인 |

## 검증 방식

1. 탭 문서를 열어 **그 탭이 보유한 기능 목록**과 **의도/목표**를 스펙에서 확정.
2. 기능별 검증 시나리오(전제 → 조작 → 기대결과)를 작성.
3. 실제 앱/API로 확인하고 결과(✅/❌)·이슈·후속을 기록.
4. README 진행 현황 표를 갱신.
