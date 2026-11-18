// 화면 시험용 진입점 — 앱 셸·로그인 없이 ProposalsPanel 하나만 마운트한다.
// 백엔드는 띄우지 않는다: /api/** 는 Playwright 시험이 page.route 로 가짜 응답을 준다.
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '../../src/app/styles/main.css'
import ProposalsPanel from '../../src/features/proposals/ui/ProposalsPanel.vue'

const app = createApp(ProposalsPanel)
app.use(createPinia())
app.mount('#app')
window.__harnessReady = true
