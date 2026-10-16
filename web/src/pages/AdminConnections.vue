<template>
  <main class="connections-page mx-auto min-h-screen w-full max-w-6xl px-5 py-8 text-stone-200 sm:px-8 lg:px-12 lg:py-11">
    <header class="mb-8 border-b border-white/10 pb-7">
      <div class="mb-4 flex items-center gap-2 text-[11px] text-stone-500"><span>Workspace</span><span>›</span><span class="text-stone-300">Conexiones</span></div>
      <h1 class="text-3xl font-semibold tracking-tight text-white">Conexiones</h1>
      <p class="mt-2 max-w-2xl text-sm text-stone-400">Revisa las cuentas externas vinculadas por cada usuario.</p>
    </header>
    <p v-if="error" class="mb-5 rounded-lg border border-red-500/25 bg-red-950/30 px-4 py-3 text-sm text-red-200">{{ error }}</p>
    <div v-if="loading" class="empty-state">Cargando conexiones…</div>
    <div v-else-if="!users.length" class="empty-state"><b>Aún no hay usuarios</b><span>Las conexiones aparecerán aquí cuando existan cuentas.</span></div>
    <section v-else class="connection-list">
      <article v-for="user in users" :key="user.id" class="connection-card">
        <header class="connection-card__head"><span class="user-avatar">{{ user.username.slice(0,2).toUpperCase() }}</span><div class="user-title"><b>{{ user.username }}</b><span>{{ user.email }}</span></div><span class="state-chip" :class="user.is_active ? 'active' : 'inactive'">{{ user.is_active ? 'Activo' : 'Desactivado' }}</span></header>
        <div class="services">
          <div class="service"><span class="service-icon google">G</span><div class="service-info"><b>Google</b><span v-if="user.connections?.google">Conectado · {{ user.connections.google }}</span><span v-else-if="user.connections?.google_error" class="warning">La conexión reportó un error</span><span v-else>Sin conectar</span></div><i class="service-status" :class="user.connections?.google ? 'ok' : user.connections?.google_error ? 'bad' : ''"></i><button v-if="user.is_active" class="connect" @click="goToUserLogin">{{ user.connections?.google ? 'Gestionar' : 'Conectar' }}</button></div>
          <div class="service"><span class="service-icon telegram">➤</span><div class="service-info"><b>Telegram</b><span v-if="user.connections?.telegram_linked">Vinculado<span v-if="user.connections?.telegram"> · {{ user.connections.telegram }}</span></span><span v-else>Sin vincular</span></div><i class="service-status" :class="user.connections?.telegram_linked ? 'ok' : ''"></i><button v-if="user.connections?.telegram_linked" class="unlink" :disabled="unlinking === user.id" @click="unlinkTelegram(user)">{{ unlinking === user.id ? 'Desvinculando…' : 'Desvincular' }}</button><button v-else-if="user.is_active" class="connect" @click="goToUserLogin">Conectar</button></div>
          <div class="service"><span class="service-icon voice">♫</span><div class="service-info"><b>Reconocimiento de voz</b><span>La grabación se gestiona desde la sesión personal del usuario.</span></div><a class="connect" :href="`/u/login?next=${encodeURIComponent('/u')}`">Iniciar sesión</a></div>
          <p class="user-portal-hint">Estas acciones se realizan desde la cuenta personal por seguridad. Usa el acceso de {{ user.username }} para conectar servicios o registrar la voz.</p>
          <a v-if="user.is_active" class="user-portal-link" href="/u/login">Abrir acceso personal de {{ user.username }} →</a>
        </div>
      </article>
    </section>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { errorMessage } from '../errors'

const users = ref([])
const loading = ref(false)
const error = ref('')
const unlinking = ref(null)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.get('/api/admin/users')
    users.value = res.data?.users || []
  } catch (e) {
    error.value = errorMessage(e, 'No se pudieron cargar las conexiones')
  } finally {
    loading.value = false
  }
}

function goToUserLogin() {
  window.location.href = '/u/login'
}

async function unlinkTelegram(user) {
  if (!window.confirm(`¿Desvincular Telegram de '${user.username}'?`)) return
  unlinking.value = user.id
  try {
    await api.delete(`/api/admin/users/${user.id}/telegram`)
    await load()
  } catch (e) {
    error.value = errorMessage(e, 'No se pudo desvincular Telegram')
  } finally {
    unlinking.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.user-portal-hint{margin:0 1rem .45rem;color:#8c7d77;font-size:.63rem;line-height:1.45}.user-portal-link{display:inline-block;margin:0 1rem .8rem;border:1px solid rgba(240,90,80,.25);border-radius:.4rem;padding:.36rem .55rem;color:#f29b92;font-size:.62rem;text-decoration:none}.connections-page{background:#100807}.empty-state{display:flex;min-height:8rem;flex-direction:column;align-items:center;justify-content:center;gap:.4rem;border:1px dashed rgba(255,255,255,.13);border-radius:.8rem;color:#887b76;font-size:.78rem}.empty-state b{color:#ded4cf;font-weight:550}.connection-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,25rem),1fr));gap:.85rem}.connection-card{overflow:hidden;border:1px solid rgba(255,255,255,.1);border-radius:.8rem;background:rgba(255,255,255,.025)}.connection-card__head{display:flex;align-items:center;gap:.75rem;padding:1rem;border-bottom:1px solid rgba(255,255,255,.07)}.user-avatar{display:grid;width:2.4rem;height:2.4rem;flex:none;place-items:center;border:1px solid rgba(240,72,65,.22);border-radius:50%;background:rgba(240,72,65,.09);color:#f29a8e;font-size:.72rem;font-weight:700}.user-title{display:flex;min-width:0;flex:1;flex-direction:column;gap:.2rem}.user-title b{color:#fff;font-size:.82rem}.user-title span{overflow:hidden;color:#a99b95;font-size:.68rem;text-overflow:ellipsis;white-space:nowrap}.state-chip{border-radius:999px;padding:.2rem .48rem;font-size:.58rem}.state-chip.active{background:rgba(43,190,130,.1);color:#5bd6a1}.state-chip.inactive{background:rgba(238,72,66,.1);color:#f28e86}.services{padding:.3rem 1rem}.service{display:flex;align-items:center;gap:.7rem;min-height:3.7rem;border-bottom:1px solid rgba(255,255,255,.06)}.service:last-child{border:0}.service-icon{display:grid;width:1.8rem;height:1.8rem;flex:none;place-items:center;border:1px solid rgba(255,255,255,.1);border-radius:.5rem;background:rgba(255,255,255,.04);font-size:.8rem;font-weight:700}.service-icon.google{color:#e8aa72}.service-icon.telegram{color:#7dbfe3}.service-info{display:flex;min-width:0;flex:1;flex-direction:column;gap:.18rem}.service-info b{color:#e8dfdb;font-size:.72rem;font-weight:550}.service-info span{color:#847873;font-size:.64rem}.service-info .warning{color:#d5a860}.connect{flex:none;border:1px solid rgba(240,90,80,.3);border-radius:.4rem;background:rgba(240,80,72,.08);padding:.32rem .55rem;color:#f29b92;font-size:.62rem;text-decoration:none;cursor:pointer}.connect:hover,.user-portal-link:hover{background:rgba(240,80,72,.16)}.service-status{width:.42rem;height:.42rem;flex:none;border-radius:50%;background:#635853}.service-status.ok{background:#51cb94;box-shadow:0 0 8px #51cb9455}.service-status.bad{background:#e96d64}.unlink{border:1px solid rgba(239,68,68,.22);border-radius:.4rem;background:transparent;padding:.32rem .5rem;color:#f29891;font-size:.62rem;cursor:pointer}.unlink:hover{background:rgba(127,29,29,.25)}.unlink:disabled{opacity:.5}
</style>
