import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './pages/Dashboard.vue'
import Configuration from './pages/Configuration.vue'

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
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
