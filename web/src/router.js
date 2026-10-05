import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './pages/Dashboard.vue'

const routes = [
  {
    path: '/',
    component: Dashboard
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
