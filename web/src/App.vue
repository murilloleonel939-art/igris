<template>
  <div id="app" class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
    <!-- Igris a pantalla completa de fondo (solo en el chat del administrador;
         el chat de usuarios monta su propio fondo dentro de UserChat) -->
    <IgrisHero v-if="$route.name === 'Chat'" />

    <!-- Navigation Menu (solo en las rutas del administrador) -->
    <nav
      v-if="showNav"
      class="border-b border-slate-700"
      style="position: relative; z-index: 10; background: rgba(15, 23, 42, 0.55); backdrop-filter: blur(6px)"
    >
      <div class="max-w-4xl mx-auto px-6 py-3 flex flex-wrap justify-center items-center gap-3">
        <router-link 
          to="/" 
          :class="{ 'bg-blue-600 text-white': $route.name === 'Chat', 'bg-slate-600 hover:bg-slate-700 text-slate-300': $route.name !== 'Chat' }"
          class="px-4 py-2 rounded transition-all"
        >
          💬 Chat
        </router-link>
        <router-link 
          to="/config" 
          :class="{ 'bg-blue-600 text-white': $route.name === 'Configuration', 'bg-slate-600 hover:bg-slate-700 text-slate-300': $route.name !== 'Configuration' }"
          class="px-4 py-2 rounded transition-all"
        >
          ⚙️ Configuración
        </router-link>
        <router-link
          v-if="adminUserLoggedIn"
          to="/u"
          class="px-4 py-2 rounded transition-all bg-slate-600 hover:bg-slate-700 text-slate-300"
        >
          🔗 Conexiones
        </router-link>
        <router-link 
          to="/panel/usuarios" 
          :class="{ 'bg-blue-600 text-white': $route.name === 'AdminUsers', 'bg-slate-600 hover:bg-slate-700 text-slate-300': $route.name !== 'AdminUsers' }"
          class="px-4 py-2 rounded transition-all"
        >
          👥 Usuarios
        </router-link>
        <button
          type="button"
          class="px-3 py-1.5 rounded text-sm text-slate-400 hover:text-white hover:bg-slate-700 transition-all"
          @click="logout"
        >
          Salir
        </button>
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
import { clearSession, isAdminUser } from './userApi'

const route = useRoute()
const router = useRouter()

// El menú es solo del administrador. El área de usuarios (/u) tiene su propia
// barra con su nombre y su botón de salir, y no debe ver ni Configuración ni
// Usuarios ni la pantalla de la clave.
const ADMIN_ROUTES = ['Chat', 'Configuration', 'AdminUsers']
const showNav = computed(() => ADMIN_ROUTES.includes(route.name))
const adminUserLoggedIn = computed(() => isAdminUser())

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
</style>
