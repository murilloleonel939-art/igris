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
    <InstallHint />

    <!-- Avisos -->
    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-else-if="needsTap" class="notice soft">Toca la pantalla para activar el sonido</div>

    <!-- Panel de memoria personal y operativa -->
    <div v-if="memories.open" class="conn-backdrop" @click.self="memories.open = false">
      <div class="conn memory-panel">
        <h2>Mi memoria</h2>
        <p class="conn-note">Aquí puedes revisar y corregir lo que Igris recuerda de ti.</p>
        <p v-if="memories.error" class="conn-error">{{ memories.error }}</p>
        <p v-if="memories.loading" class="conn-note">Cargando…</p>
        <template v-else>
          <section v-for="group in memoryGroups" :key="group.kind">
            <div class="memory-heading">
              <h3>{{ group.label }}</h3>
              <button class="btn ghost small" @click="startMemory(group.kind)">Añadir</button>
            </div>
            <div v-if="!memories.items[group.kind].length" class="conn-note">No hay recuerdos todavía.</div>
            <div v-for="item in memories.items[group.kind]" :key="item.id" class="memory-item">
              <input v-if="memories.editing === item.id" v-model="memories.draft" maxlength="260" @keyup.enter="saveMemory(item)" />
              <span v-else>{{ item.content }}</span>
              <div class="memory-actions">
                <button v-if="memories.editing === item.id" class="btn primary small" @click="saveMemory(item)">Guardar</button>
                <button v-if="memories.editing === item.id" class="btn ghost small" @click="cancelMemory">Cancelar</button>
                <button v-else class="btn ghost small" @click="editMemory(item)">Editar</button>
                <button class="btn danger small" @click="deleteMemory(item)">Borrar</button>
              </div>
            </div>
          </section>
          <section v-if="memories.creating" class="memory-new">
            <h3>Nuevo recuerdo</h3>
            <select v-model="memories.newKind">
              <option value="personal">Personal</option>
              <option value="operational">Operativo</option>
            </select>
            <textarea v-model="memories.newContent" maxlength="260" placeholder="Escribe un recuerdo…" />
            <div class="conn-actions">
              <button class="btn primary" :disabled="!memories.newContent.trim()" @click="createMemory">Guardar</button>
              <button class="btn ghost" @click="cancelNewMemory">Cancelar</button>
            </div>
          </section>
        </template>
        <div class="conn-foot"><button class="btn ghost" @click="memories.open = false">Cerrar</button></div>
      </div>
    </div>

    <!-- Panel de conexiones: qué funciones tienes y qué te falta conectar -->
    <div v-if="conn.open" class="conn-backdrop" @click.self="conn.open = false">
      <div class="conn">
        <h2>Conexiones</h2>

        <p v-if="conn.loading" class="conn-note">Cargando…</p>
        <p v-else-if="conn.error" class="conn-error">{{ conn.error }}</p>

        <template v-else>
          <section>
            <h3>Lo que puedes pedirme</h3>
            <div class="chips">
              <span v-for="f in conn.features" :key="f" class="chip">{{ featureLabel(f) }}</span>
              <span v-if="!conn.features.length" class="conn-note">
                Todavía no tienes ninguna función. Pídeselas al administrador.
              </span>
            </div>
          </section>

          <section v-if="conn.google && conn.google.needs_google">
            <h3>Tu cuenta de Google</h3>
            <p v-if="conn.google.connected" class="conn-ok">
              Conectada: {{ conn.google.email || 'cuenta de Google' }}
            </p>
            <p v-if="conn.google.error" class="conn-error">
              Google dio un error con tu cuenta: {{ conn.google.error }}. Vuelve a conectarla.
            </p>
            <p v-if="!conn.google.app_configured" class="conn-note">
              El administrador todavía no ha configurado el acceso a Google en el servidor.
            </p>
            <template v-else>
              <p class="conn-note">
                Igris leerá tu correo y tu calendario con TU cuenta, no con la de nadie más.
                Nadie más ve tus datos.
              </p>
              <div class="conn-actions">
                <button class="btn primary" @click="connectGoogle">
                  {{ conn.google.connected ? 'Volver a conectar' : 'Conectar mi Google' }}
                </button>
                <button v-if="conn.google.connected" class="btn ghost" @click="disconnectGoogle">
                  Desconectar
                </button>
              </div>
            </template>
          </section>

          <section>
            <h3>Reconocimiento de voz</h3>
            <p class="conn-note">
              Igris te guiará paso a paso. En cada paso espera la indicación y habla durante la grabación.
            </p>
            <p v-if="voiceStepLabel" class="conn-note voice-step">{{ voiceStepLabel }}</p>
             <p v-if="voiceRegistered" class="conn-ok">Voz registrada.</p>
            <p v-if="voiceError" class="conn-error">{{ voiceError }}</p>
            <div class="conn-actions">
              <button class="btn primary" :disabled="voiceRecording" @click="registerVoice">
                {{ voiceRecording ? 'Grabando…' : (voiceRegistered ? 'Actualizar mi voz' : 'Registrar mi voz') }}
                </button>
                <button v-if="voiceRegistered && !voiceRecording" class="btn ghost" @click="deleteVoiceProfile">
                  Borrar grabaciones
                </button>
            </div>
          </section>

          <section v-if="conn.features.includes('reminders')">
            <h3>Tu Telegram</h3>
            <p v-if="conn.telegram.linked" class="conn-ok">
              Vinculado{{ conn.telegram.username ? ` (@${conn.telegram.username})` : '' }}.
              Tus recordatorios te llegan por ahí.
            </p>
            <template v-else>
              <p class="conn-note">
                Para recibir recordatorios hay que vincular tu Telegram: pide el código aquí y
                envíaselo al bot.
              </p>
              <div v-if="conn.telegramCode" class="conn-code">
                <p>Envía este mensaje al bot de Igris en Telegram:</p>
                <code>/start {{ conn.telegramCode }}</code>
                <p class="conn-note">
                  Caduca en {{ conn.telegramCodeMinutes }} minutos. Cuando lo envíes, pulsa
                  «Ya lo envié».
                </p>
              </div>
              <div class="conn-actions">
                <button class="btn primary" @click="requestTelegramCode">
                  {{ conn.telegramCode ? 'Generar otro código' : 'Vincular mi Telegram' }}
                </button>
                <button v-if="conn.telegramCode" class="btn ghost" @click="refreshConnections">
                  Ya lo envié
                </button>
              </div>
            </template>
            <button v-if="conn.telegram.linked" class="btn ghost" @click="unlinkTelegram">
              Desvincular
            </button>
          </section>

          <p class="conn-note">
            Los permisos los cambia el administrador; aquí solo conectas tus propias cuentas.
          </p>
        </template>

        <div class="conn-foot">
          <button class="btn ghost" @click="conn.open = false">Cerrar</button>
        </div>
      </div>
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
import { useRoute, useRouter } from 'vue-router'
import userApi, { getUser, clearSession, errorMessage } from '../userApi'
import { getKey } from '../api'
import { igris, setIgrisState } from '../composables/useIgris'
import IgrisHero from '../components/IgrisHero.vue'
import WorkspaceNav from '../components/WorkspaceNav.vue'
import InstallHint from '../components/InstallHint.vue'

const route = useRoute()
const router = useRouter()

const username = computed(() => getUser()?.username || 'usuario')
const adminUser = computed(() => !!getUser()?.is_admin || Boolean(getKey()))

const chatInput = ref('')
const chatMessages = ref([])
const chatBox = ref(null)
const textInput = ref(null)
const showInput = ref(false)
const isListening = ref(false)
const isBusy = ref(false)
const handsFree = ref(true)
const isPlayingTTS = ref([])
const voiceRegistered = ref(false)
const voiceRecording = ref(false)
const voiceError = ref('')
const voiceStepLabel = ref('')
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
  return new Promise(async (resolve) => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      resolve({ text: '', audio: null, error: 'unsupported' })
      return
    }

    let stream
    let recorder
    let rec = null
    const chunks = []
    let meterContext
    let meterSource
    let meterAnalyser
    let meterFrame
    let heardSpeech = false
    let speechStartedAt = 0
    let lastSpeechAt = 0
    let text = ''
    let error = null
    let settled = false
    let stopCapture = null
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      })
      meterContext = new (window.AudioContext || window.webkitAudioContext)()
      meterSource = meterContext.createMediaStreamSource(stream)
      meterAnalyser = meterContext.createAnalyser()
      meterAnalyser.fftSize = 512
      meterSource.connect(meterAnalyser)
      const samples = new Uint8Array(meterAnalyser.fftSize)
      const sample = () => {
        meterAnalyser.getByteTimeDomainData(samples)
        let sum = 0
        for (const value of samples) {
          const normalized = (value - 128) / 128
          sum += normalized * normalized
        }
        const rms = Math.sqrt(sum / samples.length)
        const now = Date.now()
        if (rms > 0.011) {
          heardSpeech = true
          if (!speechStartedAt) speechStartedAt = now
          lastSpeechAt = now
        }
        if (speechStartedAt && now - lastSpeechAt > 850 && now - speechStartedAt > 700) {
          stopCapture?.()
          return
        }
        if (!settled) meterFrame = requestAnimationFrame(sample)
      }
      sample()
      const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : undefined
      recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data)
      recorder.start()
    } catch (err) {
      resolve({ text: '', audio: null, error: 'not-allowed' })
      return
    }

    const finish = () => {
      if (settled) return
      settled = true
      if (meterFrame) cancelAnimationFrame(meterFrame)
      if (meterContext) meterContext.close()
      if (recognition === rec) recognition = null
      isListening.value = false
      stream.getTracks().forEach((track) => track.stop())
      const audio = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
      resolve({ text, audio: heardSpeech ? audio : null, error })
    }

    // Whisper del backend es la única fuente de transcripción. Chrome no
    // participa en el texto porque puede inventar palabras o cortar frases.
    stopCapture = () => {
      if (settled) return
      if (rec) { try { rec.abort() } catch (err) {} }
      if (recorder && recorder.state !== 'inactive') {
        recorder.addEventListener('stop', finish, { once: true })
        recorder.stop()
      } else finish()
    }
    isListening.value = true
    setIgrisState('listening')
    // El silencio termina una orden normal; cinco segundos siguen siendo el límite.
    setTimeout(() => stopCapture?.(), 5000)
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
      const { text, audio, error } = await listenOnce()
      if (!handsFree.value) break
      if (reportVoiceError(error)) {
        handsFree.value = false
        break
      }
      // SpeechRecognition puede no devolver texto aunque MediaRecorder sí haya
      // capturado la voz. El backend usa Whisper para transcribir el audio.
      if (audio) {
        const form = new FormData()
        form.append('audio', audio, 'voice.webm')
        form.append('session_id', sessionId)
        try {
          const response = await userApi.post('/api/user/voice-chat', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          if (response.data.status === 'ok') {
            chatMessages.value.push({ from: 'user', text: response.data.text })
            chatMessages.value.push({ from: 'igris', text: response.data.reply })
            scrollToBottom()
            await playIrisResponse(response.data.reply, chatMessages.value.length - 1)
          }
        } catch (err) {
          setNotice(err.response?.data?.detail || 'Voz no reconocida. Orden rechazada.')
        }
      } else if (error && error !== 'no-speech' && error !== 'aborted') {
        await sleep(5000)
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
  if (getKey()) router.replace('/acceso')
  else router.replace('/u/login')
}

/* ───────────── Conexiones (Google y Telegram) ─────────────
   Todo lo que aparece aquí lo decide el servidor: esta pantalla solo muestra
   qué funciones tiene el usuario y le deja conectar SUS cuentas. Los permisos
   no se pueden tocar desde aquí. */

const memories = ref({
  open: false,
  loading: false,
  error: '',
  items: { personal: [], operational: [] },
  editing: null,
  draft: '',
  creating: false,
  newKind: 'personal',
  newContent: '',
})

const memoryGroups = [
  { kind: 'personal', label: 'Memoria personal' },
  { kind: 'operational', label: 'Memoria operativa' },
]

async function refreshMemories() {
  memories.value.loading = true
  memories.value.error = ''
  try {
    const res = await userApi.get('/api/user/memories')
    memories.value.items = {
      personal: res.data?.personal || [],
      operational: res.data?.operational || [],
    }
  } catch (e) {
    memories.value.error = errorMessage(e, 'No se pudo cargar tu memoria')
  } finally {
    memories.value.loading = false
  }
}

function openMemories() {
  memories.value.open = true
  memories.value.creating = false
  memories.value.editing = null
  refreshMemories()
}

function startMemory(kind) {
  memories.value.creating = true
  memories.value.newKind = kind
  memories.value.newContent = ''
  memories.value.editing = null
}

function cancelNewMemory() {
  memories.value.creating = false
  memories.value.newContent = ''
}

function editMemory(item) {
  memories.value.editing = item.id
  memories.value.draft = item.content
  memories.value.creating = false
}

function cancelMemory() {
  memories.value.editing = null
  memories.value.draft = ''
}

async function createMemory() {
  const content = memories.value.newContent.trim()
  if (!content) return
  try {
    await userApi.post('/api/user/memories', { kind: memories.value.newKind, content })
    cancelNewMemory()
    await refreshMemories()
    setNotice('Recuerdo guardado.', 4000)
  } catch (e) {
    memories.value.error = errorMessage(e, 'No se pudo guardar el recuerdo')
  }
}

async function saveMemory(item) {
  const content = memories.value.draft.trim()
  if (!content) return
  try {
    await userApi.put(`/api/user/memories/${item.id}`, { content })
    cancelMemory()
    await refreshMemories()
    setNotice('Recuerdo actualizado.', 4000)
  } catch (e) {
    memories.value.error = errorMessage(e, 'No se pudo actualizar el recuerdo')
  }
}

async function deleteMemory(item) {
  if (!window.confirm('¿Borrar este recuerdo?')) return
  try {
    await userApi.delete(`/api/user/memories/${item.id}`)
    await refreshMemories()
    setNotice('Recuerdo borrado.', 4000)
  } catch (e) {
    memories.value.error = errorMessage(e, 'No se pudo borrar el recuerdo')
  }
}

const conn = ref({
  open: false,
  loading: false,
  error: '',
  features: [],
  google: null,
  telegram: { linked: false, username: null },
  telegramCode: '',
  telegramCodeMinutes: 15,
})

function featureLabel(key) {
  const nombres = {
    time: 'Hora y fecha',
    weather: 'Clima',
    email: 'Leer correo',
    calendar: 'Ver calendario',
    calendar_write: 'Agendar eventos',
    notes: 'Notas',
    reminders: 'Recordatorios',
  }
  return nombres[key] || key
}

async function refreshVoiceStatus() {
  try {
    const res = await userApi.get('/api/user/voice-profile')
    voiceRegistered.value = Boolean(res.data?.registered)
  } catch (e) {
    voiceError.value = errorMessage(e, 'No se pudo consultar el registro de voz')
  }
}

async function deleteVoiceProfile() {
  if (!window.confirm('¿Quieres borrar todas tus grabaciones de voz?')) return
  voiceError.value = ''
  try {
    await userApi.delete('/api/user/voice-profile')
    voiceRegistered.value = false
    voiceStepLabel.value = ''
    setNotice('Grabaciones de voz eliminadas.', 5000)
  } catch (e) {
    voiceError.value = errorMessage(e, 'No se pudieron borrar las grabaciones')
  }
}

async function recordVoiceSample() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : undefined
  const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
  const chunks = []
  recorder.ondataavailable = (event) => event.data.size && chunks.push(event.data)
  const finished = new Promise((resolve) => { recorder.onstop = resolve })
  recorder.start()
  await new Promise((resolve) => setTimeout(resolve, 3000))
  recorder.stop()
  await finished
  stream.getTracks().forEach((track) => track.stop())
  return new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
}

async function registerVoice() {
  voiceError.value = ''
  handsFree.value = false
  if (recognition) recognition.abort()
  voiceRecording.value = true
  try {
    const samples = []
    const steps = [
      'Paso 1 de 4: habla con tu volumen normal, cerca del micrófono.',
      'Paso 2 de 4: aléjate aproximadamente un metro y habla con volumen normal.',
      'Paso 3 de 4: vuelve cerca del micrófono y habla un poco más bajo, sin susurrar.',
      'Paso 4 de 4: mantén la distancia y habla un poco más alto, sin gritar.',
    ]
    for (let index = 0; index < steps.length; index += 1) {
      voiceStepLabel.value = `${steps[index]} Preparando grabación…`
      await sleep(800)
      voiceStepLabel.value = `${steps[index]} Grabando ahora…`
      samples.push(await recordVoiceSample())
      if (index < steps.length - 1) {
        voiceStepLabel.value = `Muestra ${index + 1} completada. ${steps[index + 1]}`
        await sleep(5000)
      }
    }
    voiceStepLabel.value = 'Procesando tus cuatro muestras…'
    const form = new FormData()
    samples.forEach((sample) => form.append('audio', sample, 'voice.webm'))
    await userApi.post('/api/user/voice-profile', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    voiceRegistered.value = true
    voiceStepLabel.value = 'Registro completado: Igris guardó tus cuatro muestras.'
    setNotice('Voz registrada con 4 muestras.', 5000)
  } catch (e) {
    voiceStepLabel.value = ''
    voiceError.value = errorMessage(e, 'No se pudo registrar la voz')
  } finally {
    voiceRecording.value = false
  }
}

async function refreshConnections() {
  conn.value.loading = true
  conn.value.error = ''
  try {
    const res = await userApi.get('/api/user/connections')
    conn.value.features = res.data?.features || []
    conn.value.google = res.data?.google || null
    conn.value.telegram = res.data?.telegram || { linked: false, username: null }
    // El código caduca: si el usuario ya se vinculó, se deja de mostrar.
    if (conn.value.telegram.linked) conn.value.telegramCode = ''
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo consultar tus conexiones')
  } finally {
    conn.value.loading = false
  }
}

function openConnections() {
  conn.value.open = true
  refreshVoiceStatus()
  // Solo se pide al servidor la primera vez; después se refresca desde los
  // botones de dentro, para no repetir la llamada en cada apertura.
  if (!conn.value.features.length && !conn.value.google) refreshConnections()
}

// Google: el servidor devuelve la URL de consentimiento y la abre el navegador.
// Se pide en el momento (no al abrir el panel) porque el 'state' caduca.
async function connectGoogle() {
  conn.value.error = ''
  try {
    const res = await userApi.get('/api/user/google/start')
    const url = res.data?.auth_url
    if (!url) throw new Error('El servidor no devolvió la dirección de Google')
    window.location.href = url
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo iniciar la conexión con Google')
  }
}

async function disconnectGoogle() {
  if (!window.confirm('¿Desconectar tu cuenta de Google? Igris dejará de ver tu correo y tu calendario.')) return
  try {
    await userApi.delete('/api/user/google')
    await refreshConnections()
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo desconectar la cuenta')
  }
}

async function requestTelegramCode() {
  try {
    const res = await userApi.post('/api/user/telegram/code')
    conn.value.telegramCode = res.data?.code || ''
    conn.value.telegramCodeMinutes = res.data?.expires_in_minutes || 15
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo generar el código')
  }
}

async function unlinkTelegram() {
  if (!window.confirm('¿Desvincular tu Telegram? Dejarás de recibir los recordatorios.')) return
  try {
    await userApi.delete('/api/user/telegram')
    conn.value.telegramCode = ''
    await refreshConnections()
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo desvincular el Telegram')
  }
}

/* ───────────── Ciclo de vida ───────────── */
const unlock = () => {
  needsTap.value = false
  if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume()
}

onMounted(() => {
  window.addEventListener('igris:open-connections', openConnections)
  window.addEventListener('igris:open-memory', openMemories)
  window.addEventListener('pointerdown', unlock, { once: true })
  window.addEventListener('keydown', unlock, { once: true })
  runHandsFree()
  if (route.query.open === 'connections') openConnections()
})

onBeforeUnmount(() => {
  window.removeEventListener('igris:open-connections', openConnections)
  window.removeEventListener('igris:open-memory', openMemories)
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
/* ── Panel de conexiones ── */
.conn-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1rem;
  background: rgba(2, 6, 23, 0.78);
}
.conn {
  width: 100%;
  max-width: 34rem;
  max-height: 85vh;
  overflow-y: auto;
  padding: 1.5rem;
  border: 1px solid #334155;
  border-radius: 14px;
  background: #0f172a;
  color: #e2e8f0;
}
.conn h2 {
  margin: 0 0 1rem;
  font-size: 1.15rem;
  font-weight: 600;
  color: #fff;
}
.conn section {
  margin-bottom: 1.25rem;
}
.memory-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.memory-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  margin: 0.45rem 0;
  padding: 0.65rem;
  border: 1px solid #334155;
  border-radius: 9px;
  background: rgba(30, 41, 59, 0.55);
  font-size: 0.84rem;
  line-height: 1.4;
}
.memory-item > span {
  flex: 1;
}
.memory-item input,
.memory-new textarea,
.memory-new select {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #475569;
  border-radius: 7px;
  background: #0b1220;
  color: #e2e8f0;
  padding: 0.55rem;
  font: inherit;
}
.memory-new textarea {
  min-height: 5rem;
  resize: vertical;
}
.memory-new select {
  margin-bottom: 0.5rem;
}
.memory-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
  flex-shrink: 0;
}
.btn.small {
  padding: 0.3rem 0.55rem;
  font-size: 0.72rem;
}
.btn.danger {
  color: #fecaca;
  border-color: rgba(248, 113, 113, 0.45);
}
.conn h3 {
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #94a3b8;
}
.conn-note {
  margin: 0.35rem 0;
  font-size: 0.82rem;
  line-height: 1.5;
  color: #94a3b8;
}
.conn-ok {
  margin: 0.35rem 0;
  font-size: 0.85rem;
  color: #34d399;
}
.conn-error {
  margin: 0.5rem 0;
  padding: 0.6rem 0.75rem;
  border-radius: 8px;
  background: rgba(127, 29, 29, 0.45);
  font-size: 0.82rem;
  color: #fecaca;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.chip {
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(51, 65, 85, 0.8);
  font-size: 0.75rem;
  color: #cbd5e1;
}
.conn-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.6rem;
}
.conn-code {
  margin: 0.6rem 0;
  padding: 0.75rem;
  border: 1px solid #334155;
  border-radius: 10px;
  background: rgba(30, 41, 59, 0.7);
}
.conn-code p {
  margin: 0 0 0.4rem;
  font-size: 0.82rem;
  color: #94a3b8;
}
.conn-code code {
  display: block;
  margin-bottom: 0.4rem;
  font-size: 1.15rem;
  letter-spacing: 0.12em;
  color: #fff;
}
.conn code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.conn-foot {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.5rem;
}

.admin-user-chat-bar{position:fixed;z-index:40;inset:0 0 auto;display:flex;align-items:center;justify-content:flex-end;gap:.9rem;padding:1rem 2rem;background:rgba(18,12,12,.83);color:#eee}.admin-user-chat-bar button{border:1px solid #ffffff20;border-radius:.5rem;background:#ffffff08;padding:.45rem .75rem;color:#eee;cursor:pointer}

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
