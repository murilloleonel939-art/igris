<!--
  UserLogin.vue — Acceso de usuarios al área /u.

  Sigue exactamente el mismo patrón que la pantalla /acceso del administrador,
  que es la que ya funciona en producción: formulario propio, petición con el
  cliente axios de su área, y manejo local del 401 (sin interceptor que redirija
  en medio del intento). Así una contraseña equivocada muestra "Usuario o
  contraseña incorrectos" y no un error de red confuso.
-->
<template>
  <main class="min-h-screen flex items-center justify-center px-4 py-10">
    <form
      class="w-full max-w-sm rounded-xl border border-slate-700 bg-slate-800/80 p-8 shadow-xl"
      @submit.prevent="submit"
    >
      <h1 class="text-center text-3xl font-semibold tracking-wide text-white">Igris</h1>
      <p class="mt-2 text-center text-sm text-slate-400">Tu asistente personal</p>

      <div class="mt-8">
        <label for="username" class="block text-sm text-slate-300">Usuario</label>
        <input
          id="username"
          ref="userInput"
          v-model="username"
          type="text"
          autocomplete="username"
          autofocus
          :disabled="loading"
          class="mt-2 w-full rounded-lg border border-slate-600 bg-slate-900 px-4 py-2.5 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 disabled:opacity-60"
          @input="error = ''"
        />
      </div>

      <div class="mt-4">
        <label for="password" class="block text-sm text-slate-300">Contraseña</label>
        <input
          id="password"
          v-model="password"
          type="password"
          autocomplete="current-password"
          :disabled="loading"
          class="mt-2 w-full rounded-lg border border-slate-600 bg-slate-900 px-4 py-2.5 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 disabled:opacity-60"
          @input="error = ''"
        />
      </div>

      <p v-if="error" role="alert" class="mt-3 text-sm text-red-400">{{ error }}</p>

      <button
        type="submit"
        :disabled="loading || !username.trim() || !password"
        class="mt-6 w-full rounded-lg bg-blue-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {{ loading ? 'Entrando…' : 'Entrar' }}
      </button>

      <p class="mt-6 text-center text-xs text-slate-500">
        Pide tu usuario al administrador.
      </p>
    </form>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import userApi, { setSession, errorMessage } from '../userApi'

const router = useRouter()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const userInput = ref(null)

onMounted(() => {
  userInput.value?.focus()
})

async function submit() {
  const user = username.value.trim()
  if (loading.value || !user || !password.value) return

  loading.value = true
  error.value = ''

  try {
    // Esta pantalla maneja su propio 401 (el interceptor de userApi no redirige
    // cuando ya estamos en /u/login), igual que hace /acceso con la clave.
    const res = await userApi.post('/api/user/login', {
      username: user,
      password: password.value
    })

    const token = res.data?.access_token
    if (!token) throw new Error('Respuesta inesperada')

    setSession(token, res.data.user)
    await router.replace('/u')
  } catch (e) {
    const status = e.response?.status
    if (status === 401) {
      error.value = 'Usuario o contraseña incorrectos'
      password.value = ''
    } else if (status === 403) {
      error.value = errorMessage(e, 'Tu cuenta está desactivada')
    } else if (status === 429) {
      error.value = 'Demasiados intentos, espera unos minutos'
    } else if (status === 422) {
      error.value = errorMessage(e, 'Revisa los datos')
    } else {
      error.value = 'No se pudo conectar con el servidor'
    }
  } finally {
    loading.value = false
  }
}
</script>
