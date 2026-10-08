<!--
  InstallHint.vue — Aviso para instalar IGRIS como aplicación.

  Android/Chrome: el navegador avisa con "beforeinstallprompt" cuando la web es
  instalable, y aquí se ofrece un botón que abre su diálogo nativo.

  iPhone/iPad: Safari no dispara ese evento NUNCA. La única forma de instalar es
  manual (Compartir → Añadir a pantalla de inicio), así que se explican los
  pasos. Si no se explica, el usuario no tiene forma de descubrirlo.
-->
<script setup>
import { computed } from 'vue'
import { canInstall, promptInstall, useIsStandalone } from '../pwa'

const isStandalone = useIsStandalone()

const isIos = computed(() => {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  // iPad moderno se identifica como Mac, por eso se comprueba el táctil
  const iPad =
    /iPad/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)
  return /iPhone|iPod/.test(ua) || iPad
})

// El bloque solo aparece si hay algo útil que decir
const visible = computed(() => !isStandalone.value && (canInstall.value || isIos.value))
</script>

<template>
  <div v-if="visible" class="install">
    <template v-if="canInstall">
      <span class="text">Instala Igris en tu teléfono para usarla como una app.</span>
      <button type="button" class="btn" @click="promptInstall">📲 Instalar</button>
    </template>

    <template v-else-if="isIos">
      <span class="text">
        Para instalarla en iPhone: toca <strong>Compartir</strong> y luego
        <strong>Añadir a pantalla de inicio</strong>.
      </span>
    </template>
  </div>
</template>

<style scoped>
.install {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
  margin: 0 auto 16px;
  max-width: 640px;
  padding: 10px 16px;
  border: 1px solid rgba(139, 92, 246, 0.35);
  border-radius: 12px;
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(6px);
  font-size: 0.85rem;
  color: #cbd5e1;
}
.text {
  line-height: 1.4;
}
.btn {
  padding: 6px 14px;
  border: 0;
  border-radius: 999px;
  background: #7c3aed;
  color: #fff;
  font-size: 0.85rem;
  cursor: pointer;
}
.btn:hover {
  background: #8b5cf6;
}
</style>
