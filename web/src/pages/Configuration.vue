<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
    <!-- Header -->
    <header class="bg-slate-800 border-b border-slate-700 sticky top-0 z-10">
      <div class="max-w-2xl mx-auto px-6 py-4 flex justify-between items-center">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-white">⚙️ Configuración de IA</h1>
        </div>
        <div class="flex items-center gap-2">
          <router-link to="/" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded transition">
            ← Volver al Chat
          </router-link>
        </div>
      </div>
    </header>

    <!-- Content -->
    <div class="max-w-2xl mx-auto px-6 py-8 flex flex-col h-[calc(100%-160px)]">
      <!-- Status Alert -->
      <div v-if="loading" class="bg-slate-700 rounded-lg p-4 mb-4">
        <div class="flex items-center gap-2">
          <svg class="w-5 h-5 text-blue-400 animate-spin" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
          </svg>
          <span class="text-blue-300">Cargando configuración...</span>
        </div>
      </div>
      
      <div v-if="error" class="bg-red-900/50 border border-red-500 rounded-lg p-4 mb-4">
        <div class="flex items-center gap-2">
          <svg class="w-5 h-5 text-red-400" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2a10 10 0 100 20 20 10 10 0 000-20zm0-2a8 8 0 110 0 16 8 8 0 010-16z"/></svg>
          <span class="text-red-300">{{ error }}</span>
        </div>
      </div>

      <div v-if="aiConfig" class="bg-slate-800 rounded-lg p-6 space-y-6">
        <!-- Active Provider -->
        <div>
          <h2 class="text-lg font-semibold text-white mb-2">Proveedor Activo Actual</h2>
          <div class="bg-slate-700 rounded-lg p-4">
            <div class="flex items-center">
              <svg class="w-5 h-5 text-blue-400 mr-2" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2L15 6l3 3h-5l3 5L12 14l-5-5h-5l3-3-3-3z"/></svg>
              <span>{{ aiConfig.primary_provider }}</span>
            </div>
            <p class="text-sm text-slate-400 mt-1">Este es el proveedor que Igris intenta usar primero</p>
          </div>
        </div>

        <!-- Available Providers -->
        <div>
          <h2 class="text-lg font-semibold text-white mb-2">Proveedores Disponibles</h2>
          <div class="bg-slate-700 rounded-lg p-4">
            <template v-for="(provider, index) in availableProviders">
              <div class="flex items-center p-2 bg-slate-600 rounded">
                <span class="w-5 h-5 flex-shrink-0">
                  <svg class="w-4 h-4 text-green-500" viewBox="0 0 24 24" v-if="provider === aiConfig.primary_provider"><path fill="currentColor" d="M9 16l-5-5 1.41-1.41L12 12.59l7-7 1.41 1.41L12 15.41z"/></svg>
                  <svg class="w-4 h-4 text-slate-400" viewBox="0 0 24 24" v-else><path fill="currentColor" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-9 14l-5-5 1.41-1.41L10 14.17l7-7 1.41 1.41L10 18.34z"/></svg>
                </span>
                <span class="flex-1">{{ provider }}</span>
                <span v-if="provider === aiConfig.primary_provider" class="text-green-500 font-medium">(Actualmente activo)</span>
              </div>
            </template>
          </div>
        </div>

        <!-- Fallback Chain -->
        <div>
          <h2 class="text-lg font-semibold text-white mb-2">Cadena de Fallback (Orden de Prioridad)</h2>
          <div class="bg-slate-700 rounded-lg p-4">
            <p class="text-sm text-slate-400 mb-2">
              Si el proveedor activo falla, Igris probará los siguientes en este orden:
            </p>
            <div class="space-y-2">
              <template v-for="(provider, index) in aiConfig.fallback_chain">
                <div class="flex items-center p-3 bg-slate-600 rounded-lg">
                  <div class="flex items-center w-10">
                    <span class="text-xl font-bold text-blue-400">{{ index + 1 }}</span>
                  </div>
                  <div class="flex-1 flex items-center">
                    <span class="w-5 h-5 flex-shrink-0 mr-3">
                      <svg class="w-4 h-4" viewBox="0 0 24 24" :class="{ 'text-green-500': provider === aiConfig.primary_provider, 'text-blue-400': provider !== aiConfig.primary_provider }">
                        <path v-if="provider === aiConfig.primary_provider" fill="currentColor" d="M9 16l-5-5 1.41-1.41L12 12.59l7-7 1.41 1.41L12 15.41z"/>
                        <path v-else fill="currentColor" d="M12 2L15 6l3 3h-5l3 5L12 14l-5-5h-5l3-3-3-3z"/>
                      </svg>
                    </span>
                    <span>{{ provider }}</span>
                    <span v-if="provider === aiConfig.primary_provider" class="ml-auto text-green-500 font-medium">→ ACTIVO</span>
                    <span v-else-if="index === 0" class="ml-auto text-yellow-500 font-medium">→ PRIMER FALLBACK</span>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- Edit Configuration -->
        <div v-if="!saving" class="bg-slate-700 rounded-lg p-6">
          <h2 class="text-lg font-semibold text-white mb-4">Editar Configuración</h2>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">Proveedor Activo</label>
              <div class="relative">
                <select v-model="editConfig.primary_provider" class="block w-full px-4 py-2 bg-slate-600 border border-slate-500 rounded text-white focus:outline-none focus:border-blue-500">
                  <option v-for="provider in availableProviders" :key="provider" :value="provider">
                    {{ provider }}
                  </option>
                </select>
              </div>
              <p class="text-xs text-slate-400 mt-1">
                Seleccione el proveedor que Igris intentará usar primero
              </p>
            </div>
            
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">Cadena de Fallback</label>
              <div class="space-y-2">
                <template v-for="(provider, index) in availableProviders">
                  <div class="flex items-center">
                    <input 
                      type="checkbox" 
                      :id="'fallback_' + provider"
                      :checked="editConfig.fallback_chain.includes(provider)"
                      @change="toggleFallback(provider)"
                      class="w-4 h-4 text-blue-600 bg-slate-600 border-slate-500 rounded focus:ring-blue-500"
                    />
                    <label :for="'fallback_' + provider" class="ml-2 block text-slate-300">
                      {{ provider }}
                    </label>
                  </div>
                </template>
              </div>
              <p class="text-xs text-slate-400 mt-1">
                Ordene los proveedores según la prioridad (el primero en la lista tiene mayor prioridad)<br>
                Marque los proveedores que deben incluirse en la cadena de fallback
              </p>
            </div>
          </div>
          
          <div class="mt-6">
            <button 
              @click="saveConfig"
              :disabled="saving"
              class="w-full bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {{ saving ? 'Guardando...' : 'Guardar Configuración' }}
            </button>
          </div>
        </div>

        <div v-if="saving" class="bg-slate-800 rounded-lg p-4">
          <div class="flex items-center gap-3">
            <svg class="w-5 h-5 text-blue-400 animate-spin" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
            </svg>
            <span class="text-blue-300">Guardando configuración...</span>
          </div>
        </div>

        <div v-if="saveSuccess" class="bg-green-900/50 border border-green-500 rounded-lg p-4 mt-4">
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5 text-green-400" viewBox="0 0 24 24"><path fill="currentColor" d="M9 16l-5-5 1.41-1.41L12 12.59l7-7 1.41 1.41L12 15.41z"/></svg>
            <span class="text-green-300">{{ saveSuccess }}</span>
          </div>
        </div>

        <div v-if="saveError" class="bg-red-900/50 border border-red-500 rounded-lg p-4 mt-4">
          <div class="flex items-center gap-2">
            <svg class="w-5 h-5 text-red-400" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2a10 10 0 100 20 20 10 10 0 000-20zm0-2a8 8 0 110 0 16 8 8 0 010-16z"/></svg>
            <span class="text-red-300">{{ saveError }}</span>
          </div>
        </div>

        <!-- STT/TTS Info -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h2 class="text-lg font-semibold text-white mb-2">Transcripción (STT)</h2>
            <div class="bg-slate-700 rounded-lg p-4">
              <div class="flex items-center">
                <svg class="w-5 h-5 text-blue-400 mr-2" viewBox="0 0 24 24"><path fill="currentColor" d="M12 15l2-6h4l-3 5 6-3-8 4-2-6z"/></svg>
                <span>{{ aiConfig.stt.provider }}</span>
              </div>
              <p class="text-sm text-slate-400 mt-1">Habilitado: {{ aiConfig.stt.enabled ? 'Sí' : 'No' }}</p>
            </div>
          </div>
          <div>
            <h2 class="text-lg font-semibold text-white mb-2">Síntesis de Voz (TTS)</h2>
            <div class="bg-slate-700 rounded-lg p-4">
              <div class="flex items-center">
                <svg class="w-5 h-5 text-blue-400 mr-2" viewBox="0 0 24 24"><path fill="currentColor" d="M12 14c1.66 0 2.99-1.34 3-3V5c0-1.1-.9-2-2-2h-4c-1.1 0-2 .9-2 2v4c0 1.66 1.34 3 3 3zm6 0h-1v3.5c0 .83-.67 1.5-1.5 1.5S14 18.33 14 17.5V14h-3v3.5c0 .83-.67 1.5-1.5 1.5S11 18.33 11 17.5V14H8v3c0 .83-.67 1.5-1.5 1.5S6 18.33 6 17.5v-1.5C6 11.34 7.34 10 9 10h4c1.66 0 3 1.34 3 3v4c0 2.21-1.79 4-4 4S8 21.21 6 19.21V16z"/></svg>
                <span>{{ aiConfig.tts.provider }}</span>
              </div>
              <p class="text-sm text-slate-400 mt-1">Habilitado: {{ aiConfig.tts.enabled ? 'Sí' : 'No' }}</p>
            </div>
          </div>
        </div>

        <!-- How to Change Configuration -->
        <div class="bg-slate-700 rounded-lg p-6">
          <h2 class="text-lg font-semibold text-white mb-4">Cómo Cambiar la Configuración Permanentemente</h2>
          <p class="text-sm text-slate-300 mb-4">
            Los cambios realizados arriba se guardan en la configuración local del sistema.
            Para hacer los cambios permanentes (que sobrevivan a reinicios), necesita actualizar las variables de entorno
            en su plataforma de despliegue (Coolify) y volver a desplegar la aplicación.
          </p>
          
          <div class="bg-slate-800 rounded-lg p-4 mb-4">
            <h3 class="text-font-semibold text-white mb-2">Variables de Entorno Necesarias:</h3>
            <div class="space-y-2 text-sm font-mono bg-slate-900/50 p-3 rounded">
              <div class="flex items-center">
                <span class="flex-shrink-0 text-blue-300">IGRIS_PROVIDER=</span>
                <span class="flex-1 whitespace-nowrap text-white">[groq|nemotron|openai|anthropic|local]</span>
              </div>
              <div class="flex items-center">
                <span class="flex-shrink-0 text-blue-300">IGRIS_FALLBACK_CHAIN=</span>
                <span class="flex-1 whitespace-nowrap text-white">[groq,nemotron,openai,anthropic,local]</span>
              </div>
              <div class="flex items-center">
                <span class="flex-shrink-0 text-blue-300">IGRIS_NEMOTRON_MODEL=</span>
                <span class="flex-1 whitespace-nowrap text-white">[nombre del modelo nemotron]</span>
              </div>
              <div class="flex items-center">
                <span class="flex-shrink-0 text-blue-300">NEMOTRON_API_KEY=</span>
                <span class="flex-1 whitespace-nowrap text-white">[tu clave API de NVIDIA]</span>
              </div>
              <div class="flex items-center">
                <span class="flex-shrink-0 text-blue-300">NEMOTRON_API_BASE=</span>
                <span class="flex-1 whitespace-nowrap text-white">[URL base de la API nemotron]</span>
              </div>
            </div>
          </div>

          <div class="bg-slate-800 rounded-lg p-4">
            <h3 class="text-font-semibold text-white mb-2">Ejemplo de Configuración para Nemotron 3 Super 120b:</h3>
            <div class="space-y-1 text-sm font-mono bg-slate-900/50 p-3 rounded">
              <div class="flex items-center">
                <span class="flex-shrink-0 text-blue-300">IGRIS_PROVIDER=</span>
                <span class="flex-1 whitespace-nowrap text-white">nemotron</span>
              </div>
              <div class="flex items-center">
                <span class="flex-shrink-0 text-blue-300">IGRIS_FALLBACK_CHAIN=</span>
                <span class="flex-1 whitespace-nowrap text-white">nemotron,groq,openai,anthropic,local</span>
              </div>
              <div class="flex items-center">
                <span class="flex-shrink-0 text-blue-300">IGRIS_NEMOTRON_MODEL=</span>
                <span class="flex-1 whitespace-nowrap text-white">nvidia/nemotron-3-super-120b-a12b</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Important Note -->
        <div class="bg-slate-900/50 rounded-lg p-4 mt-6">
          <h2 class="text-lg font-semibold text-white mb-2">⚠️ Nota Importante</h2>
          <p class="text-sm text-slate-300">
            Los cambios en la configuración de IA realizados en esta página se guardan inmediatamente 
            y serán utilizados por el backend en su próxima solicitud. Sin embargo, para que los cambios 
            sean permanentes y sobrevivan a reinicios completos del sistema, debe actualizar las variables 
            de entorno en Coolify y hacer un redeploy.
          </p>
          <p class="text-sm text-slate-300 mt-2">
            <strong>Para cambios permanentes:</strong> Actualice IGRIS_PROVIDER y IGRIS_FALLBACK_CHAIN en Coolify → Servicio → Variables de entorno → Redeploy
          </p>
        </div>
      </div>

      <div v-if="!loading && !error && !aiConfig" class="text-center py-12">
        <p class="text-slate-400">No se pudo cargar la configuración</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const loading = ref(true)
const error = ref(null)
const aiConfig = ref(null)
const editConfig = ref({
  primary_provider: '',
  fallback_chain: []
})
const saving = ref(false)
const saveSuccess = ref(null)
const saveError = ref(null)

// Available providers (should match what's in config.py)
const availableProviders = ['groq', 'nemotron', 'openai', 'anthropic', 'local']

const loadAIConfig = async () => {
  try {
    loading.value = true
    error.value = null
    const response = await api.get('/api/ai-config')
    if (response.data.status === 'ok') {
      aiConfig.value = {
        primary_provider: response.data.primary_provider,
        fallback_chain: [...response.data.fallback_chain], // Copy array
        stt: response.data.stt || { provider: 'local', enabled: true },
        tts: response.data.tts || { provider: 'local', enabled: true }
      }
      // Initialize edit config with current values
      editConfig.value = {
        primary_provider: aiConfig.value.primary_provider,
        fallback_chain: [...aiConfig.value.fallback_chain]
      }
    } else {
      error.value = response.data.message || 'Error desconocido al cargar configuración'
    }
  } catch (err) {
    console.error('Error loading AI config:', err)
    error.value = 'No se pudo conectar al servidor'
  } finally {
    loading.value = false
  }
}

const toggleFallback = (provider) => {
  const index = editConfig.value.fallback_chain.indexOf(provider)
  if (index === -1) {
    editConfig.value.fallback_chain.push(provider)
  } else {
    editConfig.value.fallback_chain.splice(index, 1)
  }
}

const saveConfig = async () => {
  if (!editConfig.value.primary_provider) {
    saveError.value = 'Por favor seleccione un proveedor activo'
    return
  }
  
  if (editConfig.value.fallback_chain.length === 0) {
    saveError.value = 'La cadena de fallback debe tener al menos un proveedor'
    return
  }
  
  try {
    saving.value = true
    saveSuccess.value = null
    saveError.value = null
    
    const response = await api.put('/api/ai-config', {
      primary_provider: editConfig.value.primary_provider,
      fallback_chain: editConfig.value.fallback_chain
    })
    
    if (response.data.status === 'ok') {
      saveSuccess.value = response.data.message || 'Configuración guardada correctamente'
      // Update the displayed config
      aiConfig.value.primary_provider = editConfig.value.primary_provider
      aiConfig.value.fallback_chain = [...editConfig.value.fallback_chain]
    } else {
      saveError.value = response.data.message || 'Error al guardar la configuración'
    }
  } catch (err) {
    console.error('Error saving AI config:', err)
    saveError.value = 'No se pudo conectar al servidor'
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadAIConfig()
})
</script>

<style scoped>
</style>
