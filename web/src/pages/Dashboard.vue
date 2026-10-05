<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
    <!-- Header -->
    <header class="bg-slate-800 border-b border-slate-700 sticky top-0 z-10">
      <div class="max-w-2xl mx-auto px-6 py-4 flex justify-between items-center">
        <div class="flex items-center gap-3">
          <h1 class="text-2xl font-bold text-white">💬 Chat con Iris</h1>
        </div>
      </div>
    </header>

    <!-- Content -->
    <div class="max-w-2xl mx-auto px-6 py-8 flex flex-col h-[calc(100%-160px)]">
      <!-- Chat Messages -->
      <div class="bg-slate-800 rounded-lg p-4 flex-1 overflow-y-auto mb-4">
        <div v-for="(msg, i) in chatMessages" :key="i" class="mb-2 text-sm">
          <span :class="msg.from === 'user' ? 'text-blue-300' : 'text-green-300'">{{ msg.from }}:</span>
          <span class="text-white">{{ msg.text }}</span>
        </div>
      </div>
      
      <!-- Input Area -->
      <div class="flex gap-2">
        <input 
          v-model="chatInput" 
          @keyup.enter="sendChat" 
          type="text" 
          placeholder="Escribe un mensaje a Iris..."
          class="flex-1 px-4 py-2 bg-slate-600 border border-slate-500 rounded text-white focus:outline-none focus:border-blue-500"
        />
        <button 
          @click="sendChat"
          class="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded transition"
        >
          Enviar
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import api from '../api'

const chatInput = ref('')
const chatMessages = ref([])

const sendChat = async () => {
  if (!chatInput.value.trim()) return
  
  // Add user message
  chatMessages.value.push({ from: 'user', text: chatInput.value })
  const msg = chatInput.value
  chatInput.value = ''
  
  try {
    const response = await api.post('/api/chat', { text: msg })
    if (response.data.status === 'ok') {
      chatMessages.value.push({ from: 'iris', text: response.data.reply })
    } else {
      chatMessages.value.push({
        from: 'iris',
        text: `Error del servidor: ${response.data.message || 'desconocido'}`
      })
    }
  } catch (err) {
    console.error('Error en chat HTTP:', err)
    chatMessages.value.push({
      from: 'iris',
      text: 'No se pudo conectar al servidor'
    })
  }
  
  // Scroll to bottom
  nextTick(() => {
    const chatContainer = document.querySelector('.flex-1.overflow-y-auto')
    if (chatContainer) {
      chatContainer.scrollTop = chatContainer.scrollHeight
    }
  })
}
</script>