import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './app/styles/main.css'

const app = createApp(App)
app.use(createPinia())
app.mount('#app')

