<!--
  AdminUsers.vue — Panel de usuarios (solo administrador).

  Usa api.js, el mismo cliente con X-Igris-Key que el resto del panel: si el
  administrador ya está dentro, esta pantalla funciona sin volver a pedir nada.

  Los usuarios se crean a mano desde aquí. No hay registro público: nadie puede
  darse de alta por su cuenta.
-->
<template>
  <main class="mx-auto max-w-4xl px-4 py-8 text-slate-200">
    <h1 class="text-2xl font-semibold text-white">Usuarios</h1>
    <p class="mt-1 text-sm text-slate-400">
      Los usuarios entran en <code class="rounded bg-slate-800 px-1.5 py-0.5">/u</code>
      con el usuario y la contraseña que crees aquí.
    </p>

    <!-- Aviso de éxito o error -->
    <p v-if="flash" :class="['mt-4 rounded-lg px-4 py-2 text-sm', flashError ? 'bg-red-900/50 text-red-200' : 'bg-emerald-900/50 text-emerald-200']">
      {{ flash }}
    </p>

    <!-- Alta de usuario -->
    <form class="mt-6 grid gap-3 rounded-xl border border-slate-700 bg-slate-800/60 p-5 sm:grid-cols-2" @submit.prevent="createUser">
      <h2 class="sm:col-span-2 text-lg font-medium text-white">Crear usuario</h2>

      <label class="block text-sm">
        <span class="text-slate-300">Usuario</span>
        <input
          v-model="form.username"
          type="text"
          autocomplete="off"
          placeholder="laura"
          class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
        />
      </label>

      <label class="block text-sm">
        <span class="text-slate-300">Correo</span>
        <input
          v-model="form.email"
          type="email"
          autocomplete="off"
          placeholder="laura@zottagroup.com"
          class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
        />
      </label>

      <label class="block text-sm sm:col-span-2">
        <span class="text-slate-300">Contraseña</span>
        <input
          v-model="form.password"
          type="text"
          autocomplete="new-password"
          placeholder="mínimo 8 caracteres"
          class="mt-1 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-white focus:border-blue-500 focus:outline-none"
        />
        <span class="mt-1 block text-xs text-slate-500">
          Se muestra en claro para que puedas copiarla y dársela al usuario.
        </span>
      </label>

      <div class="sm:col-span-2">
        <h3 class="text-sm font-medium text-slate-300">Funciones que podrá usar</h3>
        <p class="mt-1 text-xs text-slate-500">
          Se pueden cambiar después. Lo que lee o escribe datos ajenos viene apagado a propósito.
        </p>
        <div class="mt-2 grid gap-2 sm:grid-cols-2">
          <label
            v-for="f in features"
            :key="f.key"
            class="flex cursor-pointer items-start gap-2 rounded-lg border border-slate-700 bg-slate-900/60 px-3 py-2"
          >
            <input
              type="checkbox"
              class="mt-0.5 accent-blue-500"
              :checked="form.features.includes(f.key)"
              @change="toggleFormFeature(f.key)"
            />
            <span class="text-xs">
              <span class="block text-slate-200">{{ f.label }}</span>
              <span class="block text-slate-500">{{ f.description }}</span>
              <span v-if="f.requires_google" class="mt-0.5 block text-amber-500/80">
                Necesita que el usuario conecte su Google
              </span>
            </span>
          </label>
        </div>
      </div>

      <div class="sm:col-span-2">
        <button
          type="submit"
          :disabled="saving || !form.username.trim() || !form.email.trim() || form.password.length < 8"
          class="rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {{ saving ? 'Creando…' : 'Crear usuario' }}
        </button>
      </div>
    </form>

    <!-- Lista -->
    <section class="mt-8">
      <h2 class="text-lg font-medium text-white">Usuarios existentes</h2>

      <p v-if="loading" class="mt-3 text-sm text-slate-400">Cargando…</p>
      <p v-else-if="!users.length" class="mt-3 text-sm text-slate-400">Todavía no hay usuarios.</p>

      <div v-else class="mt-3 overflow-x-auto">
        <table class="w-full text-left text-sm">
          <thead class="border-b border-slate-700 text-slate-400">
            <tr>
              <th class="py-2 pr-3">Usuario</th>
              <th class="py-2 pr-3">Correo</th>
              <th class="py-2 pr-3">Estado</th>
              <th class="py-2 pr-3">Funciones y conexiones</th>
              <th class="py-2 pr-3">Creado</th>
              <th class="py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" class="border-b border-slate-800 align-top">
              <td class="py-2 pr-3 font-medium text-white">
                {{ u.username }}
                <span v-if="u.is_admin" class="ml-2 rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-300">admin</span>
              </td>
              <td class="py-2 pr-3">{{ u.email }}</td>
              <td class="py-2 pr-3">
                <span :class="u.is_active ? 'text-emerald-400' : 'text-red-400'">
                  {{ u.is_active ? 'Activo' : 'Desactivado' }}
                </span>
              </td>
              <!-- Qué funciones tiene, y qué tiene conectado -->
              <td class="py-2 pr-3">
                <div class="flex max-w-xs flex-wrap gap-1">
                  <span
                    v-for="f in featureLabels(u)"
                    :key="f"
                    class="rounded bg-slate-700 px-1.5 py-0.5 text-xs text-slate-300"
                  >{{ f }}</span>
                  <span v-if="!u.features?.length" class="text-xs text-slate-500">Ninguna</span>
                </div>
                <div class="mt-1 space-y-0.5 text-xs">
                  <span v-if="u.connections?.google" class="block text-emerald-400/80">
                    Google: {{ u.connections.google }}
                  </span>
                  <span v-else-if="needsGoogle(u)" class="block text-amber-500/80">
                    Google sin conectar
                  </span>
                  <span v-if="u.connections?.google_error" class="block text-red-400/80">
                    Google dio error
                  </span>
                  <span v-if="u.connections?.telegram_linked" class="block text-emerald-400/80">
                    Telegram vinculado
                  </span>
                  <span v-else-if="u.features?.includes('reminders')" class="block text-amber-500/80">
                    Telegram sin vincular
                  </span>
                </div>
              </td>
              <td class="py-2 pr-3 text-slate-400">{{ formatDate(u.created_at) }}</td>
              <td class="py-2">
                <div class="flex flex-wrap gap-2">
                  <button class="act" @click="openPermisos(u)">Permisos</button>
                  <button class="act" @click="toggleActive(u)">
                    {{ u.is_active ? 'Desactivar' : 'Activar' }}
                  </button>
                  <button class="act" @click="resetPassword(u)">Cambiar contraseña</button>
                  <button class="act" @click="openTrato(u)">Editar trato</button>
                  <button class="act danger" @click="removeUser(u)">Eliminar</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
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
          <p class="text-slate-300">
            Telegram:
            <span v-if="permisosModal.connection.telegram_linked" class="text-emerald-400">vinculado</span>
            <span v-else class="text-slate-500">sin vincular</span>
          </p>
          <p class="mt-1 text-xs text-slate-500">
            Esto lo conecta el propio usuario desde su página; aquí solo se ve.
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

const form = ref({ username: '', email: '', password: '', features: [] })

// Modal de permisos
const permisosModal = ref({ open: false, id: null, username: '', features: [], connection: null })
const permisosSaving = ref(false)

// Modal de edición de trato personalizado
const tratoModal = ref({ open: false, id: null, username: '', value: '' })
const tratoSaving = ref(false)

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
      features: form.value.features
    })
    form.value = { username: '', email: '', password: '', features: defaultFeatures() }
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
.act {
  padding: 4px 10px;
  border: 1px solid #475569;
  border-radius: 6px;
  background: rgba(51, 65, 85, 0.6);
  color: #e2e8f0;
  font-size: 0.8rem;
  cursor: pointer;
  white-space: nowrap;
}
.act:hover {
  background: rgba(71, 85, 105, 0.9);
}
.act.danger {
  border-color: #7f1d1d;
  color: #fca5a5;
}
.act.danger:hover {
  background: rgba(127, 29, 29, 0.6);
}
</style>
