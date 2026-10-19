<!--
  UserChat.vue — Chat de Igris para los usuarios del área /u.

  Es la misma experiencia que el chat del administrador (voz manos libres,
  respuestas habladas, historial), pero apuntando a las rutas /api/user/* con
  el token del usuario en lugar de la clave única.

  Lo que NO tiene, a propósito: navegación al panel, ni a /config, ni ninguna
  ruta de administración. Un usuario solo ve su chat.
-->
<template>
  <div class="dash" :class="{ 'connections-page': route.name === 'UserConnections' }">
    <!-- Avisos -->
    <div v-if="notice" class="notice">{{ notice }}</div>
    <div v-else-if="needsTap" class="notice soft">Toca la pantalla para activar el sonido</div>
    <div v-if="proactive.alerts.length" class="proactive-alerts" role="status">
      <div v-for="alert in proactive.alerts" :key="alert.key" class="proactive-alert">
        <span class="proactive-icon">{{ alert.kind === 'reminder_overdue' ? '!' : '•' }}</span>
        <div><strong>{{ alert.title }}</strong><span>{{ alert.text }} · {{ formatPerceptionDate(alert.due_at) }}</span></div>
        <button type="button" class="proactive-close" @click="dismissProactive(alert)">×</button>
      </div>
    </div>

    <!-- Panel de memoria personal y operativa -->
    <div v-if="memories.open" class="conn-backdrop" @click.self="memories.open = false">
      <div class="conn memory-panel">
        <header class="conn-head">
          <div class="conn-crumbs"><span>Workspace</span><span>›</span><span>Mi memoria</span></div>
          <h2>Mi memoria</h2>
          <p>Aquí puedes revisar y corregir lo que Igris recuerda de ti.</p>
        </header>
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

    <!-- Panel de percepción en modo lectura -->
    <div v-if="perception.open" class="conn-backdrop" @click.self="perception.open = false">
      <div class="conn perception-panel">
        <header class="conn-head">
          <div class="conn-crumbs"><span>Workspace</span><span>›</span><span>Resumen del día</span></div>
          <h2>Resumen del día</h2>
          <p>Información de tus fuentes conectadas. Igris no cambia nada desde aquí.</p>
        </header>
        <p v-if="perception.error" class="conn-error">{{ perception.error }}</p>
        <p v-if="perception.loading" class="conn-note">Consultando tus datos…</p>
        <template v-else>
          <section>
            <h3>Recordatorios pendientes</h3>
            <div v-if="!perception.data.reminders.length" class="conn-note">No tienes recordatorios pendientes.</div>
            <div v-for="item in perception.data.reminders" :key="`r-${item.id}`" class="perception-item">
              <strong>{{ item.text }}</strong><span>{{ formatPerceptionDate(item.due_at) }}</span>
            </div>
          </section>
          <section>
            <h3>Calendario próximo</h3>
            <div v-if="!perception.data.calendar.length" class="conn-note">No hay eventos en los próximos 7 días.</div>
            <div v-for="item in perception.data.calendar" :key="`c-${item.id}`" class="perception-item">
              <strong>{{ item.titulo }}</strong><span>{{ item.fecha }}<template v-if="item.inicio"> · {{ item.inicio }}</template></span>
            </div>
          </section>
          <section>
            <h3>Correos sin leer</h3>
            <div v-if="!perception.data.emails.length" class="conn-note">No hay correos sin leer o Google no está conectado.</div>
            <div v-for="item in perception.data.emails" :key="`e-${item.id}`" class="perception-item">
              <strong>{{ item.asunto }}</strong><span>{{ item.de }} · {{ item.recibido }}</span>
            </div>
          </section>
          <section>
            <h3>Notas recientes</h3>
            <div v-if="!perception.data.notes.length" class="conn-note">No tienes notas guardadas.</div>
            <div v-for="item in perception.data.notes" :key="`n-${item.id}`" class="perception-item"><span>{{ item.text }}</span></div>
          </section>
          <p v-if="perception.data.errors.length" class="conn-error">{{ perception.data.errors.join(' ') }}</p>
        </template>
        <div class="conn-foot"><button class="btn ghost" @click="perception.open = false">Cerrar</button></div>
      </div>
    </div>

    <!-- Panel de conexiones: qué funciones tienes y qué te falta conectar -->
    <div v-if="conn.open || route.name === 'UserConnections'" class="conn-backdrop" :class="{ 'conn-page': route.name === 'UserConnections' }" @click.self="route.name !== 'UserConnections' && (conn.open = false)">
      <div class="conn">
        <header class="conn-head">
          <div class="conn-crumbs"><span>Workspace</span><span>›</span><span>Conexiones</span></div>
          <h2>Conexiones</h2>
          <p>Tus cuentas y tu voz. Cada cosa se conecta con tu propia cuenta: nadie más ve tus datos.</p>
        </header>

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

          <section v-if="conn.spotify && conn.spotify.needs_spotify">
            <h3>Spotify</h3>
            <p v-if="conn.spotify.connected" class="conn-ok">Conectado{{ conn.spotify.display_name ? `: ${conn.spotify.display_name}` : '' }}{{ conn.spotify.email ? ` (${conn.spotify.email})` : '' }}.</p>
            <p v-if="conn.spotify.error" class="conn-error">Spotify dio un error: {{ conn.spotify.error }}</p>
            <p v-if="!conn.spotify.app_configured" class="conn-note">El administrador todavía no ha configurado Spotify.</p>
            <template v-else>
              <p class="conn-note">Igris usará tu propia cuenta de Spotify mediante su API oficial.</p>
              <div class="conn-actions">
                <button class="btn primary" @click="connectSpotify">{{ conn.spotify.connected ? 'Volver a conectar' : 'Conectar mi Spotify' }}</button>
                <button v-if="conn.spotify.connected" class="btn ghost" @click="disconnectSpotify">Desconectar</button>
              </div>
            </template>
          </section>

          <section v-if="conn.youtube && conn.youtube.needs_youtube">
            <h3>YouTube</h3>
            <p v-if="conn.youtube.connected" class="conn-ok">Conectado a YouTube{{ conn.youtube.email ? `: ${conn.youtube.email}` : '' }}.</p>
            <p v-if="conn.youtube.error" class="conn-error">YouTube dio un error: {{ conn.youtube.error }}</p>
            <p v-if="!conn.youtube.app_configured" class="conn-note">El administrador todavía no ha configurado YouTube.</p>
            <template v-else>
              <p class="conn-note">Igris usará tu propia cuenta para consultar y administrar tus listas.</p>
              <div class="conn-actions">
                <button class="btn primary" @click="connectYouTube">{{ conn.youtube.connected ? 'Volver a conectar' : 'Conectar mi YouTube' }}</button>
                <button v-if="conn.youtube.connected" class="btn ghost" @click="disconnectYouTube">Desconectar</button>
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
          <button class="btn ghost" @click="route.name === 'UserConnections' ? router.replace('/') : (conn.open = false)">{{ route.name === 'UserConnections' ? 'Volver al chat' : 'Cerrar' }}</button>
        </div>
      </div>
    </div>

    <div v-if="route.name !== 'UserConnections'" class="bottom">
      <!-- Historial -->
      <div v-show="chatMessages.length" ref="chatBox" class="history">
        <div v-for="(msg, i) in chatMessages" :key="i" class="msg">
          <span :class="['from', msg.from === 'user' ? 'user' : 'igris']">{{ msg.from }}:</span>
          <span class="text">{{ msg.text }}</span>
          <span
            v-for="doc in (msg.documents || [])"
            :key="doc.filename"
            class="doc-download"
          >Guardado en {{ doc.local_path || 'tu carpeta Documentos' }}</span>
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
import { ref, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import userApi, { getUser, clearSession, errorMessage } from '../userApi'
import { getKey } from '../api'
import { igris, setIgrisState } from '../composables/useIgris'
import IgrisHero from '../components/IgrisHero.vue'
import WorkspaceNav from '../components/WorkspaceNav.vue'

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

/* ───────────── Enviar mensaje al backend ───────────── */const sendMessage = async (raw) => {
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
      chatMessages.value.push({
        from: 'igris',
        text: response.data.reply,
        documents: response.data.documents || [],
      })
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
        // Umbral más sensible para micrófonos de portátil y voz baja.
        if (rms > 0.004) {
          heardSpeech = true
          if (!speechStartedAt) speechStartedAt = now
          lastSpeechAt = now
        }
        // No cortar frases por una pausa breve al respirar o pensar.
        // No enviar silencios largos: evitan timeouts y falsas órdenes del STT.
        if (speechStartedAt && now - lastSpeechAt > 900 && now - speechStartedAt > 600) {
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
    // El VAD termina al detectar silencio; este límite es solo protección.
    setTimeout(() => stopCapture?.(), 8000)
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
      // capturado la voz. El backend verifica la voz localmente y luego transcribe.
      if (audio) {
        setIgrisState('processing')
        const form = new FormData()
        form.append('audio', audio, 'voice.webm')
        form.append('session_id', sessionId)
        try {
          const response = await userApi.post('/api/user/voice-chat', form, {
            headers: { 'Content-Type': 'multipart/form-data' },
          })
          if (response.data.status === 'ok') {
            setNotice('')
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

const proactive = ref({ alerts: [] })
let proactiveTimer = 0

function dismissProactive(alert) {
  const dismissed = JSON.parse(localStorage.getItem('igris:dismissed-alerts') || '[]')
  if (!dismissed.includes(alert.key)) dismissed.push(alert.key)
  localStorage.setItem('igris:dismissed-alerts', JSON.stringify(dismissed.slice(-50)))
  proactive.value.alerts = proactive.value.alerts.filter((item) => item.key !== alert.key)
}

async function refreshProactiveAlerts() {
  try {
    const res = await userApi.get('/api/user/proactive-alerts')
    const dismissed = new Set(JSON.parse(localStorage.getItem('igris:dismissed-alerts') || '[]'))
    proactive.value.alerts = (res.data?.alerts || []).filter((alert) => !dismissed.has(alert.key))
  } catch (e) {
    // Los avisos son opcionales; no interrumpen el chat si la consulta falla.
  }
}

const perception = ref({
  open: false,
  loading: false,
  error: '',
  data: { reminders: [], notes: [], calendar: [], emails: [], errors: [] },
})

function formatPerceptionDate(value) {
  if (!value) return ''
  try { return new Date(value).toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' }) } catch (e) { return value }
}

async function refreshPerception() {
  perception.value.loading = true
  perception.value.error = ''
  try {
    const res = await userApi.get('/api/user/perception')
    perception.value.data = {
      reminders: res.data?.reminders || [], notes: res.data?.notes || [],
      calendar: res.data?.calendar || [], emails: res.data?.emails || [], errors: res.data?.errors || [],
    }
  } catch (e) {
    perception.value.error = errorMessage(e, 'No se pudo consultar tu resumen')
  } finally {
    perception.value.loading = false
  }
}

function openPerception() {
  perception.value.open = true
  refreshPerception()
}

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
  youtube: null,
  spotify: null,
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
    youtube: 'Administrar listas de YouTube',
    spotify: 'Spotify',
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
      'Paso 1 de 6: habla con tu volumen normal, cerca del micrófono.',
      'Paso 2 de 6: aléjate aproximadamente un metro y habla con volumen normal.',
      'Paso 3 de 6: vuelve cerca del micrófono y habla un poco más bajo, sin susurrar.',
      'Paso 4 de 6: mantén la distancia y habla un poco más alto, sin gritar.',
      'Paso 5 de 6: habla espontáneamente con ruido de fondo moderado.',
      'Paso 6 de 6: cambia ligeramente de posición y di otra frase espontánea.',
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
    voiceStepLabel.value = 'Procesando tus seis muestras…'
    const form = new FormData()
    samples.forEach((sample) => form.append('audio', sample, 'voice.webm'))
    await userApi.post('/api/user/voice-profile', form, { headers: { 'Content-Type': 'multipart/form-data' } })
    voiceRegistered.value = true
    voiceStepLabel.value = 'Registro completado: Igris guardó tus seis muestras.'
    setNotice('Voz registrada con 6 muestras.', 5000)
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
    conn.value.youtube = res.data?.youtube || null
    conn.value.spotify = res.data?.spotify || null
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

// Entrar por el menú a /conexiones no vuelve a montar el componente: Vue
// reutiliza esta misma instancia. Sin este vigilante, el panel no se abriría
// al pulsar «Conexiones» y el usuario vería el chat. Al salir se cierra, para
// que no quede el panel flotando encima del chat.
watch(
  () => [route.name, route.query.open],
  ([name, open]) => {
    if (name === 'UserConnections') openConnections()
    else conn.value.open = false
    if (name === 'UserChat' && open === 'memory') openMemories()
    else if (name === 'UserChat') memories.value.open = false
  },
)

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

async function connectSpotify() {
  conn.value.error = ''
  try {
    const res = await userApi.get('/api/user/spotify/start')
    const url = res.data?.auth_url
    if (!url) throw new Error('El servidor no devolvió la dirección de Spotify')
    window.location.href = url
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo iniciar la conexión con Spotify')
  }
}

async function disconnectSpotify() {
  if (!window.confirm('¿Desconectar tu cuenta de Spotify?')) return
  try {
    await userApi.delete('/api/user/spotify')
    await refreshConnections()
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo desconectar Spotify')
  }
}

async function connectYouTube() {
  conn.value.error = ''
  try {
    const res = await userApi.get('/api/user/youtube/start')
    const url = res.data?.auth_url
    if (!url) throw new Error('El servidor no devolvió la dirección de YouTube')
    window.location.href = url
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo iniciar la conexión con YouTube')
  }
}

async function disconnectYouTube() {
  if (!window.confirm('¿Desconectar tu cuenta de Google? También se desconectará el acceso a YouTube.')) return
  try {
    await userApi.delete('/api/user/youtube')
    await refreshConnections()
  } catch (e) {
    conn.value.error = errorMessage(e, 'No se pudo desconectar YouTube')
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
  window.addEventListener('igris:open-perception', openPerception)
  window.addEventListener('pointerdown', unlock, { once: true })
  window.addEventListener('keydown', unlock, { once: true })
  runHandsFree()
  refreshProactiveAlerts()
  proactiveTimer = window.setInterval(refreshProactiveAlerts, 60000)
  if (route.query.open === 'connections' || route.name === 'UserConnections') openConnections()
  if (route.query.open === 'memory' && route.name === 'UserChat') openMemories()
})

onBeforeUnmount(() => {
  window.removeEventListener('igris:open-connections', openConnections)
  window.removeEventListener('igris:open-memory', openMemories)
  window.removeEventListener('igris:open-perception', openPerception)
  window.removeEventListener('pointerdown', unlock)
  window.removeEventListener('keydown', unlock)
  clearTimeout(noticeTimer)
  clearInterval(proactiveTimer)
  handsFree.value = false
  if (recognition) recognition.abort()
  stopSpeaking()
  stopLevelMeter()
  setIgrisState('idle')
})
</script>

<style scoped>
/* ── Paneles (conexiones y memoria) — diseño del workspace ── */
.proactive-alerts {
  position: fixed;
  z-index: 50;
  top: 5rem;
  right: 1rem;
  width: min(26rem, calc(100vw - 2rem));
  display: grid;
  gap: .5rem;
}
.proactive-alert {
  display: flex;
  align-items: flex-start;
  gap: .6rem;
  padding: .75rem .8rem;
  border: 1px solid rgba(240, 128, 114, .45);
  border-radius: .7rem;
  background: rgba(35, 15, 13, .95);
  color: #f2e8e3;
  box-shadow: 0 12px 30px rgba(0,0,0,.28);
}
.proactive-alert strong,
.proactive-alert span { display: block; }
.proactive-alert span { margin-top: .15rem; color: #cbbab3; font-size: .78rem; }
.proactive-icon { color: #f08072 !important; font-weight: 800; font-size: 1rem !important; }
.proactive-close { margin-left: auto; border: 0; background: transparent; color: #b9aaa4; font-size: 1.2rem; cursor: pointer; }
.conn-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  overflow-y: auto;
  padding: 5.5rem 1rem 2.5rem;
  background: rgba(8, 4, 4, 0.86);
  backdrop-filter: blur(14px);
}
.conn-backdrop.conn-page {
  position: relative;
  inset: auto;
  min-height: 100vh;
  padding: 7rem 1.25rem 3rem;
  background: transparent;
  backdrop-filter: none;
}
.conn {
  width: 100%;
  max-width: 44rem;
  margin: auto;
  padding: 1.75rem clamp(1.1rem, 3vw, 2.25rem) 2rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 1rem;
  background: #140b0a;
  color: #ded4cf;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.45);
}
.conn-backdrop.conn-page .conn {
  max-width: 48rem;
}
.conn-head {
  margin-bottom: 1.35rem;
  padding-bottom: 1.15rem;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.conn-crumbs {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
  color: #8c7d77;
  font-size: 0.68rem;
  letter-spacing: 0.05em;
}
.conn-crumbs span:last-child {
  color: #cbbdb7;
}
.conn-head h2,
.conn > h2 {
  margin: 0;
  color: #fff;
  font-size: 1.5rem;
  font-weight: 650;
  letter-spacing: -0.01em;
}
.conn > h2 {
  margin-bottom: 1rem;
}
.conn-head p {
  margin: 0.5rem 0 0;
  max-width: 34rem;
  color: #a99b95;
  font-size: 0.82rem;
  line-height: 1.55;
}
.conn section {
  margin-bottom: 0.85rem;
  padding: 1rem 1.1rem;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 0.8rem;
  background: rgba(255, 255, 255, 0.025);
}
.memory-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}
.perception-item {
  display: flex;
  justify-content: space-between;
  gap: 0.7rem;
  margin: 0.45rem 0;
  padding: 0.65rem;
  border: 1px solid rgba(255, 255, 255, .1);
  border-radius: .6rem;
  background: rgba(255,255,255,.035);
  font-size: .82rem;
}
.perception-item span:last-child {
  color: #a99a94;
  text-align: right;
  font-size: .75rem;
}
.memory-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  margin: 0.45rem 0;
  padding: 0.65rem;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 0.6rem;
  background: rgba(255, 255, 255, 0.035);
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
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 0.5rem;
  background: rgba(0, 0, 0, 0.35);
  color: #f3ece8;
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
  color: #f7b6ae;
  border: 1px solid rgba(240, 90, 80, 0.35);
  background: rgba(240, 72, 65, 0.08);
}
.conn h3 {
  margin: 0 0 0.55rem;
  font-size: 0.8rem;
  font-weight: 650;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #cbbdb7;
}
.conn-note {
  margin: 0.35rem 0;
  font-size: 0.82rem;
  line-height: 1.55;
  color: #a99b95;
}
.conn-ok {
  margin: 0.35rem 0;
  font-size: 0.85rem;
  color: #5bd6a1;
}
.conn-error {
  margin: 0.5rem 0;
  padding: 0.6rem 0.8rem;
  border: 1px solid rgba(240, 90, 80, 0.28);
  border-radius: 0.6rem;
  background: rgba(127, 29, 29, 0.32);
  font-size: 0.82rem;
  color: #f7b6ae;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.chip {
  padding: 0.25rem 0.7rem;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  font-size: 0.75rem;
  color: #ded4cf;
}
.conn-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.7rem;
}
/* Los botones del panel usan el acento del workspace, no el azul genérico. */
.conn .btn {
  border: 1px solid transparent;
  border-radius: 0.6rem;
  font-size: 0.84rem;
  font-weight: 550;
}
.conn .btn.primary {
  background: #e0453e;
  color: #fff;
}
.conn .btn.primary:hover:not(:disabled) {
  background: #f05a50;
}
.conn .btn.ghost {
  border-color: rgba(255, 255, 255, 0.13);
  background: rgba(255, 255, 255, 0.05);
  color: #ded4cf;
}
.conn .btn.ghost:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
}
.conn-code {
  margin: 0.6rem 0;
  padding: 0.8rem;
  border: 1px solid rgba(240, 90, 80, 0.25);
  border-radius: 0.7rem;
  background: rgba(240, 72, 65, 0.07);
}
.conn-code p {
  margin: 0 0 0.4rem;
  font-size: 0.82rem;
  color: #cbbdb7;
}
.conn-code code {
  display: block;
  margin-bottom: 0.4rem;
  font-size: 1.2rem;
  letter-spacing: 0.14em;
  color: #fff;
}
.conn code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.conn-foot {
  display: flex;
  justify-content: flex-end;
  margin-top: 0.9rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
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
/* Enlace de descarga del documento Word generado por Igris. */
.doc-download {
  flex: none;
  align-self: center;
  margin-left: 10px;
  padding: 4px 10px;
  border: 1px solid #2563eb66;
  border-radius: 6px;
  background: #2563eb22;
  color: #bfdbfe;
  font-size: .82em;
  text-decoration: none;
  white-space: nowrap;
}
.doc-download:hover {
  background: #2563eb44;
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
