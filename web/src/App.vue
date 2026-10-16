<template>
  <div id="app" class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
    <!-- Fondo de Igris compartido en ambas superficies de chat -->
    <IgrisHero v-if="$route.name === 'Chat'" />

    <!-- Navegación del espacio de trabajo, compartida y adaptada por rol -->
    <WorkspaceNav v-if="showNav" :admin="isAdmin" :username="displayName" @logout="logout" @connections="requestConnections" @memory="requestMemory" />

    <!-- Page Content (por encima del avatar) -->
    <div style="position: relative; z-index: 10">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import WorkspaceNav from './components/WorkspaceNav.vue'
import { clearKey, getKey } from './api'
import { clearSession, getToken, getUser, isAdminUser } from './userApi'

const route = useRoute()
const router = useRouter()

// El menú del panel solo se muestra a administradores autenticados. El portal
// /u de usuarios normales mantiene únicamente chat, conexiones y memoria.
const ADMIN_ROUTES = ['Configuration', 'AdminConnections']
const isAdmin = computed(() => isAdminUser() || !!getKey())
const showNav = computed(() => route.name === 'UserChat' || (route.name === 'Chat' && isAdmin.value) || (ADMIN_ROUTES.includes(route.name) && isAdmin.value))
const displayName = computed(() => getUser()?.username || 'Administrador')
function requestConnections() { window.dispatchEvent(new Event('igris:open-connections')) }
function requestMemory() { window.dispatchEvent(new Event('igris:open-memory')) }

const displayInitials = computed(() => {
  const parts = displayName.value.trim().split(/\s+/).filter(Boolean)
  return parts.slice(0, 2).map(part => part[0]).join('').toUpperCase()
})

// Borra la clave guardada y vuelve a la pantalla de acceso.
// Al cambiar de ruta, la página actual se desmonta (Dashboard detiene el micrófono).
function logout() {
  const wasAdminUser = isAdminUser()
  clearKey()
  clearSession()
  router.replace(wasAdminUser ? { name: 'UserLogin' } : { name: 'Access' })
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
    'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app { --admin-nav-height: 3.5rem; }
.admin-nav {
  position: fixed;
  inset: 0 0 auto;
  z-index: 20;
  height: var(--admin-nav-height);
  border-bottom: 1px solid rgba(255, 255, 255, 0.11);
  background: rgba(19, 8, 7, 0.94);
  backdrop-filter: blur(12px);
}
.admin-nav__inner {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  width: min(100%, 1200px);
  height: 100%;
  margin: 0 auto;
  padding: 0 2.75rem;
}
.brand { display: inline-flex; align-items: center; width: max-content; color: white; text-decoration: none; }
.brand__mark { width: 1.55rem; height: 1.55rem; color: #f04b45; }
.brand__name { margin-left: .55rem; font-size: 1.18rem; font-weight: 800; letter-spacing: .025em; }
.brand__divider { width: 1px; height: 1.1rem; margin: 0 .9rem; background: rgba(255, 255, 255, .17); }
.brand__workspace { color: #cda99c; font-size: .57rem; font-weight: 700; letter-spacing: .16em; }
.admin-nav__links { display: flex; align-items: center; gap: .45rem; }
.nav-link { display: inline-flex; align-items: center; gap: .45rem; border-radius: .55rem; padding: .68rem .9rem; color: #c8b2a9; font-size: .8rem; text-decoration: none; transition: .2s; }
.nav-link:hover { color: white; background: rgba(255,255,255,.05); }
.nav-link.active { color: white; background: rgba(255,255,255,.09); font-weight: 600; }
.nav-link span { color: #bca79f; font-size: .95rem; line-height: 1; }
.nav-link.active span { color: white; }
.nav-account { display: inline-flex; justify-self: end; align-items: center; gap: .55rem; color: #c8b2a9; font-size: .76rem; }
.nav-logout { border: 0; border-radius: .4rem; padding: .4rem .6rem; color: #c8b2a9; background: transparent; cursor: pointer; font-size: .72rem; }
.nav-logout:hover { color: white; background: rgba(255,255,255,.08); }
.nav-user__initials { display: grid; width: 1.75rem; height: 1.75rem; place-items: center; border-radius: 50%; color: #fff2e9; background: #2e1d1c; font-size: .58rem; font-weight: 700; }
.nav-user__arrow { color: #897972; font-size: 1rem; }
#app:has(.igris--full) > div[style*="z-index: 10"] { padding-top: var(--admin-nav-height); }
@media (max-width: 760px) {
  #app { --admin-nav-height: 5.75rem; }
  .admin-nav__inner { grid-template-columns: 1fr auto; grid-template-rows: 2.5rem 2.75rem; padding: .2rem 1rem 0; gap: 0 .75rem; }
  .admin-nav__links { grid-column: 1 / -1; grid-row: 2; justify-content: space-between; width: 100%; gap: 0; overflow-x: auto; }
  .nav-link { padding: .45rem .65rem; white-space: nowrap; }
  .brand__workspace, .brand__divider, .nav-user__name { display: none; }
  .nav-logout { padding: .35rem .5rem; }
}
@media (max-width: 400px) {
  #app { --admin-nav-height: 5.5rem; }
  .nav-link { gap: .3rem; padding: .42rem .45rem; font-size: .72rem; }
}
</style>
