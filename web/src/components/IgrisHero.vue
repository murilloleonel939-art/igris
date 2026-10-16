<!--
  IgrisHero.vue — Igris a pantalla completa de fondo + estado en la parte superior.
  Ubicación: web/src/components/IgrisHero.vue
-->
<script setup>
import { computed } from 'vue'
import IgrisAvatar from './IgrisAvatar.vue'
import { igris } from '../composables/useIgris'

const CAPTIONS = {
  idle: 'Listo para servirle, mi señor',
  listening: 'Escuchando…',
  thinking: 'Pensando…',
  speaking: 'Hablando…',
}
const caption = computed(() => CAPTIONS[igris.state] || CAPTIONS.idle)
</script>

<template>
  <div>
    <IgrisAvatar fullscreen :state="igris.state" :level="igris.level" />
    <p class="caption" aria-live="polite">{{ caption }}</p>
  </div>
</template>

<style scoped>
.caption {
  position: fixed;
  top: calc(var(--admin-nav-height, 0px) + 10px);
  left: 0;
  right: 0;
  z-index: 5;
  text-align: center;
  pointer-events: none;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  color: #cbd5e1;
  text-shadow: 0 1px 8px rgba(2, 6, 23, 0.9);
}
</style>
