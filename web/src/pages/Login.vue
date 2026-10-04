<template>
  <div class="min-h-screen flex items-center justify-center px-4">
    <div class="w-full max-w-md">
      <!-- Logo -->
      <div class="text-center mb-10">
        <h1 class="text-4xl font-bold text-white mb-2">🔮 IGRIS</h1>
        <p class="text-gray-400">Plataforma de Control de IA</p>
      </div>

      <!-- Formulario -->
      <div class="bg-slate-800 rounded-lg shadow-2xl p-8 border border-slate-700">
        <!-- Solo Login -->
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">Usuario</label>
            <input
              v-model="login.username"
              type="text"
              class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              placeholder="Tu usuario"
              @keyup.enter="handleLogin"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-gray-300 mb-2">Contraseña</label>
            <input
              v-model="login.password"
              type="password"
              class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              placeholder="Tu contraseña"
              @keyup.enter="handleLogin"
            />
          </div>

          <!-- 2FA Code (si requiere) -->
          <div v-if="requiresOTP">
            <label class="block text-sm font-medium text-gray-300 mb-2">
              Código Google Authenticator
            </label>
            <input
              v-model="login.otpCode"
              type="text"
              maxlength="6"
              class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 text-center text-2xl tracking-widest"
              placeholder="000000"
              @keyup.enter="handleLogin"
            />
            <p class="text-xs text-gray-400 mt-2">
              Si no tienes código, puedes usar un código de respaldo
            </p>
          </div>

          <!-- Errores -->
          <div v-if="error" class="bg-red-900 border border-red-700 text-red-200 px-4 py-3 rounded">
            {{ error }}
          </div>

          <!-- Botón Login -->
          <button
            @click="handleLogin"
            :disabled="loading"
            class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-bold py-2 px-4 rounded transition"
          >
            {{ loading ? 'Iniciando...' : 'Iniciar Sesión' }}
          </button>
        </div>


      </div>

      <!-- Footer -->
      <p class="text-center text-gray-500 text-sm mt-6">
        IGRIS v2.0 | Plataforma segura con autenticación 2FA
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref('login')
const loading = ref(false)
const error = ref('')
const requiresOTP = ref(false)

const login = ref({
  username: '',
  password: '',
  otpCode: ''
})

const register = ref({
  username: '',
  email: '',
  password: '',
  confirmPassword: ''
})

const handleLogin = async () => {
  try {
    loading.value = true
    error.value = ''
    
    await authStore.login(
      login.value.username,
      login.value.password,
      login.value.otpCode
    )
    
    router.push('/dashboard')
  } catch (err) {
    if (err.error?.includes('2FA')) {
      requiresOTP.value = true
      error.value = 'Por favor ingresa tu código 2FA'
    } else {
      error.value = err.error || 'Error en login'
    }
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  try {
    loading.value = true
    error.value = ''
    
    if (register.value.password !== register.value.confirmPassword) {
      error.value = 'Las contraseñas no coinciden'
      loading.value = false
      return
    }
    
    await authStore.register(
      register.value.username,
      register.value.email,
      register.value.password,
      register.value.confirmPassword
    )
    
    error.value = ''
    activeTab.value = 'login'
    login.value.username = register.value.username
    login.value.password = register.value.password
    
    alert('¡Cuenta creada! Por favor inicia sesión')
  } catch (err) {
    error.value = err.error || 'Error en registro'
  } finally {
    loading.value = false
  }
}
</script>
