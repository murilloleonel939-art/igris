<template>
  <main class="configuration-page min-h-screen text-[#f7f2ef]">
    <section class="mx-auto w-full max-w-6xl px-5 py-8 sm:px-8 lg:px-12 lg:py-12">
      <header class="border-b border-white/10 pb-8">
        <div class="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div class="mb-4 flex items-center gap-2 text-[11px] text-stone-500"><span>Workspace</span><span>›</span><span class="text-stone-300">Configuración</span></div>
            <h1 class="text-3xl font-semibold tracking-tight text-white">Configuración de IA</h1>
            <p class="mt-2 text-sm text-stone-400">Tu inteligencia artificial, conectada y bajo control.</p>
          </div>
          <router-link to="/" class="back-button">← Volver al chat</router-link>
        </div>
        <nav class="mt-9 flex gap-7" aria-label="Secciones de configuración">
          <button class="tab-button" :class="{ active: activeTab === 'providers' }" @click="activeTab = 'providers'">✺ Proveedores</button>
          <button class="tab-button" :class="{ active: activeTab === 'voice' }" @click="activeTab = 'voice'">✦ Voz y audio</button>
           <button class="tab-button" :class="{ active: activeTab === 'whatsapp' }" @click="activeTab = 'whatsapp'">◉ WhatsApp</button>
        </nav>
      </header>

      <div v-if="loading" class="py-20 text-center text-sm text-stone-400">Cargando configuración…</div>
      <div v-else-if="error" class="mt-8 rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-300">{{ error }}</div>

      <div v-else-if="aiConfig" class="pt-7">
        <div v-if="activeTab === 'providers'" class="grid gap-10 lg:grid-cols-[minmax(0,1fr)_255px]">
          <section>
            <div class="flex items-center justify-between gap-3">
              <div><h2 class="section-title">Proveedor principal</h2><p class="section-description">Elige el proveedor que responderá primero a tus consultas.</p></div>
              <span class="online-label"><i class="status-dot"></i>Conectado</span>
            </div>
            <div class="provider-grid mt-5">
              <button v-for="provider in availableProviders" :key="provider" @click="setPrimary(provider)" class="provider-card" :class="{ selected: editConfig.primary_provider === provider }">
                <span class="provider-mark" :class="provider">{{ providerIcon(provider) }}</span>
                <span class="mt-5 block text-sm font-semibold text-white">{{ providerLabel(provider) }}</span>
                <span v-if="editConfig.primary_provider === provider" class="card-check">✓</span>
              </button>
            </div>

            <div class="mt-10 flex items-end justify-between border-b border-white/10 pb-4"><div><h2 class="section-title">Cadena de respaldo</h2><p class="section-description">Si un proveedor no está disponible, IGRIS continuará con el siguiente.</p></div><span class="text-xs text-stone-400">{{ editConfig.fallback_chain.length }} activos</span></div>
            <div class="divide-y divide-white/10">
              <div v-for="(provider, index) in editConfig.fallback_chain" :key="provider" class="fallback-row">
                <span class="w-6 text-[10px] text-stone-500">{{ String(index + 1).padStart(2, '0') }}</span>
                <span class="provider-mark small" :class="provider">{{ providerIcon(provider) }}</span>
                <span class="ml-3 flex-1 text-sm font-medium text-white">{{ providerLabel(provider) }}</span>
                <span v-if="index === 0" class="mr-3 hidden text-[10px] text-emerald-400 sm:block"><i class="status-dot mr-1"></i>Primer respaldo</span>
                <div class="flex items-center gap-1 text-stone-500"><button @click="moveFallback(index, -1)" :disabled="index === 0" class="icon-action">↑</button><button @click="moveFallback(index, 1)" :disabled="index === editConfig.fallback_chain.length - 1" class="icon-action">↓</button><button @click="toggleFallback(provider)" :disabled="editConfig.fallback_chain.length === 1" class="toggle-on"><span></span></button></div>
              </div>
            </div>
            <div class="mt-4 flex flex-wrap gap-2"><button v-for="provider in inactiveProviders" :key="provider" @click="toggleFallback(provider)" class="add-provider">+ Añadir {{ providerLabel(provider) }}</button></div>
            <div class="mt-8 flex flex-col gap-4 border-t border-white/10 pt-5 sm:flex-row sm:items-center sm:justify-between"><p class="text-xs text-stone-500"><span class="mr-1 text-emerald-400">♧</span>{{ saveSuccess || 'Tu configuración está actualizada' }}</p><div class="flex items-center gap-4"><button @click="resetProviderEdits" :disabled="saving" class="discard-button">↶ Descartar</button><button @click="saveConfig" :disabled="saving" class="save-button">{{ saving ? 'Guardando…' : '▣ Guardar cambios' }}</button></div></div>
            <p v-if="saveError" class="mt-3 text-sm text-red-300">{{ saveError }}</p>
          </section>

          <aside class="summary-panel">
            <p class="eyebrow">Estado del sistema</p>
            <div class="mt-4 flex items-center gap-3"><span class="provider-mark large" :class="editConfig.primary_provider">{{ providerIcon(editConfig.primary_provider) }}</span><div><p class="font-semibold text-white">{{ providerLabel(editConfig.primary_provider) }}</p><p class="mt-0.5 text-[10px] text-stone-500">Proveedor principal</p></div></div>
            <p class="mt-5 text-xs text-emerald-400"><i class="status-dot mr-1"></i>Disponible y conectado</p>
            <dl class="metric-list"><div><dt>Proveedores disponibles</dt><dd>{{ availableProviders.length }}</dd></div><div><dt>Respaldos activos</dt><dd>{{ editConfig.fallback_chain.length }}</dd></div><div><dt>Modo de conexión</dt><dd>Automático</dd></div></dl>
            <div class="mt-7 border-t border-white/10 pt-5"><p class="eyebrow">Servicios de voz</p><div class="voice-status"><span>♩</span><div><b>Transcripción</b><small>{{ sttConfig.provider === 'openai' ? 'Whisper OpenAI' : 'Whisper local' }}</small></div><em><i class="status-dot"></i>Activo</em></div><div class="voice-status"><span>◖</span><div><b>Síntesis de voz</b><small>{{ aiConfig.tts.provider || 'Local' }} · TTS</small></div><em><i class="status-dot"></i>Activo</em></div><p class="mt-5 text-[10px] text-stone-500"><span class="mr-1 text-emerald-400">♧</span>Todo en orden</p></div>
          </aside>
        </div>

        <section v-else-if="activeTab === 'voice'" class="grid gap-10 lg:grid-cols-[minmax(0,1fr)_255px]">
          <div><h2 class="section-title">Voz y audio</h2><p class="section-description">Configura cómo IGRIS transcribe y responde mediante voz.</p>
            <article class="voice-panel mt-7"><div class="flex items-start justify-between gap-5"><div><h3 class="text-base font-semibold text-white">Transcripción</h3><p class="mt-1 text-sm text-stone-400">Selecciona el motor que convierte tu voz en texto.</p></div><span class="online-label"><i class="status-dot"></i>Activo</span></div>
              <div class="mt-6 grid gap-3 sm:grid-cols-2"><button @click="sttEdit.provider = 'local'" class="voice-choice" :class="{ selected: sttEdit.provider === 'local' }"><b>Whisper local</b><span>Procesa el audio en el servidor.</span></button><button @click="sttEdit.provider = 'openai'" :disabled="!sttConfig.cloud_ready" class="voice-choice" :class="{ selected: sttEdit.provider === 'openai', disabled: !sttConfig.cloud_ready }"><b>Whisper OpenAI</b><span>{{ sttConfig.cloud_ready ? 'Transcripción cloud de OpenAI.' : 'Requiere IGRIS_STT_API_KEY en Coolify.' }}</span></button></div>
              <div v-if="sttEdit.provider === 'local'" class="mt-5 rounded-lg border border-white/10 bg-black/15 p-4 text-sm text-stone-400"><label for="local-stt-engine">Motor local:</label><select id="local-stt-engine" v-model="sttEdit.local_engine" class="ml-2 rounded border border-white/10 bg-black/20 p-1 text-stone-200"><option v-for="engine in localEngines" :key="engine.value" :value="engine.value">{{ engine.label }}</option></select><label v-if="sttEdit.local_engine !== 'whisper.cpp'" class="ml-4" for="local-compute-type">Precisión:</label><select v-if="sttEdit.local_engine !== 'whisper.cpp'" id="local-compute-type" v-model="sttEdit.local_compute_type" class="ml-2 rounded border border-white/10 bg-black/20 p-1 text-stone-200"><option v-for="type in computeTypes" :key="type.value" :value="type.value">{{ type.label }}</option></select><label v-if="sttEdit.local_engine === 'whisper.cpp'" class="ml-4" for="whisper-cpp-model">Modelo GGML/GGUF:</label><input v-if="sttEdit.local_engine === 'whisper.cpp'" id="whisper-cpp-model" v-model="sttEdit.whisper_cpp_model" placeholder="/app/models/ggml-medium.bin" class="ml-2 rounded border border-white/10 bg-black/20 p-1 text-stone-200" /><label v-if="sttEdit.local_engine !== 'whisper.cpp'" class="ml-4" for="local-whisper-model">Modelo:</label><select v-if="sttEdit.local_engine !== 'whisper.cpp'" id="local-whisper-model" v-model="sttEdit.local_model" class="ml-2 rounded border border-white/10 bg-black/20 p-1 text-stone-200"><option v-for="model in localModels" :key="model.value" :value="model.value">{{ model.label }}</option></select></div><div v-else class="mt-5 rounded-lg border border-white/10 bg-black/15 p-4 text-sm text-stone-400">Modelo cloud activo: <b class="text-stone-200">{{ sttConfig.cloud_model }}</b>. La clave permanece segura en Coolify.</div>
              <div class="mt-6 flex items-center justify-between gap-4"><p v-if="sttError" class="text-sm text-red-300">{{ sttError }}</p><p v-else class="text-sm text-emerald-400">{{ sttSuccess }}</p><button @click="saveSTTConfig" :disabled="sttSaving || (sttEdit.provider === 'openai' && !sttConfig.cloud_ready)" class="save-button ml-auto">{{ sttSaving ? 'Guardando…' : 'Guardar voz y audio' }}</button></div>
            </article>
            <article class="voice-panel mt-5"><h3 class="text-base font-semibold text-white">Síntesis de voz</h3><p class="mt-2 text-sm text-stone-400">Proveedor actual: <b class="text-stone-200">{{ aiConfig.tts.provider || 'local' }}</b>. La voz se reproduce automáticamente tras cada respuesta.</p></article>
          </div>
          <aside class="summary-panel"><p class="eyebrow">Información</p><p class="mt-4 text-sm leading-6 text-stone-400">El cambio de proveedor de transcripción se guarda al instante. Las credenciales nunca se muestran en este panel.</p></aside>
        </section>
         <section v-else class="grid gap-10 lg:grid-cols-[minmax(0,1fr)_255px]">
           <div><h2 class="section-title">WhatsApp</h2><p class="section-description">Define el número que recibirá los mensajes de IGRIS.</p><article class="voice-panel mt-7 max-w-2xl"><label for="whatsapp-phone" class="block text-sm font-semibold text-white">Número de WhatsApp</label><p class="mt-2 text-xs text-stone-400">Usa el formato internacional, incluido el signo +.</p><input id="whatsapp-phone" v-model="whatsappEdit.phone_number" type="tel" inputmode="tel" placeholder="+573162486102" class="mt-5 w-full rounded-lg border border-white/10 bg-black/20 p-3 text-stone-200" /><div class="mt-6 flex items-center justify-between gap-4"><p v-if="whatsappError" class="text-sm text-red-300">{{ whatsappError }}</p><p v-else class="text-sm text-emerald-400">{{ whatsappSuccess }}</p><button @click="saveWhatsAppConfig" :disabled="whatsappSaving" class="save-button ml-auto">{{ whatsappSaving ? 'Guardando…' : 'Guardar número' }}</button></div></article></div><aside class="summary-panel"><p class="eyebrow">Canal de mensajes</p><p class="mt-4 text-sm leading-6 text-stone-400">Los tokens permanecen en la configuración segura del servidor y nunca se muestran aquí.</p></aside>
         </section>
      </div>
    </section>
   </main>
 </template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '../api'

const loading = ref(true), error = ref(null), activeTab = ref('providers'), aiConfig = ref(null)
const editConfig = ref({ primary_provider: '', fallback_chain: [] })
const saving = ref(false), saveSuccess = ref(''), saveError = ref('')
const sttConfig = ref({ provider: 'local', local_engine: 'whisper', local_compute_type: 'int8', whisper_cpp_model: '', cloud_model: 'whisper-1', local_model: 'tiny', cloud_ready: false })
const sttEdit = ref({ provider: 'local', local_engine: 'whisper', local_compute_type: 'int8', whisper_cpp_model: '', local_model: 'tiny' }), sttSaving = ref(false), sttSuccess = ref(''), sttError = ref('')
const whatsappEdit = ref({ phone_number: '' }), whatsappSaving = ref(false), whatsappSuccess = ref(''), whatsappError = ref('')
const localEngines = [{ value: 'whisper', label: 'Whisper' }, { value: 'faster-whisper', label: 'faster-whisper' }, { value: 'whisper.cpp', label: 'whisper.cpp (GGML/GGUF)' }]
const computeTypes = [{ value: 'int8', label: 'int8 — CPU recomendado' }, { value: 'float16', label: 'float16 — GPU' }, { value: 'float32', label: 'float32 — máxima compatibilidad' }]
const localModels = [
  { value: 'tiny', label: 'Tiny — más rápido' },
  { value: 'base', label: 'Base — equilibrio' },
  { value: 'small', label: 'Small — más precisión' },
  { value: 'medium', label: 'Medium — máxima precisión local' },
]
const availableProviders = ['groq', 'nemotron', 'openai', 'anthropic', 'local']
const inactiveProviders = computed(() => availableProviders.filter(p => !editConfig.value.fallback_chain.includes(p)))
const providerLabel = p => ({ groq: 'Groq', nemotron: 'Nemotron', openai: 'OpenAI', anthropic: 'Anthropic', local: 'Local' }[p] || p)
const providerIcon = p => ({ groq: 'g', nemotron: '✺', openai: '✧', anthropic: 'A', local: '◇' }[p] || '◇')

const loadAIConfig = async () => {
  try {
    loading.value = true
    const [response, sttResponse, whatsappResponse] = await Promise.all([api.get('/api/ai-config'), api.get('/api/stt-config'), api.get('/api/whatsapp-config')])
    if (response.data.status !== 'ok') throw new Error(response.data.message)
    aiConfig.value = { primary_provider: response.data.primary_provider, fallback_chain: [...response.data.fallback_chain], tts: response.data.tts || { provider: 'local', enabled: true } }
    editConfig.value = { primary_provider: aiConfig.value.primary_provider, fallback_chain: [...aiConfig.value.fallback_chain] }
    if (sttResponse.data.status === 'ok') { sttConfig.value = sttResponse.data; sttEdit.value = { provider: sttResponse.data.provider, local_engine: sttResponse.data.local_engine || 'whisper', local_compute_type: sttResponse.data.local_compute_type || 'int8', whisper_cpp_model: sttResponse.data.whisper_cpp_model || '', local_model: sttResponse.data.local_model } }
    if (whatsappResponse.data.status === 'ok') whatsappEdit.value.phone_number = whatsappResponse.data.phone_number || ''
  } catch (err) { error.value = err.response?.data?.detail || 'No se pudo cargar la configuración.' } finally { loading.value = false }
}
const setPrimary = p => { editConfig.value.primary_provider = p; if (!editConfig.value.fallback_chain.includes(p)) editConfig.value.fallback_chain.unshift(p) }
const toggleFallback = p => { const i = editConfig.value.fallback_chain.indexOf(p); if (i === -1) editConfig.value.fallback_chain.push(p); else if (editConfig.value.fallback_chain.length > 1) editConfig.value.fallback_chain.splice(i, 1) }
const moveFallback = (i, d) => { const target = i + d; if (target < 0 || target >= editConfig.value.fallback_chain.length) return; const list = editConfig.value.fallback_chain; [list[i], list[target]] = [list[target], list[i]] }
const resetProviderEdits = () => { editConfig.value = { primary_provider: aiConfig.value.primary_provider, fallback_chain: [...aiConfig.value.fallback_chain] }; saveError.value = ''; saveSuccess.value = '' }
const saveConfig = async () => { if (!editConfig.value.primary_provider || !editConfig.value.fallback_chain.length) { saveError.value = 'Selecciona un proveedor y al menos un respaldo.'; return }; try { saving.value = true; saveError.value = ''; saveSuccess.value = ''; const response = await api.put('/api/ai-config', editConfig.value); if (response.data.status !== 'ok') throw new Error(response.data.message); aiConfig.value.primary_provider = editConfig.value.primary_provider; aiConfig.value.fallback_chain = [...editConfig.value.fallback_chain]; saveSuccess.value = response.data.message || 'Configuración guardada correctamente.' } catch (err) { saveError.value = err.response?.data?.detail || err.message || 'No se pudo guardar la configuración.' } finally { saving.value = false } }
const saveWhatsAppConfig = async () => { try { whatsappSaving.value = true; whatsappError.value = ''; whatsappSuccess.value = ''; const response = await api.put('/api/whatsapp-config', whatsappEdit.value); whatsappEdit.value.phone_number = response.data.phone_number || ''; whatsappSuccess.value = response.data.message || 'Número de WhatsApp guardado.' } catch (err) { whatsappError.value = err.response?.data?.detail || 'No se pudo guardar el número de WhatsApp.' } finally { whatsappSaving.value = false } }
const saveSTTConfig = async () => { try { sttSaving.value = true; sttError.value = ''; sttSuccess.value = ''; const response = await api.put('/api/stt-config', { provider: sttEdit.value.provider, local_engine: sttEdit.value.local_engine, local_compute_type: sttEdit.value.local_compute_type, whisper_cpp_model: sttEdit.value.whisper_cpp_model, local_model: sttEdit.value.local_model }); sttConfig.value = response.data; sttEdit.value.local_engine = response.data.local_engine; sttEdit.value.local_compute_type = response.data.local_compute_type; sttEdit.value.whisper_cpp_model = response.data.whisper_cpp_model; sttEdit.value.local_model = response.data.local_model; sttSuccess.value = response.data.message || 'Configuración de voz guardada.' } catch (err) { sttError.value = err.response?.data?.detail || 'No se pudo guardar la configuración de voz.' } finally { sttSaving.value = false } }
onMounted(loadAIConfig)
</script>

<style scoped>
.configuration-page{background:#100807;min-height:100vh}.back-button{display:inline-flex;align-items:center;justify-content:center;border:1px solid rgba(255,255,255,.15);border-radius:.55rem;padding:.55rem 1rem;color:#c7bbb5;font-size:.85rem;transition:.2s}.back-button:hover{border-color:rgba(255,255,255,.3);background:rgba(255,255,255,.05);color:#fff}.tab-button{border-bottom:1px solid transparent;padding:0 0 12px;color:#8e817c;font-size:.78rem;transition:.2s}.tab-button:hover,.tab-button.active{color:#fff;border-color:#f0443e}.section-title{color:#fff;font-size:1rem;font-weight:650}.section-description{margin-top:.35rem;color:#a29691;font-size:.76rem}.online-label{display:inline-flex;align-items:center;gap:.35rem;color:#4ed49e;font-size:.67rem}.provider-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.55rem;max-width:37rem}.provider-card{position:relative;min-height:7rem;border:1px solid rgba(255,255,255,.12);border-radius:.75rem;padding:1rem;background:rgba(255,255,255,.025);text-align:left;transition:.2s}.provider-card:hover{border-color:rgba(255,255,255,.28);background:rgba(255,255,255,.045)}.provider-card.selected{border-color:#ec3f39;background:rgba(184,35,31,.09);box-shadow:inset 0 0 0 1px rgba(236,63,57,.18)}.provider-mark{display:inline-flex;height:1.5rem;width:1.5rem;align-items:center;justify-content:center;border-radius:.4rem;font-size:.95rem;font-weight:700}.provider-mark.small{height:1.35rem;width:1.35rem;font-size:.78rem}.provider-mark.large{height:2.5rem;width:2.5rem;font-size:1.25rem}.provider-mark.openai{color:#72e6be;background:rgba(50,204,149,.12)}.provider-mark.nemotron{color:#b0df62;background:rgba(168,221,87,.11)}.provider-mark.anthropic{color:#f0a35f;background:rgba(240,163,95,.1)}.provider-mark.groq{color:#ff745f;background:rgba(255,116,95,.1)}.provider-mark.local{color:#9fc3ff;background:rgba(124,167,255,.1)}.card-check{position:absolute;top:.75rem;right:.75rem;display:grid;height:1rem;width:1rem;place-items:center;border:1px solid #f0443e;border-radius:100%;color:#f0443e;font-size:.6rem}.fallback-row{display:flex;min-height:3.7rem;align-items:center}.icon-action{padding:.25rem;font-size:.85rem;transition:.2s}.icon-action:hover:not(:disabled){color:#fff}.icon-action:disabled{cursor:default;opacity:.25}.toggle-on{height:1.25rem;width:2.25rem;border-radius:999px;background:#ee4842;padding:.125rem;transition:.2s}.toggle-on:disabled{opacity:.4}.toggle-on span{display:block;height:1rem;width:1rem;transform:translateX(1rem);border-radius:100%;background:#fff;box-shadow:0 1px 3px #0008}.add-provider{border:1px dashed rgba(255,255,255,.18);border-radius:.5rem;padding:.4rem .65rem;color:#a29691;font-size:.7rem;transition:.2s}.add-provider:hover{border-color:#ec3f39;color:#fff}.status-dot{display:inline-block;height:.32rem;width:.32rem;border-radius:100%;background:currentColor}.summary-panel{border-left:1px solid rgba(255,255,255,.1);padding-left:1.75rem}.eyebrow{color:#a29691;font-size:.61rem;font-weight:650;letter-spacing:.11em;text-transform:uppercase}.metric-list{margin-top:1.35rem;border-top:1px solid rgba(255,255,255,.1)}.metric-list div{display:flex;justify-content:space-between;padding:.7rem 0;color:#a29691;font-size:.7rem}.metric-list dd{color:#fff;font-weight:600}.voice-status{display:grid;grid-template-columns:1rem 1fr auto;align-items:center;gap:.55rem;padding:.85rem 0;border-bottom:1px solid rgba(255,255,255,.07)}.voice-status>span{color:#a29691}.voice-status b{display:block;color:#fff;font-size:.72rem}.voice-status small{color:#817570;font-size:.61rem}.voice-status em{color:#4ed49e;font-size:.59rem;font-style:normal}.save-button{border-radius:.55rem;background:#ee4842;padding:.63rem .9rem;color:#fff;font-size:.78rem;font-weight:600;transition:.2s}.save-button:hover:not(:disabled){background:#ff5b55}.save-button:disabled{cursor:not-allowed;opacity:.5}.discard-button{color:#817570;font-size:.8rem;transition:.2s}.discard-button:hover{color:#fff}.voice-panel{border:1px solid rgba(255,255,255,.1);border-radius:.8rem;background:rgba(255,255,255,.025);padding:1.25rem}.voice-choice{min-height:6.25rem;border:1px solid rgba(255,255,255,.12);border-radius:.7rem;padding:1rem;text-align:left;transition:.2s}.voice-choice b{display:block;color:#fff;font-size:.9rem}.voice-choice span{display:block;margin-top:.45rem;color:#9e918c;font-size:.74rem;line-height:1.35}.voice-choice:hover:not(.disabled),.voice-choice.selected{border-color:#ec3f39;background:rgba(184,35,31,.09)}.voice-choice.disabled{cursor:not-allowed;opacity:.5}@media(min-width:640px){.provider-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:1023px){.summary-panel{border-left:0;border-top:1px solid rgba(255,255,255,.1);padding-left:0;padding-top:1.5rem}}
</style>
