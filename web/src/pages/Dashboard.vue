<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex flex-col">
    <!-- Content -->
    <div class="flex-1 px-6">
      <!-- Chat Messages -->
      <div class="bg-slate-800 rounded-lg p-4 mb-4 flex-1 overflow-y-auto">
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
          @click="startVoiceInput"
          :disabled="isListening"
          class="flex-0 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded transition disabled:opacity-50 disabled:cursor-not-allowed"
          title="Hablar con Iris"
        >
          <svg v-if="!isListening" class="w-5 h-5" viewBox="0 0 24 24"><path fill="currentColor" d="M12 15c3.31 0 6-2.69 6-6h-4c0 2.21-1.79 4-4 4s-4-1.79-4-4h-4c0 3.31 2.69 6 6 6zm7.18-9.81l-1.42-1.42C15.56 3.9 13.63 3 12 3c-3.31 0-6 2.69-6 6H1c0-3.87 3.13-7 7-7s7 3.13 7 7c0 2.76-1.74 5.12-4.24 6.18l1.42 1.42c1.9-1.24 3.04-3.03 3.04-5.08z"/></svg>
          <svg v-else class="w-5 h-5 animate-spin" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2a10 10 0 100 20 20 20 10 10 0 00-20-20zm0 2a8 8 0 110 0 16 8 8 0 010-16z"/></svg>
        </button>
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
const isListening = ref(false)

const sendChat = async () => {
  if (!chatInput.value.trim()) return
  
  // Add user message
  chatMessages.value.push({ from: 'user', text: chatInput.value })
  const msg = chatInput.value
  chatInput.value = ''
  
  try {
    const response = await api.post('/api/chat', { text: msg })
    if (response.data.status === 'ok') {
      chatMessages.value.push({ from: 'igris', text: response.data.reply })
    } else {
      chatMessages.value.push({
        from: 'igris',
        text: `Error del servidor: ${response.data.message || 'desconocido'}`
      })
    }
  } catch (err) {
    console.error('Error en chat HTTP:', err)
    chatMessages.value.push({
      from: 'igris',
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

const startVoiceInput = async () => {
  // Check if browser supports Speech Recognition
  if (!('SpeechRecognition' in window) && !('webkitSpeechRecognition' in window)) {
    alert('Lo siento, tu navegador no soporta la entrada de voz. Por favor usa Chrome o Edge para esta característica.')
    return
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
  const recognition = new SpeechRecognition()
  
  // Configure for Spanish
  recognition.lang = 'es-ES'
  recognition.interimResults = false
  recognition.maxAlternatives = 1

  isListening.value = true

  // Flag to ensure we only process one result per session
  let resultProcessed = false
  let finalTranscript = ''

  recognition.onresult = (event) => {
    // Prevent processing multiple results
    if (resultProcessed) return
    
    try {
      // Get the transcript from the most recent result
      const transcript = event.results[event.resultIndex][0].transcript
      
      // Only update if we have meaningful content
      if (transcript.trim().length > 0) {
        finalTranscript = transcript.trim()
      }
    } catch (err) {
      console.error('Error processing voice result:', err)
    }
  }

  recognition.onend = () => {
    isListening.value = false
    // Process the final result when recognition ends
    if (!resultProcessed && finalTranscript.trim().length > 0) {
      resultProcessed = true
      try {
        // Send the captured transcript
        chatInput.value = finalTranscript
        sendChat()
      } catch (err) {
        console.error('Error sending chat message:', err)
      }
    }
    // Reset for next attempt
    resultProcessed = false
    finalTranscript = ''
  }

  recognition.onerror = (event) => {
    console.error('Speech recognition error:', event.error)
    isListening.value = false
    resultProcessed = false
    finalTranscript = ''
    
    if (event.error === 'not-allowed') {
      alert('Permiso de micrófono denegado. Por favor permite el acceso al micrófono en la configuración de tu navegador.')
    } else if (event.error === 'audio-capture') {
      alert('No se pudo acceder al micrófono. Por favor verifica que esté conectado y funcionando.')
    } else {
      alert(`Error de reconocimiento de voz: ${event.error}`)
    }
  }

  try {
    recognition.start()
  } catch (err) {
    console.error('Error starting recognition:', err)
    isListening.value = false
    alert('No se pudo iniciar el reconocimiento de voz. Por favor verifica tu micrófono y permisos.')
  }
}
</script>