# docs/

이 폴더에는 설계·조사 문서가 있다. **Electron 납품 관련 문서는 여기 없다.**

## Electron 납품 문서가 있는 곳

```
C:\Users\YSW\Desktop\electron-test\
```

| 파일 | 무엇 |
|---|---|
| `work-summary-*.md` | 평문 요약. 전체 그림을 먼저 잡을 때 |
| `enterprise-todo.md` | 남은 작업과 상태. §0 계열에 최신 재평가 |
| `enterprise-done.md` · `enterprise-done-v2.md` | 완료 내역 |
| `worklog-*.md` | 재개 브리핑 — 무엇을 왜 고쳤는지 |
| `electron-runtime-handoff-*.md` | 런타임 구조·빌드·릴리스 |
| `app-operations.md` | 설치본 운영 (환경변수·중앙 DB 구성) |

**왜 저장소 밖인가.** 납품 진행 상황은 저장소 하나가 아니라 여러 저장소와 릴리스
산출물에 걸쳐 있고, 문서를 대화·인수인계에 그대로 붙여 쓴다. 한 저장소에 두면
다른 저장소의 작업이 이 저장소의 커밋을 기다리게 된다.

**그래서 주의할 점 하나** — 이 문서들은 **git 밖에 있다.** 이력도 되돌리기도 없다.
고칠 때 앞 판을 남길 필요가 있으면 파일을 날짜로 나눠 쓴다(`work-summary-2026-09-28.md`
처럼).
