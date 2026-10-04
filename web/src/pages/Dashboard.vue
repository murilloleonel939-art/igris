<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
    <!-- Header -->
    <header class="bg-slate-800 border-b border-slate-700 sticky top-0 z-10">
      <div class="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-white">🔮 IGRIS Dashboard</h1>
          <span class="text-sm text-gray-400">v2.0</span>
        </div>
        <div class="flex items-center gap-4">
          <span class="text-gray-300">{{ authStore.user?.username }}</span>
          <button
            @click="logout"
            class="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded transition"
          >
            Logout
          </button>
        </div>
      </div>
    </header>

    <!-- Content -->
    <div class="max-w-7xl mx-auto px-6 py-8">
      <!-- Tabs -->
      <div class="flex gap-4 mb-8 border-b border-slate-700">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="[
            'px-6 py-3 font-semibold transition border-b-2',
            activeTab === tab.id
              ? 'border-blue-500 text-blue-400'
              : 'border-transparent text-gray-400 hover:text-gray-300'
          ]"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="space-y-6">
        <!-- IA Providers -->
        <div v-if="activeTab === 'providers'" class="space-y-6">
          <div class="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 class="text-xl font-bold text-white mb-4">⚙️ Configuración de Proveedores IA</h2>
            
            <div class="space-y-4">
              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">
                  Proveedor Principal
                </label>
                <select
                  v-model="aiConfig.primaryProvider"
                  @change="updateAIConfig"
                  class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="groq">🚀 Groq (Gratis, rápido)</option>
                  <option value="openai">🔵 OpenAI (GPT-4)</option>
                  <option value="anthropic">🤖 Anthropic (Claude)</option>
                  <option value="local">💻 Local (Ollama)</option>
                </select>
                <p class="text-xs text-gray-500 mt-1">Proveedor que se usará primero</p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">
                  Cadena de Fallback
                </label>
                <div class="space-y-2">
                  <div
                    v-for="(provider, index) in aiConfig.fallbackChain"
                    :key="index"
                    class="flex items-center gap-3 bg-slate-700 p-3 rounded"
                  >
                    <span class="text-gray-400">{{ index + 1 }}.</span>
                    <span class="flex-1 text-white">{{ provider }}</span>
                    <button
                      v-if="index > 0"
                      @click="moveUp(index)"
                      class="text-blue-400 hover:text-blue-300"
                    >
                      ↑
                    </button>
                    <button
                      v-if="index < aiConfig.fallbackChain.length - 1"
                      @click="moveDown(index)"
                      class="text-blue-400 hover:text-blue-300"
                    >
                      ↓
                    </button>
                  </div>
                </div>
                <p class="text-xs text-gray-500 mt-2">
                  Si falla el proveedor principal, intenta con los siguientes en orden
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">
                  STT Provider (Speech-to-Text)
                </label>
                <select
                  v-model="aiConfig.sttProvider"
                  @change="updateAIConfig"
                  class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="local">Local (Whisper)</option>
                  <option value="openai">OpenAI API</option>
                </select>
              </div>

              <div>
                <label class="block text-sm font-medium text-gray-300 mb-2">
                  TTS Provider (Text-to-Speech)
                </label>
                <select
                  v-model="aiConfig.ttsProvider"
                  @change="updateAIConfig"
                  class="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-500"
                >
                  <option value="local">Local (Piper)</option>
                  <option value="edge-tts">Edge TTS (Microsoft)</option>
                </select>
              </div>

              <button
                @click="saveConfig"
                :disabled="saving"
                class="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-bold py-2 px-4 rounded transition"
              >
                {{ saving ? 'Guardando...' : '💾 Guardar Configuración' }}
              </button>

              <div v-if="successMessage" class="bg-green-900 border border-green-700 text-green-200 px-4 py-3 rounded">
                {{ successMessage }}
              </div>
            </div>
          </div>
        </div>

        <!-- Perfiles de Usuarios -->
        <div v-if="activeTab === 'profiles'" class="space-y-6">
          <div class="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <div class="flex justify-between items-center mb-4">
              <h2 class="text-xl font-bold text-white">👥 Perfiles Autorizados</h2>
              <button
                @click="showCreateProfile = true"
                class="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded transition"
              >
                + Nuevo Perfil
              </button>
            </div>

            <!-- Create Profile Form -->
            <div v-if="showCreateProfile" class="bg-slate-700 p-4 rounded mb-4 space-y-3">
              <input
                v-model="newProfile.name"
                type="text"
                placeholder="Nombre del perfil"
                class="w-full px-4 py-2 bg-slate-600 border border-slate-500 rounded text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
              <div class="flex gap-4">
                <label class="flex items-center text-gray-300">
                  <input
                    v-model="newProfile.canExecuteCommands"
                    type="checkbox"
                    class="mr-2"
                  />
                  Ejecutar comandos
                </label>
                <label class="flex items-center text-gray-300">
                  <input
                    v-model="newProfile.canManageUsers"
                    type="checkbox"
                    class="mr-2"
                  />
                  Gestionar usuarios
                </label>
              </div>
              <div class="flex gap-2">
                <button
                  @click="createProfile"
                  class="flex-1 bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded transition"
                >
                  Crear
                </button>
                <button
                  @click="showCreateProfile = false"
                  class="flex-1 bg-gray-600 hover:bg-gray-700 text-white px-4 py-2 rounded transition"
                >
                  Cancelar
                </button>
              </div>
            </div>

            <!-- Profiles List -->
            <div class="space-y-3">
              <div
                v-for="profile in profiles"
                :key="profile.id"
                class="bg-slate-700 p-4 rounded flex justify-between items-center"
              >
                <div>
                  <h3 class="text-white font-semibold">{{ profile.name }}</h3>
                  <p class="text-sm text-gray-400">
                    {{ profile.canExecuteCommands ? '✓ Ejecutar comandos' : '' }}
                    {{ profile.canManageUsers ? '✓ Gestionar usuarios' : '' }}
                  </p>
                </div>
                <button
                  @click="deleteProfile(profile.id)"
                  class="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded transition text-sm"
                >
                  Eliminar
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 2FA -->
        <div v-if="activeTab === '2fa'" class="space-y-6">
          <div class="bg-slate-800 rounded-lg p-6 border border-slate-700">
            <h2 class="text-xl font-bold text-white mb-4">🔐 Autenticación de Dos Factores</h2>
            
            <div v-if="!twoFAEnabled" class="space-y-4">
              <p class="text-gray-400">
                Protege tu cuenta con Google Authenticator
              </p>
              <button
                @click="setupTwoFA"
                :disabled="twoFALoading"
                class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-bold py-2 px-4 rounded transition"
              >
                {{ twoFALoading ? 'Preparando...' : '🔓 Activar 2FA' }}
              </button>

              <!-- QR Code -->
              <div v-if="twoFAQR" class="bg-slate-700 p-4 rounded space-y-4">
                <p class="text-sm text-gray-300">
                  Escanea este código QR con Google Authenticator:
                </p>
                <img :src="twoFAQR.qr_code" alt="QR Code" class="mx-auto w-48 h-48" />
                <p class="text-xs text-gray-400 text-center">
                  Secreto: <code class="bg-slate-600 px-2 py-1 rounded">{{ twoFAQR.secret }}</code>
                </p>
                <div>
                  <input
                    v-model="twoFACode"
                    type="text"
                    maxlength="6"
                    placeholder="Código 6 dígitos"
                    class="w-full px-4 py-2 bg-slate-600 border border-slate-500 rounded text-white text-center text-2xl tracking-widest focus:outline-none focus:border-blue-500"
                  />
                </div>
                <button
                  @click="confirmTwoFA"
                  class="w-full bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded transition"
                >
                  Confirmar
                </button>
              </div>
            </div>

            <div v-else class="space-y-4">
              <div class="bg-green-900 border border-green-700 text-green-200 px-4 py-3 rounded">
                ✓ 2FA está activado
              </div>
              <button
                @click="disableTwoFA"
                class="bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded transition"
              >
                🔒 Desactivar 2FA
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref('providers')
const tabs = [
  { id: 'providers', label: '⚙️ Proveedores IA' },
  { id: 'profiles', label: '👥 Perfiles' },
  { id: '2fa', label: '🔐 2FA' }
]

const aiConfig = ref({
  primaryProvider: 'groq',
  fallbackChain: ['groq', 'openai', 'anthropic', 'local'],
  sttProvider: 'local',
  ttsProvider: 'local'
})

const profiles = ref([])
const saving = ref(false)
const successMessage = ref('')
const showCreateProfile = ref(false)

const newProfile = ref({
  name: '',
  canExecuteCommands: true,
  canManageUsers: false
})

const twoFAEnabled = ref(false)
const twoFALoading = ref(false)
const twoFAQR = ref(null)
const twoFACode = ref('')

onMounted(async () => {
  await loadDashboard()
})

const logout = () => {
  authStore.logout()
  router.push('/login')
}

const loadDashboard = async () => {
  try {
    const response = await api.get('/api/dashboard')
    aiConfig.value = {
      primaryProvider: response.data.ai_config.primary_provider,
      fallbackChain: response.data.ai_config.fallback_chain,
      sttProvider: response.data.ai_config.stt_provider,
      ttsProvider: response.data.ai_config.tts_provider
    }
    profiles.value = response.data.profiles
    twoFAEnabled.value = response.data.two_fa_enabled
  } catch (error) {
    console.error('Error loading dashboard:', error)
  }
}

const updateAIConfig = async () => {
  // Actualizar inmediatamente
  await saveConfig()
}

const moveUp = (index) => {
  if (index > 0) {
    const temp = aiConfig.value.fallbackChain[index]
    aiConfig.value.fallbackChain[index] = aiConfig.value.fallbackChain[index - 1]
    aiConfig.value.fallbackChain[index - 1] = temp
    saveConfig()
  }
}

const moveDown = (index) => {
  if (index < aiConfig.value.fallbackChain.length - 1) {
    const temp = aiConfig.value.fallbackChain[index]
    aiConfig.value.fallbackChain[index] = aiConfig.value.fallbackChain[index + 1]
    aiConfig.value.fallbackChain[index + 1] = temp
    saveConfig()
  }
}

const saveConfig = async () => {
  try {
    saving.value = true
    successMessage.value = ''
    
    await api.put('/api/ai-config', {
      primary_provider: aiConfig.value.primaryProvider,
      fallback_chain: aiConfig.value.fallbackChain,
      stt_provider: aiConfig.value.sttProvider,
      tts_provider: aiConfig.value.ttsProvider
    })
    
    successMessage.value = '✓ Configuración guardada'
    setTimeout(() => {
      successMessage.value = ''
    }, 3000)
  } catch (error) {
    console.error('Error saving config:', error)
  } finally {
    saving.value = false
  }
}

const createProfile = async () => {
  try {
    const response = await api.post('/api/profiles', {
      name: newProfile.value.name,
      can_execute_commands: newProfile.value.canExecuteCommands,
      can_manage_users: newProfile.value.canManageUsers
    })
    
    profiles.value.push(response.data)
    newProfile.value = {
      name: '',
      canExecuteCommands: true,
      canManageUsers: false
    }
    showCreateProfile.value = false
  } catch (error) {
    console.error('Error creating profile:', error)
  }
}

const deleteProfile = async (profileId) => {
  if (confirm('¿Estás seguro de que deseas eliminar este perfil?')) {
    try {
      await api.delete(`/api/profiles/${profileId}`)
      profiles.value = profiles.value.filter(p => p.id !== profileId)
    } catch (error) {
      console.error('Error deleting profile:', error)
    }
  }
}

const setupTwoFA = async () => {
  try {
    twoFALoading.value = true
    const response = await authStore.setup2FA()
    twoFAQR.value = response
  } catch (error) {
    console.error('Error setup 2FA:', error)
  } finally {
    twoFALoading.value = false
  }
}

const confirmTwoFA = async () => {
  try {
    const response = await authStore.verify2FA(twoFACode.value)
    if (response.success) {
      twoFAEnabled.value = true
      twoFAQR.value = null
      twoFACode.value = ''
      alert('2FA activado correctamente. Guarda tus códigos de respaldo.')
    }
  } catch (error) {
    console.error('Error confirming 2FA:', error)
    alert('Código incorrecto, intenta de nuevo')
  }
}

const disableTwoFA = async () => {
  const password = prompt('Ingresa tu contraseña para desactivar 2FA:')
  if (password) {
    try {
      await authStore.disable2FA(password)
      twoFAEnabled.value = false
      alert('2FA desactivado')
    } catch (error) {
      console.error('Error disabling 2FA:', error)
    }
  }
}
</script>
