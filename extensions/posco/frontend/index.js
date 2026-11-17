/**
 * POSCO 확장 — 화면 쪽. **지금 posco-web 판이 하는 것을 값으로** 적어 둔다.
 *
 * 근거(posco-web 브랜치, 2026-11-17 기준):
 *   hiddenTabs   TopBar.vue `tabs` — 사내망에 claude CLI 가 없어 Proposals·Code 를 뺐다(2026-09-29)
 *   startTab     App.vue `activeTab = ref('Legacy')` — 감춘 탭으로 열리지 않게
 *   proposals    featureVisibility.js `PROPOSALS_VISIBLE = false` (헌장은 따라간다)
 *   formats      ExportDocumentDialog.vue — DOCX 만
 *   fileName     exportDocument/fileName.js — 설계_{프로젝트명}_서비스설계서_YYYYMMDD_HHmmss.docx
 *   ecm          ExportDocumentDialog.vue — 정본화 결과를 'ECM 등록' 으로 말한다
 *   gatewayName  AiRoutingSection.vue · LlmModelSection.vue — 'P-GPT'
 *   templates    TemplatePanel.vue — 기본 묶음 template-poscodx · 설명 · com.poscodx 패키지
 *   sourceMode   AnalysisPanel.vue readRoot() — 경로 모드 안 씀
 *
 * 화면 쪽 항목은 P5 에서 코어가 모두 읽게 됐다. 남은(백엔드) 목록: extensions/posco/README.md
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
    // 납품 문서는 사내 ECM 에 등록한다 — 정본화 결과를 ECM 기준으로 말한다.
    ecm: true,
  },
  ai: {
    gatewayName: 'P-GPT',
  },
  templates: {
    defaultSet: 'template-poscodx',
    description: '이벤트 스토밍 요소로 POSCO DX 5계층 Java 프로젝트를 생성합니다.',
    packagePrefix: 'com.poscodx',
  },
}
