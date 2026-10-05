<template>
  <div id="app" class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
    <!-- Navigation Menu -->
    <nav class="bg-slate-800 border-b border-slate-700">
      <div class="max-w-2xl mx-auto px-6 py-3 flex justify-center space-x-4">
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
      </div>
    </nav>

    <!-- Page Content -->
    <router-view />
  </div>
</template>

<script setup>
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
