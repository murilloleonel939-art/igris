<template>
  <main class="min-h-screen flex flex-col items-center justify-center px-4 py-10">
    <!-- El aviso de instalación va aquí, en la pantalla de entrada del
         administrador: es donde tiene sentido ofrecerle instalar la app. -->
    <InstallHint />

    <form
      class="w-full max-w-sm rounded-xl border border-slate-700 bg-slate-800/80 p-8 shadow-xl"
      @submit.prevent="submit"
    >
      <h1 class="text-center text-3xl font-semibold tracking-wide text-white">Igris</h1>

      <div class="mt-8">
        <label for="access-key" class="block text-sm text-slate-300">Clave de acceso</label>
        <input
          id="access-key"
          ref="keyInput"
          v-model="key"
          type="password"
          autocomplete="current-password"
          autofocus
          :disabled="loading"
          class="mt-2 w-full rounded-lg border border-slate-600 bg-slate-900 px-4 py-2.5 text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40 disabled:opacity-60"
          @input="error = ''"
        />
      </div>

      <p v-if="error" role="alert" class="mt-3 text-sm text-red-400">{{ error }}</p>

      <button
        type="submit"
        :disabled="loading || !key.trim()"
        class="mt-6 w-full rounded-lg bg-blue-600 px-4 py-2.5 font-medium text-white transition-colors hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {{ loading ? 'Verificando…' : 'Entrar' }}
      </button>
    </form>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api, { setKey } from '../api'
import InstallHint from '../components/InstallHint.vue'

const router = useRouter()

const key = ref('')
const loading = ref(false)
const error = ref('')
const keyInput = ref(null)

onMounted(() => {
  keyInput.value?.focus()
})

async function submit() {
  const candidate = key.value.trim()
  if (loading.value || !candidate) return

  loading.value = true
  error.value = ''

  try {
    // Esta pantalla envía la clave tipeada y maneja su propio 401:
    // api.js no redirige cuando la ruta actual es /acceso.
    const res = await api.get('/api/auth/check', {
      headers: { 'X-Igris-Key': candidate }
    })
    if (res.data?.ok !== true) {
      throw new Error('Respuesta inesperada')
    }
    setKey(candidate)
    await router.replace('/')
  } catch (e) {
    const status = e.response?.status
    if (status === 401) {
      error.value = 'Clave incorrecta'
      key.value = ''
    } else if (status === 429) {
      error.value = 'Demasiados intentos, espera unos minutos'
    } else {
      // Sin respuesta (red caída, CORS) o respuesta inesperada
      error.value = 'No se pudo conectar con el servidor'
    }
  } finally {
    loading.value = false
    // El input estaba deshabilitado durante la petición: se devuelve el foco
    if (!error.value) return
    setTimeout(() => keyInput.value?.focus(), 0)
  }
}
</script>
