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
          <svg class="w-5 h-5 text-red-400" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2a10 10 0 100 20 10 10 0 000-20zm0-2a8 8 0 110 16 8 8 0 010-16z"/></svg>
          <span class="text-red-300">{{ error }}</span>
        </div>
      </div>

      <div v-if="configData" class="bg-slate-800 rounded-lg p-6 space-y-6">
        <!-- Active Provider -->
        <div>
          <h2 class="text-lg font-semibold text-white mb-2">Proveedor Activo</h2>
          <div class="bg-slate-700 rounded-lg p-4">
            <p class="text-blue-300">{{ configData.active_provider }}</p>
          </div>
        </div>

        <!-- Available Providers -->
        <div>
          <h2 class="text-lg font-semibold text-white mb-2">Proveedores Disponibles</h2>
          <div class="bg-slate-700 rounded-lg p-4 space-y-2">
            <template v-for="(provider, index) in configData.available_providers">
              <div class="flex items-center justify-between p-2 bg-slate-600 rounded">
                <span>{{ provider }}</span>
                <span v-if="provider === configData.active_provider" class="text-green-500 font-medium">(Activo)</span>
              </div>
            </template>
          </div>
        </div>

        <!-- Fallback Chain -->
        <div>
          <h2 class="text-lg font-semibold text-white mb-2">Cadena de Fallback</h2>
          <div class="bg-slate-700 rounded-lg p-4 space-y-2">
            <template v-for="(provider, index) in configData.fallback_chain">
              <div class="flex items-center p-2 bg-slate-600 rounded">
                <span>{{ index + 1 }}.</span>
                <span class="flex-1">{{ provider }}</span>
                <span v-if="provider === configData.active_provider" class="text-green-500">→ Activo</span>
              </div>
            </template>
          </div>
        </div>

        <!-- STT/TTS Info -->
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <h2 class="text-lg font-semibold text-white mb-2">Transcripción (STT)</h2>
            <div class="bg-slate-700 rounded-lg p-4">
              <p class="text-blue-300">{{ configData.stt.provider }}</p>
              <p class="text-sm text-slate-400">Habilitado: {{ configData.stt.enabled ? 'Sí' : 'No' }}</p>
            </div>
          </div>
          <div>
            <h2 class="text-lg font-semibold text-white mb-2">Síntesis de Voz (TTS)</h2>
            <div class="bg-slate-700 rounded-lg p-4">
              <p class="text-blue-300">{{ configData.tts.provider }}</p>
              <p class="text-sm text-slate-400">Habilitado: {{ configData.tts.enabled ? 'Sí' : 'No' }}</p>
            </div>
          </div>
        </div>

        <!-- Note -->
        <div class="bg-slate-700 rounded-lg p-4">
          <h2 class="text-lg font-semibold text-white mb-2">Nota Importante</h2>
          <p class="text-sm text-slate-300">
            La configuración de proveedores de IA se administra mediante variables de entorno en el servidor.
            Para cambiar el proveedor activo, modelo o claves de API, necesita actualizar las variables de entorno
            en su plataforma de despliegue (Coolify) y volver a desplegar la aplicación.
          </p>
          <p class="text-sm text-slate-300 mt-2">
            Las variables de entorno relevantes incluyen: <br>
            • IGRIS_PROVIDER (groq, nemotron, openai, anthropic, local)<br>
            • NEMOTRON_API_KEY, NEMOTRON_API_BASE<br>
            • GROQ_API_KEY, IGRIS_GROQ_MODEL<br>
            • OPENAI_API_KEY, IGRIS_OPENAI_MODEL<br>
            • ANTHROPIC_API_KEY, IGRIS_ANTHROPIC_MODEL<br>
            • IGRIS_STT_PROVIDER, IGRIS_TTS_PROVIDER
          </p>
        </div>
      </div>

      <div v-if="!loading && !error && !configData" class="text-center py-12">
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
const configData = ref(null)

const loadConfig = async () => {
  try {
    loading.value = true
    error.value = null
    const response = await api.get('/status')
    if (response.data.status === 'ok') {
      configData.value = response.data
    } else {
      error.value = response.data.message || 'Error desconocido al cargar configuración'
    }
  } catch (err) {
    console.error('Error loading config:', err)
    error.value = 'No se pudo conectar al servidor'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
</style>