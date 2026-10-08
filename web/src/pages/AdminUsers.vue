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
              <th class="py-2 pr-3">Creado</th>
              <th class="py-2">Acciones</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" class="border-b border-slate-800">
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
              <td class="py-2 pr-3 text-slate-400">{{ formatDate(u.created_at) }}</td>
              <td class="py-2">
                <div class="flex flex-wrap gap-2">
                  <button class="act" @click="toggleActive(u)">
                    {{ u.is_active ? 'Desactivar' : 'Activar' }}
                  </button>
                  <button class="act" @click="resetPassword(u)">Cambiar contraseña</button>
                  <button class="act danger" @click="removeUser(u)">Eliminar</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
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

const form = ref({ username: '', email: '', password: '' })

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
      password: form.value.password
    })
    form.value = { username: '', email: '', password: '' }
    await load()
    showFlash(`Usuario '${created}' creado. Ya puede entrar en /u`)
  } catch (e) {
    showFlash(errorMessage(e, 'No se pudo crear el usuario'), true)
  } finally {
    saving.value = false
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

onMounted(load)
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
