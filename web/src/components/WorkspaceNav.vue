<template>
  <nav class="workspace-nav" aria-label="Navegación principal">
    <router-link to="/" class="brand"><span class="brand-mark">✦</span><span>IGRIS</span><small>WORKSPACE</small></router-link>
    <div class="links">
      <router-link to="/" class="link">Chat</router-link>
      <template v-if="admin">
        <router-link to="/config" class="link">Configuración</router-link>
        <router-link to="/panel/conexiones" class="link">Conexiones</router-link>
        <router-link to="/panel/usuarios" class="link">Usuarios</router-link>
      </template>
      <template v-else>
        <router-link to="/conexiones" class="link">Conexiones</router-link><button class="link" type="button" @click="$emit('perception')">Resumen</button>
        <button class="link" type="button" @click="$emit('memory')">Mi memoria</button>
      </template>
    </div>
    <div class="account"><span>{{ username }}</span><button class="logout" @click="$emit('logout')">Salir</button></div>
  </nav>
</template>
<script setup>
defineProps({ admin: Boolean, username: { type: String, default: 'usuario' } })
defineEmits(['logout', 'connections', 'memory', 'perception'])
</script>
<style scoped>
.workspace-nav{position:fixed;z-index:40;inset:0 0 auto;display:flex;align-items:center;gap:2rem;min-height:4.3rem;padding:.7rem clamp(1rem,4vw,3.5rem);border-bottom:1px solid rgba(255,255,255,.09);background:rgba(18,12,12,.83);backdrop-filter:blur(16px);color:#f7f2ef}.brand{display:flex;align-items:center;gap:.55rem;color:#fff;text-decoration:none;font-weight:750;letter-spacing:.12em;font-size:.8rem;white-space:nowrap}.brand-mark{color:#f08072;font-size:1.2rem}.brand small{margin-left:.2rem;padding-left:.7rem;border-left:1px solid #ffffff24;color:#978984;font-size:.53rem;letter-spacing:.16em}.links{display:flex;align-items:center;gap:.25rem;flex:1}.link{border:0;border-radius:.55rem;background:transparent;padding:.55rem .8rem;color:#b9ada8;text-decoration:none;font:inherit;font-size:.78rem;cursor:pointer}.link:hover,.router-link-active.link{background:#ffffff0d;color:white}.account{display:flex;align-items:center;gap:.8rem;color:#c9bfba;font-size:.75rem}.logout{border:1px solid #ffffff20;border-radius:.5rem;background:#ffffff08;padding:.45rem .75rem;color:#eee;font:inherit;cursor:pointer}@media(max-width:760px){.workspace-nav{flex-wrap:wrap;gap:.3rem;padding:.55rem .8rem}.brand{margin-right:auto}.links{order:3;width:100%;overflow:auto}.link{padding:.45rem .6rem;white-space:nowrap}.account{font-size:.68rem}}
</style>
