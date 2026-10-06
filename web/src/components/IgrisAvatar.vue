<!--
  IgrisAvatar.vue — avatar basado en video vertical (mp4 en bucle).
  Ubicación: web/src/components/IgrisAvatar.vue
  Video:     web/public/igris.mp4   (se sirve como /igris.mp4)

  Props (iguales que antes: no hay que tocar IgrisHero ni useIgris)
    state : 'idle' | 'listening' | 'thinking' | 'speaking'
    level : volumen 0..1. Si es -1, se simula.
    size  : ancho en px (el alto se calcula con la proporción 480x800 del video)
-->
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  state: { type: String, default: 'idle' },
  level: { type: Number, default: -1 },
  size: { type: Number, default: 240 },
})

const VIDEO_SRC = '/igris.mp4'
const RATIO = 800 / 480

const LABELS = {
  idle: 'Igris en reposo',
  listening: 'Igris escuchando',
  thinking: 'Igris pensando',
  speaking: 'Igris hablando',
}

// rate: velocidad del video · glow: brillo base · hue: giro de color (grados)
const PROFILE = {
  idle: { rate: 1.0, glow: 1.0, hue: 0 },
  listening: { rate: 1.25, glow: 1.15, hue: 0 },
  thinking: { rate: 0.6, glow: 0.8, hue: 25 },
  speaking: { rate: 1.6, glow: 1.2, hue: -10 },
}

const video = ref(null)
const box = ref(null)
const failed = ref(false)

const reduceMotion =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const cur = { rate: 1, glow: 1, hue: 0, level: 0 }
let raf = 0

function frame(now) {
  const t = now / 1000
  const p = PROFILE[props.state] || PROFILE.idle
  const k = reduceMotion ? 0.3 : 1

  let target = props.level
  if (target < 0) {
    if (props.state === 'speaking') target = 0.5 + 0.4 * Math.sin(t * 7) * Math.sin(t * 2.3)
    else if (props.state === 'listening') target = 0.3 + 0.3 * Math.sin(t * 5.1)
    else if (props.state === 'thinking') target = 0.25 + 0.25 * Math.sin(t * 3.2)
    else target = 0
  }
  target = Math.max(0, Math.min(1, target))

  cur.level += (target - cur.level) * 0.2
  cur.rate += (p.rate - cur.rate) * 0.05
  cur.glow += (p.glow - cur.glow) * 0.08
  cur.hue += (p.hue - cur.hue) * 0.05

  if (video.value) {
    video.value.playbackRate = Math.max(0.25, cur.rate * (reduceMotion ? 0.6 : 1))
  }
  if (box.value) {
    const b = cur.glow + cur.level * 0.5 * k
    const s = 1 + cur.level * 0.025 * k
    box.value.style.filter =
      `brightness(${b.toFixed(2)}) saturate(${(1 + cur.level * 0.35).toFixed(2)}) hue-rotate(${cur.hue.toFixed(1)}deg)`
    box.value.style.transform = `scale(${s.toFixed(3)})`
  }

  raf = requestAnimationFrame(frame)
}

onMounted(() => {
  frame(performance.now())
  // Si el navegador bloquea el autoplay, arranca al primer toque/clic
  const resume = () => video.value?.play().catch(() => {})
  window.addEventListener('pointerdown', resume, { once: true })
})
onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>

<template>
  <div
    class="igris"
    :data-state="state"
    :style="{ width: size + 'px', height: Math.round(size * RATIO) + 'px' }"
    role="img"
    :aria-label="LABELS[state] || LABELS.idle"
  >
    <div ref="box" class="box">
      <video
        v-if="!failed"
        ref="video"
        :src="VIDEO_SRC"
        autoplay
        loop
        muted
        playsinline
        preload="auto"
        @error="failed = true"
      />
      <p v-else class="fallback">No se encontró igris.mp4</p>
    </div>
  </div>
</template>

<style scoped>
.igris {
  position: relative;
  display: block;
  overflow: hidden;
  border-radius: 16px;
  /* Difumina los cuatro bordes para que se funda con el fondo oscuro de la página */
  -webkit-mask-image:
    linear-gradient(to right, transparent, #000 14%, #000 86%, transparent),
    linear-gradient(to bottom, transparent, #000 10%, #000 78%, transparent);
  -webkit-mask-composite: source-in;
  mask-image:
    linear-gradient(to right, transparent, #000 14%, #000 86%, transparent),
    linear-gradient(to bottom, transparent, #000 10%, #000 78%, transparent);
  mask-composite: intersect;
}
.box {
  width: 100%;
  height: 100%;
  will-change: transform, filter;
}
video {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  pointer-events: none;
}
.fallback {
  color: #8b9bb8;
  font-size: 0.8rem;
  text-align: center;
  padding-top: 45%;
}
</style>
