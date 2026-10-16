<template>
  <div id="app" class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
    <!-- Igris a pantalla completa de fondo (solo en el chat del administrador;
         el chat de usuarios monta su propio fondo dentro de UserChat) -->
    <IgrisHero v-if="$route.name === 'Chat'" />

    <!-- Navegación administrativa -->
    <nav v-if="showNav" class="admin-nav">
      <div class="admin-nav__inner">
        <router-link to="/" class="brand" aria-label="Igris · Chat">
          <svg class="brand__mark" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3.2 4.3 5.4 2l4.1 4.1v3.1L3.2 4.3Zm8.2 1.8L15.5 2l2.2 2.3-6.3 6.3V6.1Zm-8 5.2 2.2-2.2 6.3 6.3v3.1L3.4 11.3Zm8.2 3.2 6.3-6.3 2.2 2.2-8.5 8.5v-4.4Zm-6.3 5.2 2.2-2.2 2.3 2.3-2.2 2.2-2.3-2.3Zm9.5-1.1 2.2-2.2 2.2 2.2-2.2 2.2-2.2-2.2Z"/></svg>
          <span class="brand__name">IGRIS</span><span class="brand__divider"></span><span class="brand__workspace">WORKSPACE</span>
        </router-link>

        <div class="admin-nav__links">
          <router-link to="/" class="nav-link" :class="{ active: $route.name === 'Chat' }"><span>▢</span> Chat</router-link>
          <router-link to="/config" class="nav-link" :class="{ active: $route.name === 'Configuration' }"><span>⌘</span> Configuración</router-link>
          <router-link to="/panel/conexiones" class="nav-link" :class="{ active: $route.name === 'AdminConnections' }"><span>♧</span> Conexiones</router-link>
          <router-link to="/panel/usuarios" class="nav-link" :class="{ active: $route.name === 'AdminUsers' }"><span>♧</span> Usuarios</router-link>
        </div>

        <button type="button" class="nav-user" @click="logout" title="Cerrar sesión de {{ displayName }}"><span class="nav-user__initials">{{ displayInitials }}</span><span class="nav-user__name">{{ displayName }}</span><span class="nav-user__arrow">⌄</span></button>
      </div>
    </nav>

    <!-- Page Content (por encima del avatar) -->
    <div style="position: relative; z-index: 10">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import IgrisHero from './components/IgrisHero.vue'
import { clearKey } from './api'
import { clearSession, getUser } from './userApi'

const route = useRoute()
const router = useRouter()

// El menú es solo del administrador. El área de usuarios (/u) tiene su propia
// barra con su nombre y su botón de salir, y no debe ver ni Configuración ni
// Usuarios ni la pantalla de la clave.
const ADMIN_ROUTES = ['Chat', 'Configuration', 'AdminUsers', 'AdminConnections']
const showNav = computed(() => ADMIN_ROUTES.includes(route.name))
const displayName = computed(() => getUser()?.username || 'Administrador')
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
.nav-user { display: inline-flex; justify-self: end; align-items: center; gap: .55rem; border: 0; border-radius: .5rem; padding: .35rem; color: #c8b2a9; background: transparent; cursor: pointer; font-size: .76rem; transition: .2s; }
.nav-user:hover { background: rgba(255,255,255,.06); color: white; }
.nav-user__initials { display: grid; width: 1.75rem; height: 1.75rem; place-items: center; border-radius: 50%; color: #fff2e9; background: #2e1d1c; font-size: .58rem; font-weight: 700; }
.nav-user__arrow { color: #897972; font-size: 1rem; }
#app:has(.igris--full) > div[style*="z-index: 10"] { padding-top: var(--admin-nav-height); }
@media (max-width: 760px) {
  #app { --admin-nav-height: 5.75rem; }
  .admin-nav__inner { grid-template-columns: 1fr auto; grid-template-rows: 2.5rem 2.75rem; padding: .2rem 1rem 0; gap: 0 .75rem; }
  .admin-nav__links { grid-column: 1 / -1; grid-row: 2; justify-content: space-between; width: 100%; gap: 0; overflow-x: auto; }
  .nav-link { padding: .45rem .65rem; white-space: nowrap; }
  .brand__workspace, .brand__divider, .nav-user__name { display: none; }
}
@media (max-width: 400px) {
  #app { --admin-nav-height: 5.5rem; }
  .nav-link { gap: .3rem; padding: .42rem .45rem; font-size: .72rem; }
}
</style>
