import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './app/styles/main.css'
import './open-pencil-theme.css'

import { bootstrapAIDesign } from './features/aiDesign/bootstrap'
import { preloadKoreanFont } from './features/aiDesign/fonts'
// 032: identity-header interceptor — installed before any data fetch so
// every backend request carries X-User-Name/X-User-Email once the launcher
// has populated the session store. In web mode the interceptor stays
// installed but is a no-op (session.user is null).
import { installIdentityInterceptor } from './app/http.js'

const app = createApp(App)
app.use(createPinia())
installIdentityInterceptor()

// Wire open-pencil's AI provider to the backend proxy. Pure static config —
// no backend fetch needed. The real provider/model/credentials live on the
// backend; the browser only needs SDK plumbing values to know where to POST.
bootstrapAIDesign()

// Preload a bundled Korean font for the CanvasKit renderer. open-pencil's
// default CJK fallback path (Google Fonts metadata API) is rate-limited, so
// without this Hangul renders as tofu in the FrameEditor.
preloadKoreanFont()

app.mount('#app')

