import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from './router'
import App from './App.vue'
import './style.css'
import { initPwa } from './pwa'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')

// Se registra el service worker y se escucha el aviso de instalación.
// Después del mount para no retrasar el primer pintado.
initPwa()
