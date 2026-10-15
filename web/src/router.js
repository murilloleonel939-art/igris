import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from './pages/Dashboard.vue'
import Configuration from './pages/Configuration.vue'
import Access from './pages/Access.vue'
import AdminUsers from './pages/AdminUsers.vue'
import UserLogin from './pages/UserLogin.vue'
import UserChat from './pages/UserChat.vue'
import { getKey } from './api'
import { isLoggedIn, isAdminUser } from './userApi'
import { syncManifest } from './pwa'

// Las dos superficies de la aplicación, separadas:
//
//   Administrador  /            -> clave única (X-Igris-Key, en localStorage)
//                  /config
//                  /panel/usuarios
//                  /acceso       -> pantalla de la clave
//
//   Usuarios       /u           -> chat/conexiones (token Bearer)
//                  /u/login     -> pantalla de usuario y contraseña
//
// Un usuario normal queda en /u. Un usuario con is_admin=true también puede
// abrir el panel del administrador; el backend vuelve a validar ese permiso.
const USER_ROUTE_NAMES = ['UserLogin', 'UserChat']

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
    path: '/panel/usuarios',
    name: 'AdminUsers',
    component: AdminUsers
  },
  {
    path: '/acceso',
    name: 'Access',
    component: Access
  },
  {
    path: '/u',
    name: 'UserChat',
    component: UserChat,
    meta: { requiresUser: true }
  },
  {
    path: '/u/login',
    name: 'UserLogin',
    component: UserLogin
  },
  {
    // Cualquier otra ruta bajo /u lleva al acceso de usuarios.
    // Sin esto, una URL mal escrita mostraría la pantalla del administrador.
    path: '/u/:pathMatch(.*)*',
    redirect: '/u/login'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const wantsUser = USER_ROUTE_NAMES.includes(to.name) || to.meta.requiresUser

  if (wantsUser) {
    // --- Área de usuarios ---
    const logged = isLoggedIn()
    if (!logged && to.name !== 'UserLogin') {
      return { name: 'UserLogin' }
    }
    // Ya dentro: la pantalla de acceso de usuarios no tiene sentido
    if (logged && to.name === 'UserLogin') {
      return { path: '/u' }
    }
    return true
  }

  // --- Área del administrador ---
  // Se permite la clave histórica o un usuario logueado con is_admin=true.
  const hasAdminAccess = !!getKey() || isAdminUser()
  if (!hasAdminAccess && to.name !== 'Access') {
    return { name: 'Access' }
  }
  if (hasAdminAccess && to.name === 'Access') {
    return { path: '/' }
  }
})

// Cada ruta necesita su propio manifest: /u y /u/login son la app de los
// usuarios (abren en /u/login) y el resto es la del administrador (abre en
// /acceso). El servidor ya sirve el correcto al cargar la página; esto lo
// mantiene al día en la navegación interna, sin recargar.
router.afterEach((to) => {
  syncManifest(to.path)
})

// api.js emite este evento cuando el backend responde 401 (clave borrada o
// cambiada). Navegar desde aquí desmonta la página actual (Dashboard detiene
// el micrófono en su limpieza) y evita importar el router desde api.js.
window.addEventListener('igris:unauthorized', () => {
  if (router.currentRoute.value.name !== 'Access') {
    router.replace({ name: 'Access' })
  }
})

// userApi.js emite este evento cuando el token del usuario caduca o deja de
// valer. Es un evento aparte para que un fallo de un usuario no toque la clave
// del administrador.
window.addEventListener('igris:user-unauthorized', () => {
  if (router.currentRoute.value.name !== 'UserLogin') {
    router.replace({ name: 'UserLogin' })
  }
})

export default router
