<template>
  <div class="flex flex-col">
    <div class="flex-1 px-6 pb-6">
      <!-- Chat Messages -->
      <div
        ref="chatBox"
        class="bg-slate-800 rounded-lg p-4 mb-4 overflow-y-auto"
        style="min-height: 120px; max-height: 38vh"
      >
        <div v-for="(msg, i) in chatMessages" :key="i" class="mb-2 text-sm flex items-start">
          <span :class="msg.from === 'user' ? 'text-blue-300' : 'text-green-300'">{{ msg.from }}:</span>
          <span class="text-white ml-2">{{ msg.text }}</span>
          <!-- Botón de altavoz solo para mensajes de Igris -->
          <button
            v-if="msg.from === 'igris'"
            @click.stop="playIrisResponse(msg.text, i)"
            :disabled="isPlayingTTS[i]"
            class="ml-2 p-1 rounded hover:bg-slate-600 transition-opacity opacity-70"
            title="Reproducir respuesta"
            aria-label="Reproducir respuesta"
          >
            <svg v-if="!isPlayingTTS[i]" class="w-4 h-4 text-slate-400" viewBox="0 0 24 24">
              <path
                fill="currentColor"
                d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"
              />
            </svg>
            <svg v-else class="w-4 h-4 animate-spin text-slate-400" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="40 20" />
            </svg>
          </button>
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

        <!-- Micrófono: una frase -->
        <button
          @click="startVoiceInput"
          :disabled="isListening || isBusy || handsFree"
          class="flex-0 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded transition disabled:opacity-50 disabled:cursor-not-allowed"
          title="Hablar con Iris (una frase)"
        >
          <svg v-if="!isListening" class="w-5 h-5" viewBox="0 0 24 24">
            <path
              fill="currentColor"
              d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z"
            />
          </svg>
          <svg v-else class="w-5 h-5 animate-spin" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="40 20" />
          </svg>
        </button>

        <!-- Manos libres: escucha continua -->
        <button
          @click="toggleHandsFree"
          :class="handsFree ? 'bg-violet-600 hover:bg-violet-700 ring-2 ring-violet-300' : 'bg-slate-600 hover:bg-slate-500'"
          class="px-4 py-2 text-white rounded transition"
          :title="handsFree ? 'Desactivar manos libres' : 'Activar manos libres: solo háblale'"
        >
          {{ handsFree ? '🎧 Manos libres: ON' : '🎧 Manos libres' }}
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
import { ref, nextTick, onBeforeUnmount } from 'vue'
import api from '../api'
import { igris, setIgrisState } from '../composables/useIgris'

const chatInput = ref('')
const chatMessages = ref([])
const chatBox = ref(null)
const isListening = ref(false)
const isBusy = ref(false) // true mientras Igris piensa o habla
const handsFree = ref(false)
const isPlayingTTS = ref([])

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const scrollToBottom = () => {
  nextTick(() => {
    if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight
  })
}

/* ───────────── Medidor de volumen de la voz de Igris ───────────── */
let audioCtx = null
let levelRaf = 0

function startLevelMeter(audio) {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)()
    if (audioCtx.state === 'suspended') audioCtx.resume()
    const src = audioCtx.createMediaElementSource(audio)
    const analyser = audioCtx.createAnalyser()
    analyser.fftSize = 512
    src.connect(analyser)
    analyser.connect(audioCtx.destination)
    const buf = new Uint8Array(analyser.fftSize)
    const tick = () => {
      analyser.getByteTimeDomainData(buf)
      let sum = 0
      for (let i = 0; i < buf.length; i++) {
        const v = (buf[i] - 128) / 128
        sum += v * v
      }
      igris.level = Math.min(1, Math.sqrt(sum / buf.length) * 4)
      levelRaf = requestAnimationFrame(tick)
    }
    tick()
  } catch (e) {
    // Si falla, el avatar simula el volumen (level = -1)
    igris.level = -1
  }
}

function stopLevelMeter() {
  cancelAnimationFrame(levelRaf)
  igris.level = -1
}

/* ───────────── Voz de Igris (TTS) ───────────── */
let currentAudio = null

const playIrisResponse = async (text, index) => {
  if (!text || text.trim().length === 0) return

  const marking = index !== undefined && index !== null
  if (marking) isPlayingTTS.value[index] = true
  setIgrisState('thinking')

  let audioUrl = null
  try {
    const response = await api.post('/api/tts', { text }, { responseType: 'arraybuffer' })
    if (!response.data) return

    const audioBlob = new Blob([response.data], { type: 'audio/mpeg' })
    audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)
    currentAudio = audio

    // Espera a que termine de sonar
    await new Promise((resolve) => {
      audio.onplay = () => {
        setIgrisState('speaking')
        startLevelMeter(audio)
      }
      audio.onended = resolve
      audio.onerror = resolve
      audio.play().catch((err) => {
        console.error('Error playing audio:', err)
        resolve()
      })
    })
  } catch (err) {
    console.error('Error fetching TTS:', err)
  } finally {
    stopLevelMeter()
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    currentAudio = null
    if (marking) isPlayingTTS.value[index] = false
    setIgrisState('idle')
  }
}

const stopSpeaking = () => {
  if (currentAudio) {
    currentAudio.pause()
    if (currentAudio.onended) currentAudio.onended()
  }
}

/* ───────────── Enviar mensaje al backend ───────────── */
const sendMessage = async (raw) => {
  const msg = (raw || '').trim()
  if (!msg) return

  isBusy.value = true
  chatMessages.value.push({ from: 'user', text: msg })
  scrollToBottom()
  setIgrisState('thinking')

  try {
    const response = await api.post('/api/chat', { text: msg })
    if (response.data.status === 'ok') {
      chatMessages.value.push({ from: 'igris', text: response.data.reply })
      scrollToBottom()
      await playIrisResponse(response.data.reply, chatMessages.value.length - 1)
    } else {
      chatMessages.value.push({
        from: 'igris',
        text: `Error del servidor: ${response.data.message || 'desconocido'}`,
      })
      setIgrisState('idle')
    }
  } catch (err) {
    console.error('Error en chat HTTP:', err)
    chatMessages.value.push({ from: 'igris', text: 'No se pudo conectar al servidor' })
    setIgrisState('idle')
  } finally {
    isBusy.value = false
    scrollToBottom()
  }
}

const sendChat = async () => {
  const msg = chatInput.value
  chatInput.value = ''
  await sendMessage(msg)
}

/* ───────────── Reconocimiento de voz ───────────── */
let recognition = null

// Escucha una frase y devuelve { text, error }
function listenOnce() {
  return new Promise((resolve) => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) {
      resolve({ text: '', error: 'unsupported' })
      return
    }

    const rec = new SR()
    recognition = rec
    rec.lang = 'es-CO'
    rec.interimResults = false
    rec.maxAlternatives = 1

    let text = ''
    let error = null

    rec.onresult = (event) => {
      const parts = []
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) parts.push(event.results[i][0].transcript)
      }
      if (parts.length) text = (text + ' ' + parts.join(' ')).trim()
    }
    rec.onerror = (event) => {
      error = event.error
    }
    rec.onend = () => {
      recognition = null
      isListening.value = false
      resolve({ text, error })
    }

    try {
      isListening.value = true
      setIgrisState('listening')
      rec.start()
    } catch (err) {
      console.error('Error starting recognition:', err)
      recognition = null
      isListening.value = false
      setIgrisState('idle')
      resolve({ text: '', error: 'start-failed' })
    }
  })
}

// Devuelve true si el error impide seguir escuchando
function reportVoiceError(error) {
  if (!error || error === 'no-speech' || error === 'aborted') return false
  if (error === 'unsupported') {
    alert('Lo siento, tu navegador no soporta la entrada de voz. Por favor usa Chrome o Edge.')
  } else if (error === 'not-allowed' || error === 'service-not-allowed') {
    alert('Permiso de micrófono denegado. Permite el acceso al micrófono en la configuración de tu navegador.')
  } else if (error === 'audio-capture') {
    alert('No se pudo acceder al micrófono. Verifica que esté conectado y funcionando.')
  } else if (error === 'start-failed') {
    alert('No se pudo iniciar el reconocimiento de voz. Verifica tu micrófono y permisos.')
  } else {
    alert(`Error de reconocimiento de voz: ${error}`)
  }
  return true
}

// Botón del micrófono: una sola frase
const startVoiceInput = async () => {
  if (isListening.value || isBusy.value || handsFree.value) return
  const { text, error } = await listenOnce()
  reportVoiceError(error)
  if (text) await sendMessage(text)
  else setIgrisState('idle')
}

/* ───────────── Modo manos libres ───────────── */
let loopRunning = false

const runHandsFree = async () => {
  if (loopRunning) return
  loopRunning = true
  try {
    while (handsFree.value) {
      // Mientras Igris piensa o habla no se escucha (evita que se oiga a sí mismo)
      if (isBusy.value) {
        await sleep(200)
        continue
      }
      const { text, error } = await listenOnce()
      if (!handsFree.value) break
      if (reportVoiceError(error)) {
        handsFree.value = false
        break
      }
      if (text) await sendMessage(text)
      else await sleep(300)
    }
  } finally {
    loopRunning = false
    if (!isBusy.value) setIgrisState('idle')
  }
}

const toggleHandsFree = () => {
  if (handsFree.value) {
    handsFree.value = false
    if (recognition) recognition.abort()
    return
  }
  handsFree.value = true
  runHandsFree()
}

onBeforeUnmount(() => {
  handsFree.value = false
  if (recognition) recognition.abort()
  stopSpeaking()
  stopLevelMeter()
  setIgrisState('idle')
})
</script>
