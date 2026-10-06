<!--
  IgrisHero.vue — cabeza de Igris centrada sobre el chat (opción A).
  Ubicación sugerida: web/src/components/IgrisHero.vue
  Colócalo justo encima del chat:  <IgrisHero />
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
  <section class="hero">
    <IgrisAvatar :state="igris.state" :level="igris.level" :size="180" />
    <p class="caption" aria-live="polite">{{ caption }}</p>
  </section>
</template>

<style scoped>
.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0 4px;
}
.caption {
  margin: 4px 0 0;
  font-size: 0.9rem;
  color: #8b9bb8;
}
@media (max-width: 640px) {
  .hero :deep(svg) {
    width: 140px;
    height: auto;
  }
}
</style>
