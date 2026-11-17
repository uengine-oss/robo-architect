/**
 * POSCO 확장 — 화면 쪽. **지금 posco-web 판이 하는 것을 값으로** 적어 둔다.
 *
 * 근거(posco-web 브랜치, 2026-11-17 기준):
 *   hiddenTabs   TopBar.vue `tabs` — 사내망에 claude CLI 가 없어 Proposals·Code 를 뺐다(2026-09-29)
 *   startTab     App.vue `activeTab = ref('Legacy')` — 감춘 탭으로 열리지 않게
 *   proposals    featureVisibility.js `PROPOSALS_VISIBLE = false` (헌장은 따라간다)
 *   formats      ExportDocumentDialog.vue — DOCX 만
 *   fileName     exportDocument/fileName.js — 설계_{프로젝트명}_서비스설계서_YYYYMMDD_HHmmss.docx
 *
 * ⚠ P3 단계에서 코어가 읽는 것은 hiddenTabs · startTab 둘뿐이다. 나머지는 P5(포스코 옮기기)에서
 *   코어가 이 자리를 읽기 시작할 때 살아난다 — 그때까지 현장 판은 posco-web 브랜치 그대로다.
 *   남은 목록: extensions/posco/README.md
 */
export default {
  id: 'posco',
  shell: {
    hiddenTabs: ['Proposals', 'Code'],
    startTab: 'Legacy',
  },
  features: {
    proposals: false,
  },
  // 레거시 분석은 폴더를 **올려서** 한다(서버의 경로를 지정하는 모드 안 씀).
  legacy: {
    sourceMode: 'upload',
  },
  // Proposals 를 안 쓰므로 새 프로젝트에 대상 폴더 경로가 필요 없다 — 이름만 받는다.
  projects: {
    requireRoot: false,
  },
  deliverables: {
    formats: ['docx'],
    fileNameTemplate: '설계_{project}_{kind}_{yyyyMMdd}_{HHmmss}',
  },
}
