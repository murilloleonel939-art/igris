<!--
  AdminUsers.vue — Panel de usuarios (solo administrador).

  Usa api.js, el mismo cliente con X-Igris-Key que el resto del panel: si el
  administrador ya está dentro, esta pantalla funciona sin volver a pedir nada.

  Los usuarios se crean a mano desde aquí. No hay registro público: nadie puede
  darse de alta por su cuenta.
-->
<template>
  <main class="users-page mx-auto min-h-screen w-full max-w-6xl px-5 py-8 text-stone-200 sm:px-8 lg:px-12 lg:py-11">
    <header class="mb-8 border-b border-white/10 pb-7">
      <div class="mb-4 flex items-center gap-2 text-[11px] text-stone-500"><span>Workspace</span><span>›</span><span class="text-stone-300">Usuarios</span></div>
      <div class="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
        <div><h1 class="text-3xl font-semibold tracking-tight text-white">Usuarios</h1><p class="mt-2 max-w-2xl text-sm text-stone-400">Administra cuentas, permisos y conexiones de tu workspace.</p></div>
        <span class="users-count"><span class="count-dot"></span>{{ users.length }} {{ users.length === 1 ? 'usuario' : 'usuarios' }}</span>
      </div>
    </header>

    <p v-if="flash" :class="['mb-5 rounded-lg border px-4 py-3 text-sm', flashError ? 'border-red-500/25 bg-red-950/30 text-red-200' : 'border-emerald-500/25 bg-emerald-950/20 text-emerald-200']">{{ flash }}</p>

    <form class="create-panel" @submit.prevent="createUser">
      <div class="create-heading"><span class="create-icon">＋</span><div><h2 class="text-base font-semibold text-white">Crear usuario</h2><p class="mt-1 text-xs text-stone-400">Crea una cuenta y define qué funciones podrá utilizar.</p></div></div>
      <div class="form-grid">
        <label class="field-label"><span>Usuario</span><input v-model="form.username" type="text" autocomplete="off" placeholder="laura" class="field-input" /></label>
        <label class="field-label"><span>Correo electrónico</span><input v-model="form.email" type="email" autocomplete="off" placeholder="laura@ejemplo.com" class="field-input" /></label>
        <label class="field-label"><span>Contraseña</span><input v-model="form.password" type="text" autocomplete="new-password" placeholder="Mínimo 8 caracteres" class="field-input" /><small>Se muestra para que puedas copiarla y compartirla.</small></label>
        <label class="admin-check"><input v-model="form.is_admin" type="checkbox" /><span><b>Permisos de administrador</b><small>Podrá acceder al panel y gestionar usuarios.</small></span></label>
      </div>
      <div class="feature-section"><h3 class="text-sm font-semibold text-white">Funciones disponibles</h3><p class="mt-1 text-xs text-stone-500">Puedes modificarlas después. Las funciones que acceden a datos externos vienen desactivadas por defecto.</p>
        <div class="mt-3 grid gap-2 sm:grid-cols-2">
          <label v-for="f in features" :key="f.key" class="feature-option"><input type="checkbox" :checked="form.features.includes(f.key)" @change="toggleFormFeature(f.key)" /><span><b>{{ f.label }}</b><small>{{ f.description }}</small><em v-if="f.requires_google">Requiere conectar Google</em></span></label>
        </div>
      </div>
      <div class="mt-5 flex justify-end"><button type="submit" :disabled="saving || !form.username.trim() || !form.email.trim() || form.password.length < 8" class="primary-action">{{ saving ? 'Creando…' : '＋ Crear usuario' }}</button></div>
    </form>

    <section class="mt-9">
      <div class="mb-4 flex items-end justify-between gap-4"><div><h2 class="text-lg font-semibold text-white">Usuarios existentes</h2><p class="mt-1 text-xs text-stone-500">Cuentas, permisos y servicios conectados.</p></div><span v-if="!loading" class="text-xs text-stone-500">{{ users.length }} en total</span></div>
      <div v-if="loading" class="empty-state">Cargando usuarios…</div>
      <div v-else-if="!users.length" class="empty-state"><span class="empty-icon">♧</span><b>Aún no hay usuarios</b><span>Crea la primera cuenta con el formulario de arriba.</span></div>
      <div v-else class="user-list">
        <article v-for="u in users" :key="u.id" class="user-card">
          <div class="user-card__main">
            <div class="avatar-initials">{{ u.username.slice(0, 2).toUpperCase() }}</div>
            <div class="user-identity"><div class="flex flex-wrap items-center gap-2"><h3>{{ u.username }}</h3><span v-if="u.is_admin" class="role-chip">ADMIN</span><span class="state-chip" :class="u.is_active ? 'is-active' : 'is-disabled'"><i></i>{{ u.is_active ? 'Activo' : 'Desactivado' }}</span></div><p>{{ u.email }}</p><small>Creado {{ formatDate(u.created_at) }}</small></div>
            <div class="user-actions"><button class="act" @click="openPermisos(u)">Permisos</button><button class="act" @click="openMemory(u)">Memoria</button><button class="act" @click="toggleActive(u)">{{ u.is_active ? 'Desactivar' : 'Activar' }}</button><button class="act" @click="resetPassword(u)">Cambiar contraseña</button><button class="act" @click="openTrato(u)">Editar trato</button><button class="act danger" @click="removeUser(u)">Eliminar</button></div>
          </div>
          <div class="user-card__details"><div class="detail-group"><span class="detail-label">FUNCIONES</span><div class="flex flex-wrap gap-1.5"><span v-for="f in featureLabels(u)" :key="f" class="feature-chip">{{ f }}</span><span v-if="!u.features?.length" class="text-xs text-stone-500">Sin funciones habilitadas</span></div></div>
            <div class="connection-list"><span v-if="u.connections?.google" class="connection-chip connected">Google · {{ u.connections.google }}</span><span v-else-if="needsGoogle(u)" class="connection-chip pending">Google sin conectar</span><span v-if="u.connections?.google_error" class="connection-chip failed">Error de Google</span><span v-if="u.connections?.telegram_linked" class="connection-chip connected">Telegram vinculado</span><span v-else-if="u.features?.includes('reminders')" class="connection-chip pending">Telegram sin vincular</span></div>
          </div>
        </article>
      </div>
    </section>

    <!-- Modal: permisos del usuario -->
    <div v-if="permisosModal.open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div class="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <h3 class="mb-1 text-lg font-medium text-white">Funciones de {{ permisosModal.username }}</h3>
        <p class="mb-4 text-sm text-slate-400">
          Igris solo ofrecerá lo que marques aquí. Lo que no esté marcado no lo puede usar,
          aunque se lo pida de otra forma.
        </p>

        <div class="space-y-2">
          <label
            v-for="f in features"
            :key="f.key"
            class="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2"
          >
            <input v-model="permisosModal.features" type="checkbox" :value="f.key" class="mt-0.5 accent-blue-500" />
            <span class="text-sm">
              <span class="block text-slate-200">{{ f.label }}</span>
              <span class="block text-xs text-slate-500">{{ f.description }}</span>
              <span v-if="f.requires_google" class="mt-0.5 block text-xs text-amber-500/80">
                Necesita que el usuario conecte su Google en su propia página.
              </span>
            </span>
          </label>
        </div>

        <!-- Estado de las conexiones del usuario -->
        <div v-if="permisosModal.connection" class="mt-4 rounded-lg border border-slate-700 bg-slate-800/40 p-3 text-sm">
          <p class="text-slate-300">
            Google:
            <span v-if="permisosModal.connection.google" class="text-emerald-400">
              conectado ({{ permisosModal.connection.google }})
            </span>
            <span v-else class="text-slate-500">sin conectar</span>
          </p>
          <div class="flex items-center justify-between">
            <p class="text-slate-300">
              Telegram:
              <span v-if="permisosModal.connection.telegram_linked" class="text-emerald-400">vinculado</span>
              <span v-else class="text-slate-500">sin vincular</span>
            </p>
            <button
              v-if="permisosModal.connection.telegram_linked"
              :disabled="unlinkingTelegram"
              class="rounded px-2 py-0.5 text-xs font-medium text-red-400 ring-1 ring-red-400/40 hover:bg-red-400/10 disabled:opacity-50"
              @click="adminUnlinkTelegram(permisosModal.id)"
            >
              {{ unlinkingTelegram ? 'Desvinculando…' : 'Desvincular' }}
            </button>
          </div>
          <p class="mt-1 text-xs text-slate-500">
            Esto lo conecta el propio usuario desde su página. Puedes desvincular su Telegram desde aquí.
          </p>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button class="act" @click="permisosModal.open = false">Cancelar</button>
          <button
            class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
            :disabled="permisosSaving"
            @click="savePermisos"
          >
            {{ permisosSaving ? 'Guardando…' : 'Guardar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: memoria del usuario -->
    <div v-if="memoryModal.open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div class="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <div class="mb-5 flex items-start justify-between gap-4">
          <div><h3 class="text-lg font-medium text-white">Memoria de {{ memoryModal.username }}</h3><p class="mt-1 text-sm text-slate-400">Solo lectura de los recuerdos guardados para esta cuenta.</p></div>
          <button class="act" @click="memoryModal.open = false">Cerrar</button>
        </div>
        <p v-if="memoryModal.loading" class="text-sm text-slate-400">Cargando memoria…</p>
        <p v-else-if="memoryModal.error" class="text-sm text-red-300">{{ memoryModal.error }}</p>
        <div v-else class="memory-columns grid gap-4 md:grid-cols-2">
          <section v-for="group in memoryGroups" :key="group.key" class="rounded-lg border border-slate-700 bg-slate-800/40 p-4">
            <h4 class="mb-3 text-sm font-semibold text-white">{{ group.label }}</h4>
            <div v-if="!memoryModal.items[group.key].length" class="text-xs text-slate-500">Sin recuerdos guardados.</div>
            <div v-for="item in memoryModal.items[group.key]" :key="item.id" class="mb-2 rounded border border-slate-700 px-3 py-2 text-sm text-slate-300">{{ item.content }}</div>
          </section>
        </div>
      </div>
    </div>

    <!-- Modal: editar trato personalizado -->    <div v-if="tratoModal.open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div class="w-full max-w-lg rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
        <h3 class="mb-1 text-lg font-medium text-white">Trato personalizado</h3>
        <p class="mb-4 text-sm text-slate-400">
          Cómo debe dirigirse Igris a <strong class="text-slate-200">{{ tratoModal.username }}</strong>.
          Déjalo vacío para usar el trato global ("mi señor").
        </p>
        <textarea
          v-model="tratoModal.value"
          rows="5"
          placeholder='Ej: La usuaria se llama Diana. Dirígete a ella por su nombre con tono cordial. No uses "señor" ni tratamientos masculinos.'
          class="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-blue-500 focus:outline-none"
        />
        <div class="mt-4 flex justify-end gap-2">
          <button class="act" @click="tratoModal.open = false">Cancelar</button>
          <button
            class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
            :disabled="tratoSaving"
            @click="saveTrato"
          >
            {{ tratoSaving ? 'Guardando…' : 'Guardar' }}
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { errorMessage } from '../errors'

const users = ref([])
const loading = ref(false)
const saving = ref(false)
const flash = ref('')
const flashError = ref(false)

// Catálogo de funciones, tal como lo publica el backend (/api/admin/features).
// Se carga de ahí en vez de tenerlo escrito aquí: así, si se añade una función
// nueva en el servidor, aparece sola en el panel.
const features = ref([])

// Valores por defecto de una cuenta nueva (los que marque el backend como tales).
const defaultFeatures = () => features.value.filter((f) => f.default).map((f) => f.key)

const form = ref({ username: '', email: '', password: '', is_admin: false, features: [] })

// Modal de permisos
const permisosModal = ref({ open: false, id: null, username: '', features: [], connection: null })
const permisosSaving = ref(false)
const unlinkingTelegram = ref(false)

// Modal de edición de trato personalizado
const tratoModal = ref({ open: false, id: null, username: '', value: '' })
const tratoSaving = ref(false)
const memoryGroups = [{ key: 'personal', label: 'Memoria personal' }, { key: 'operational', label: 'Memoria operativa' }]
const memoryModal = ref({ open: false, loading: false, error: '', id: null, username: '', items: { personal: [], operational: [] } })

function featureLabels(u) {
  const keys = u.features || []
  return keys
    .map((k) => features.value.find((f) => f.key === k)?.label || k)
}

// ¿Tiene alguna función de Google activada y sin conectar? Sirve para avisar.
function needsGoogle(u) {
  const keys = u.features || []
  return keys.some((k) => features.value.find((f) => f.key === k)?.requires_google)
}

function toggleFormFeature(key) {
  const list = form.value.features
  const i = list.indexOf(key)
  if (i === -1) list.push(key)
  else list.splice(i, 1)
}

let flashTimer = 0
function showFlash(msg, isError = false) {
  flash.value = msg
  flashError.value = isError
  clearTimeout(flashTimer)
  if (msg) flashTimer = setTimeout(() => (flash.value = ''), 8000)
}

function formatDate(value) {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleDateString('es-CO')
  } catch {
    return '—'
  }
}

async function loadFeatures() {
  try {
    const res = await api.get('/api/admin/features')
    features.value = res.data?.features || []
    // El formulario de alta empieza con las funciones de fábrica.
    form.value.features = defaultFeatures()
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudo cargar la lista de funciones'), true)
  }
}

async function load() {
  loading.value = true
  try {
    const res = await api.get('/api/admin/users')
    users.value = res.data?.users || []
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudieron cargar los usuarios'), true)
  } finally {
    loading.value = false
  }
}

async function createUser() {
  if (saving.value) return
  saving.value = true
  // Se guarda antes de recargar: load() limpia el aviso, así que el mensaje
  // tiene que mostrarse DESPUÉS de que la lista se haya actualizado.
  const created = form.value.username.trim()

  try {
    await api.post('/api/admin/users', {
      username: created,
      email: form.value.email.trim(),
      password: form.value.password,
      is_admin: form.value.is_admin,
      features: form.value.features
    })
    form.value = { username: '', email: '', password: '', is_admin: false, features: defaultFeatures() }
    await load()
    showFlash(`Usuario '${created}' creado. Ya puede entrar en /u`)
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudo crear el usuario'), true)
  } finally {
    saving.value = false
  }
}

function openPermisos(u) {
  permisosModal.value = {
    open: true,
    id: u.id,
    username: u.username,
    features: [...(u.features || [])],
    connection: u.connections || null,
  }
}

async function adminUnlinkTelegram(userId) {
  unlinkingTelegram.value = true
  try {
    await api.delete(`/api/admin/users/${userId}/telegram`)
    // Actualiza el estado local sin cerrar el modal
    if (permisosModal.value.connection) {
      permisosModal.value.connection.telegram_linked = false
      permisosModal.value.connection.telegram = null
    }
    await load()
  } catch (e) {
    alert(e?.response?.data?.detail || 'Error al desvincular Telegram')
  } finally {
    unlinkingTelegram.value = false
  }
}

async function savePermisos() {
  permisosSaving.value = true
  try {
    await api.put(`/api/admin/users/${permisosModal.value.id}`, {
      features: permisosModal.value.features,
    })
    const nombre = permisosModal.value.username
    await load()
    permisosModal.value.open = false
    showFlash(`Funciones de '${nombre}' actualizadas`)
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudieron guardar las funciones'), true)
  } finally {
    permisosSaving.value = false
  }
}

async function toggleActive(u) {
  try {
    await api.put(`/api/admin/users/${u.id}`, { is_active: !u.is_active })
    await load()
    showFlash(`Usuario '${u.username}' ${u.is_active ? 'desactivado' : 'activado'}`)
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudo cambiar el estado'), true)
  }
}

async function resetPassword(u) {
  const nueva = window.prompt(`Nueva contraseña para '${u.username}' (mínimo 8 caracteres):`)
  if (nueva === null) return
  if (nueva.length < 8) {
    showFlash('La contraseña debe tener al menos 8 caracteres', true)
    return
  }
  try {
    await api.put(`/api/admin/users/${u.id}`, { password: nueva })
    await load()
    showFlash(`Contraseña de '${u.username}' actualizada`)
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudo cambiar la contraseña'), true)
  }
}

async function removeUser(u) {
  if (!window.confirm(`¿Eliminar al usuario '${u.username}'? Esta acción no se puede deshacer.`)) return
  try {
    await api.delete(`/api/admin/users/${u.id}`)
    await load()
    showFlash(`Usuario '${u.username}' eliminado`)
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudo eliminar el usuario'), true)
  }
}

async function openMemory(u) {
  memoryModal.value = { open: true, loading: true, error: '', id: u.id, username: u.username, items: { personal: [], operational: [] } }
  try {
    const res = await api.get(`/api/admin/users/${u.id}/memories`)
    memoryModal.value.items = { personal: res.data?.personal || [], operational: res.data?.operational || [] }
  } catch (e) {
    memoryModal.value.error = errorMessage(e, 'No se pudo cargar la memoria')
  } finally {
    memoryModal.value.loading = false
  }
}

function openTrato(u) {
  tratoModal.value = {
    open: true,
    id: u.id,
    username: u.username,
    value: u.addressing_instruction || '',
  }
}

async function saveTrato() {
  tratoSaving.value = true
  try {
    await api.put(`/api/admin/users/${tratoModal.value.id}`, {
      addressing_instruction: tratoModal.value.value,
    })
    await load()
    tratoModal.value.open = false
    showFlash(`Trato de '${tratoModal.value.username}' actualizado`)
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudo guardar el trato'), true)
  } finally {
    tratoSaving.value = false
  }
}

onMounted(async () => {
  await loadFeatures()
  await load()
})
</script>

<style scoped>
.users-page{background:#100807;min-height:calc(100vh - var(--admin-nav-height, 0px))}users-count{display:inline-flex;align-items:center;gap:.45rem;border:1px solid rgba(255,255,255,.1);border-radius:999px;padding:.45rem .75rem;color:#c7b8b0;font-size:.72rem}.count-dot{width:.38rem;height:.38rem;border-radius:50%;background:#ed5149;box-shadow:0 0 10px #ed514966}.create-panel{border:1px solid rgba(255,255,255,.1);border-radius:.9rem;background:linear-gradient(135deg,rgba(255,255,255,.035),rgba(255,255,255,.012));padding:1.25rem}.create-heading{display:flex;align-items:center;gap:.75rem;border-bottom:1px solid rgba(255,255,255,.08);padding-bottom:1rem}.create-icon{display:grid;width:2.25rem;height:2.25rem;place-items:center;border:1px solid rgba(240,72,65,.3);border-radius:.65rem;background:rgba(240,72,65,.1);color:#f06a62;font-size:1.3rem}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin-top:1.1rem}.field-label{display:flex;flex-direction:column;gap:.4rem;color:#d4c7c1;font-size:.75rem}.field-label small,.admin-check small{color:#847873;font-size:.65rem;line-height:1.4}.field-input{width:100%;border:1px solid rgba(255,255,255,.12);border-radius:.55rem;background:#160e0d;padding:.65rem .75rem;color:#fff;font-size:.82rem;outline:none;transition:.2s}.field-input:focus{border-color:#eb514a;box-shadow:0 0 0 2px rgba(235,81,74,.12)}.field-input::placeholder{color:#655954}.admin-check{display:flex;align-items:center;gap:.65rem;align-self:end;min-height:2.5rem;color:#eee5e1}.admin-check input,.feature-option input{accent-color:#ef5149}.admin-check b,.admin-check small,.feature-option b,.feature-option small,.feature-option em{display:block}.admin-check b{font-size:.74rem;font-weight:500}.feature-section{margin-top:1.2rem;border-top:1px solid rgba(255,255,255,.08);padding-top:1rem}.feature-option{display:flex;align-items:flex-start;gap:.6rem;border:1px solid rgba(255,255,255,.08);border-radius:.6rem;background:rgba(0,0,0,.12);padding:.65rem;cursor:pointer}.feature-option:hover{border-color:rgba(255,255,255,.18)}.feature-option input{margin-top:.13rem}.feature-option b{color:#e8dfdb;font-size:.72rem;font-weight:550}.feature-option small{margin-top:.15rem;color:#847873;font-size:.64rem;line-height:1.4}.feature-option em{margin-top:.2rem;color:#daa564;font-size:.62rem;font-style:normal}.primary-action{border-radius:.55rem;background:#ee4842;padding:.65rem 1rem;color:#fff;font-size:.78rem;font-weight:600;transition:.2s}.primary-action:hover:not(:disabled){background:#ff5b55}.primary-action:disabled{cursor:not-allowed;opacity:.45}.empty-state{display:flex;min-height:8rem;flex-direction:column;align-items:center;justify-content:center;gap:.4rem;border:1px dashed rgba(255,255,255,.13);border-radius:.8rem;color:#887b76;font-size:.78rem}.empty-state b{color:#ded4cf;font-weight:550}.empty-icon{color:#e3655e;font-size:1.35rem}.user-list{display:grid;gap:.75rem}.user-card{overflow:hidden;border:1px solid rgba(255,255,255,.1);border-radius:.8rem;background:rgba(255,255,255,.025)}.user-card__main{display:grid;grid-template-columns:auto minmax(10rem,1fr) minmax(15rem,auto);align-items:center;gap:.85rem;padding:1rem}.avatar-initials{display:grid;width:2.5rem;height:2.5rem;place-items:center;border:1px solid rgba(240,72,65,.22);border-radius:50%;background:rgba(240,72,65,.09);color:#f29a8e;font-size:.75rem;font-weight:700}.user-identity h3{color:#fff;font-size:.88rem;font-weight:600}.user-identity p{margin-top:.2rem;color:#b1a39d;font-size:.72rem}.user-identity small{display:block;margin-top:.2rem;color:#766b67;font-size:.62rem}.role-chip{border-radius:999px;background:rgba(238,72,66,.13);padding:.18rem .42rem;color:#f49a91;font-size:.55rem;font-weight:700;letter-spacing:.06em}.state-chip{display:inline-flex;align-items:center;gap:.3rem;border-radius:999px;padding:.18rem .45rem;font-size:.6rem}.state-chip i{width:.3rem;height:.3rem;border-radius:50%;background:currentColor}.is-active{background:rgba(43,190,130,.1);color:#5bd6a1}.is-disabled{background:rgba(238,72,66,.1);color:#f28e86}.user-actions{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:.35rem}.act{border:1px solid rgba(255,255,255,.13);border-radius:.45rem;background:rgba(255,255,255,.035);padding:.38rem .55rem;color:#d6cbc6;font-size:.66rem;cursor:pointer;white-space:nowrap;transition:.2s}.act:hover{border-color:rgba(255,255,255,.25);background:rgba(255,255,255,.08);color:#fff}.act.danger{border-color:rgba(239,68,68,.25);color:#f29891}.act.danger:hover{background:rgba(127,29,29,.3)}.user-card__details{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:.75rem;border-top:1px solid rgba(255,255,255,.07);background:rgba(0,0,0,.12);padding:.7rem 1rem}.detail-group{display:flex;flex-wrap:wrap;align-items:center;gap:.55rem}.detail-label{color:#847873;font-size:.55rem;font-weight:700;letter-spacing:.1em}.feature-chip{border-radius:.3rem;background:rgba(255,255,255,.07);padding:.2rem .4rem;color:#c5b8b2;font-size:.6rem}.connection-list{display:flex;flex-wrap:wrap;gap:.35rem}.connection-chip{border:1px solid transparent;border-radius:999px;padding:.2rem .48rem;font-size:.58rem}.connection-chip.connected{border-color:rgba(43,190,130,.15);background:rgba(43,190,130,.07);color:#68ce9e}.connection-chip.pending{border-color:rgba(228,166,84,.18);background:rgba(228,166,84,.06);color:#d5a860}.connection-chip.failed{border-color:rgba(239,68,68,.2);background:rgba(239,68,68,.06);color:#ec8e87}
:deep(.fixed.inset-0 > div){border-color:rgba(255,255,255,.12);background:#160e0d}.act + .bg-blue-600,.bg-blue-600{background:#ee4842}.bg-blue-600:hover{background:#ff5b55}.focus\\:border-blue-500:focus{border-color:#ee4842}
@media(max-width:900px){.memory-columns{grid-template-columns:1fr}.user-card__main{grid-template-columns:auto 1fr}.user-actions{grid-column:1/-1;justify-content:flex-start}.user-card__details{align-items:flex-start;flex-direction:column}}
@media(max-width:560px){.form-grid{grid-template-columns:1fr}.admin-check{align-self:auto}.create-panel{padding:1rem}.user-card__main{gap:.65rem;padding:.8rem}.user-actions .act{font-size:.62rem}.user-card__details{padding:.65rem .8rem}}
</style>
