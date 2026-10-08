<!--
  UserChat.vue — Chat de Igris para los usuarios del área /u.

  Es la misma experiencia que el chat del administrador (voz manos libres,
  respuestas habladas, historial), pero apuntando a las rutas /api/user/* con
  el token del usuario en lugar de la clave única.

  Lo que NO tiene, a propósito: navegación al panel, ni a /config, ni ninguna
  ruta de administración. Un usuario solo ve su chat.
-->
<template>
  <div class="dash">
    <IgrisHero />

    <InstallHint />

    <!-- Avisos -->
    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-else-if="needsTap" class="notice soft">Toca la pantalla para activar el sonido</div>

    <!-- Barra superior: usuario y salir -->
    <div class="topbar">
      <span class="who">👤 {{ username }}</span>
      <button type="button" class="out" @click="logout">Salir</button>
    </div>

    <div class="bottom">
      <!-- Historial -->
      <div v-show="chatMessages.length" ref="chatBox" class="history">
        <div v-for="(msg, i) in chatMessages" :key="i" class="msg">
          <span :class="['from', msg.from === 'user' ? 'user' : 'igris']">{{ msg.from }}:</span>
          <span class="text">{{ msg.text }}</span>
          <button
            v-if="msg.from === 'igris'"
            @click.stop="playIgrisResponse(msg.text, i)"
            :disabled="isPlayingTTS[i]"
            class="speaker"
            title="Reproducir respuesta"
            aria-label="Reproducir respuesta"
          >
            <svg v-if="!isPlayingTTS[i]" viewBox="0 0 24 24" width="16" height="16">
              <path
                fill="currentColor"
                d="M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 7.97v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"
              />
            </svg>
            <svg v-else class="spin" viewBox="0 0 24 24" width="16" height="16">
              <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="3" stroke-dasharray="40 20" />
            </svg>
          </button>
        </div>
      </div>

      <!-- Cuadro de texto: aparece al pulsar "Enviar" -->
      <div v-if="showInput" class="composer">
        <input
          ref="textInput"
          v-model="chatInput"
          @keyup.enter="sendChat"
          @keyup.esc="closeInput"
          type="text"
          placeholder="Escribe un mensaje a Igris..."
        />
        <button class="btn primary" :disabled="isBusy || !chatInput.trim()" @click="sendChat">Enviar</button>
        <button class="btn ghost" @click="closeInput" title="Cerrar" aria-label="Cerrar">✕</button>
      </div>

      <!-- Controles -->
      <div class="controls">
        <button class="pill" :class="{ on: handsFree }" @click="toggleHandsFree">
          <span class="dot" :class="{ live: isListening }"></span>
          {{ handsFree ? 'Manos libres: activo' : 'Manos libres: pausado' }}
        </button>
        <button v-if="!showInput" class="pill" @click="openInput">✉️ Enviar</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import userApi, { getUser, clearSession } from '../userApi'
import { igris, setIgrisState } from '../composables/useIgris'
import IgrisHero from '../components/IgrisHero.vue'
import InstallHint from '../components/InstallHint.vue'

const router = useRouter()

const username = computed(() => getUser()?.username || 'usuario')

const chatInput = ref('')
const chatMessages = ref([])
const chatBox = ref(null)
const textInput = ref(null)
const showInput = ref(false)
const isListening = ref(false)
const isBusy = ref(false)
const handsFree = ref(true)
const isPlayingTTS = ref([])
const notice = ref('')
const needsTap = ref(
  typeof navigator !== 'undefined' && !(navigator.userActivation && navigator.userActivation.hasBeenActive),
)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// Identificador de esta conversación. El servidor lo prefija con el id del
// usuario, así que aunque dos personas usaran el mismo valor nunca compartirían
// historial. Al recargar empieza una conversación nueva.
const sessionId = crypto.randomUUID
  ? crypto.randomUUID()
  : Date.now().toString(36) + Math.random().toString(36).slice(2)

let noticeTimer = 0
const setNotice = (msg, ms = 9000) => {
  notice.value = msg
  clearTimeout(noticeTimer)
  if (msg) noticeTimer = setTimeout(() => (notice.value = ''), ms)
}

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

  const wasBusy = isBusy.value
  isBusy.value = true
  if (recognition) recognition.abort()
  setIgrisState('thinking')

  let audioUrl = null
  try {
    const response = await userApi.post('/api/user/tts', { text }, { responseType: 'arraybuffer' })
    if (!response.data) return

    const audioBlob = new Blob([response.data], { type: 'audio/mpeg' })
    audioUrl = URL.createObjectURL(audioBlob)
    const audio = new Audio(audioUrl)
    currentAudio = audio

    await new Promise((resolve) => {
      audio.onplay = () => {
        needsTap.value = false
        setIgrisState('speaking')
        startLevelMeter(audio)
      }
      audio.onended = resolve
      audio.onerror = resolve
      audio.play().catch((err) => {
        console.error('Error playing audio:', err)
        if (err && err.name === 'NotAllowedError') needsTap.value = true
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
    if (!wasBusy) isBusy.value = false
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
  if (!msg || isBusy.value) return

  isBusy.value = true
  if (recognition) recognition.abort()
  chatMessages.value.push({ from: 'user', text: msg })
  scrollToBottom()
  setIgrisState('thinking')

  try {
    const response = await userApi.post('/api/user/chat', { text: msg, session_id: sessionId })
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
    // Si el token caducó, userApi ya avisó al router y estamos yendo a /u/login
    if (err.response?.status !== 401) {
      chatMessages.value.push({ from: 'igris', text: 'No se pudo conectar al servidor' })
    }
    setIgrisState('idle')
  } finally {
    isBusy.value = false
    scrollToBottom()
  }
}

/* ───────────── Cuadro de texto ───────────── */
const openInput = () => {
  showInput.value = true
  if (recognition) recognition.abort()
  nextTick(() => textInput.value && textInput.value.focus())
}

const closeInput = () => {
  showInput.value = false
  chatInput.value = ''
}

const sendChat = async () => {
  const msg = chatInput.value.trim()
  if (!msg || isBusy.value) return
  chatInput.value = ''
  showInput.value = false
  await sendMessage(msg)
}

/* ───────────── Reconocimiento de voz ───────────── */
let recognition = null

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
      if (recognition === rec) recognition = null
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

const FATAL = ['unsupported', 'not-allowed', 'service-not-allowed', 'audio-capture', 'start-failed']

function reportVoiceError(error) {
  if (!error || error === 'no-speech' || error === 'aborted') return false
  const blocked =
    'Micrófono bloqueado. Permítelo en el candado de la barra de direcciones y pulsa "Manos libres".'
  const msgs = {
    unsupported: 'Tu navegador no soporta la voz. Usa Chrome o Edge.',
    'not-allowed': blocked,
    'service-not-allowed': blocked,
    'audio-capture': 'No se detecta el micrófono. Revisa que esté conectado.',
    'start-failed': 'No se pudo iniciar el micrófono. Pulsa "Manos libres" para reintentar.',
  }
  setNotice(msgs[error] || `Error de voz: ${error}`)
  return FATAL.includes(error)
}

/* ───────────── Modo manos libres (siempre activo) ───────────── */
let loopRunning = false

const runHandsFree = async () => {
  if (loopRunning) return
  loopRunning = true
  try {
    while (handsFree.value) {
      if (isBusy.value || showInput.value) {
        if (showInput.value && !isBusy.value && igris.state === 'listening') setIgrisState('idle')
        await sleep(200)
        continue
      }
      const { text, error } = await listenOnce()
      if (!handsFree.value) break
      if (reportVoiceError(error)) {
        handsFree.value = false
        break
      }
      if (text) {
        await sendMessage(text)
      } else if (error && error !== 'no-speech' && error !== 'aborted') {
        await sleep(2000)
      } else {
        await sleep(300)
      }
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
  setNotice('')
  handsFree.value = true
  runHandsFree()
}

/* ───────────── Salir ───────────── */
function logout() {
  clearSession()
  router.replace('/u/login')
}

/* ───────────── Ciclo de vida ───────────── */
const unlock = () => {
  needsTap.value = false
  if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume()
}

onMounted(() => {
  window.addEventListener('pointerdown', unlock, { once: true })
  window.addEventListener('keydown', unlock, { once: true })
  runHandsFree()
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', unlock)
  window.removeEventListener('keydown', unlock)
  clearTimeout(noticeTimer)
  handsFree.value = false
  if (recognition) recognition.abort()
  stopSpeaking()
  stopLevelMeter()
  setIgrisState('idle')
})
</script>

<style scoped>
.topbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 11;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(6px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}
.who {
  font-size: 0.85rem;
  color: #cbd5e1;
}
.out {
  padding: 6px 14px;
  border: 0;
  border-radius: 999px;
  background: rgba(51, 65, 85, 0.8);
  color: #e2e8f0;
  font-size: 0.8rem;
  cursor: pointer;
}
.out:hover {
  background: rgba(71, 85, 105, 0.9);
}

.bottom {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: 0 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.notice {
  position: fixed;
  top: 120px;
  left: 50%;
  transform: translateX(-50%);
  max-width: 90vw;
  padding: 8px 16px;
  border-radius: 999px;
  font-size: 0.85rem;
  color: #fff;
  background: rgba(185, 28, 28, 0.85);
  backdrop-filter: blur(6px);
  text-align: center;
  z-index: 12;
}
.notice.soft {
  background: rgba(30, 41, 59, 0.8);
  color: #cbd5e1;
}

.history {
  max-height: 26vh;
  overflow-y: auto;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.15);
  background: rgba(2, 6, 23, 0.55);
  backdrop-filter: blur(8px);
  font-size: 0.9rem;
  color: #fff;
}
.msg {
  display: flex;
  align-items: flex-start;
  margin-bottom: 6px;
}
.from {
  flex: none;
}
.from.user {
  color: #93c5fd;
}
.from.igris {
  color: #86efac;
}
.text {
  margin-left: 8px;
}
.speaker {
  flex: none;
  margin-left: 8px;
  padding: 2px 4px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  opacity: 0.75;
}
.speaker:hover:not(:disabled) {
  background: rgba(71, 85, 105, 0.7);
}
.spin {
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.composer {
  display: flex;
  gap: 8px;
}
.composer input {
  flex: 1;
  min-width: 0;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid #475569;
  background: rgba(30, 41, 59, 0.85);
  color: #fff;
  outline: none;
  font-size: 0.95rem;
}
.composer input:focus {
  border-color: #3b82f6;
}
.btn {
  padding: 10px 18px;
  border: 0;
  border-radius: 10px;
  color: #fff;
  cursor: pointer;
  font-size: 0.95rem;
}
.btn.primary {
  background: #2563eb;
}
.btn.primary:hover:not(:disabled) {
  background: #1d4ed8;
}
.btn.ghost {
  background: rgba(51, 65, 85, 0.8);
  padding: 10px 14px;
}
.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.controls {
  display: flex;
  justify-content: center;
  gap: 10px;
}
.pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 16px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.3);
  background: rgba(30, 41, 59, 0.75);
  backdrop-filter: blur(6px);
  color: #e2e8f0;
  font-size: 0.85rem;
  cursor: pointer;
}
.pill:hover {
  background: rgba(51, 65, 85, 0.85);
}
.pill.on {
  border-color: #8b5cf6;
  background: rgba(91, 33, 182, 0.55);
}
.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 8px;
  border-radius: 50%;
  background: #64748b;
}
.pill.on .dot {
  background: #a78bfa;
}
.dot.live {
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  50% {
    transform: scale(1.6);
    opacity: 0.6;
  }
}
</style>
