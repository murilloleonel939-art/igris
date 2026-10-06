import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './pages/Dashboard.vue'
import Configuration from './pages/Configuration.vue'
import Access from './pages/Access.vue'
import { getKey } from './api'

const routes = [
  {
    path: '/',
    name: 'Chat',
    component: Dashboard
  },
  {
    path: '/config',
    name: 'Configuration',
    component: Configuration
  },
  {
    path: '/acceso',
    name: 'Access',
    component: Access
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Sin clave guardada solo se puede ver la pantalla de acceso;
// con clave guardada, la pantalla de acceso no tiene sentido.
router.beforeEach((to) => {
  const hasKey = !!getKey()
  if (!hasKey && to.name !== 'Access') {
    return { name: 'Access' }
  }
  if (hasKey && to.name === 'Access') {
    return { path: '/' }
  }
})

// api.js emite este evento cuando el backend responde 401 (clave borrada o
// cambiada). Navegar desde aquí desmonta la página actual (Dashboard detiene
// el micrófono en su limpieza) y evita importar el router desde api.js.
window.addEventListener('igris:unauthorized', () => {
  if (router.currentRoute.value.name !== 'Access') {
    router.replace({ name: 'Access' })
  }
})

export default router
