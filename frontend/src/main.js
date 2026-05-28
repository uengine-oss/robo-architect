import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './app/styles/main.css'
import './open-pencil-theme.css'

import { bootstrapAIDesign } from './features/aiDesign/bootstrap'
import { preloadKoreanFont } from './features/aiDesign/fonts'
import { useLanguageStore } from './app/language.store'
import { installLanguageFetchInterceptor } from './app/httpInterceptor'

const app = createApp(App)
app.use(createPinia())

// Feature 031: install the global window.fetch patch that attaches
// Accept-Language to every outbound request. Must run AFTER Pinia is
// registered (the patch dereferences useLanguageStore() lazily on each
// call) and BEFORE any feature code issues a fetch. Touching the store
// once here forces its eager `initLanguage()` to run so the first fetch
// already has a value to read.
useLanguageStore()
installLanguageFetchInterceptor()

// Wire open-pencil's AI provider to the backend proxy. Pure static config —
// no backend fetch needed. The real provider/model/credentials live on the
// backend; the browser only needs SDK plumbing values to know where to POST.
bootstrapAIDesign()

// Preload a bundled Korean font for the CanvasKit renderer. open-pencil's
// default CJK fallback path (Google Fonts metadata API) is rate-limited, so
// without this Hangul renders as tofu in the FrameEditor.
preloadKoreanFont()

app.mount('#app')

