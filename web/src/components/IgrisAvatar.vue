<!--
  IgrisAvatar.vue — cabeza de Igris en SVG con la pluma roja animada.
  Ubicación sugerida: web/src/components/IgrisAvatar.vue

  Props
    state : 'idle' | 'listening' | 'thinking' | 'speaking'
    level : volumen 0..1 (micrófono o voz de Igris). Si no se pasa, se simula.
    size  : ancho en px

  Uso
    <IgrisAvatar :state="estado" :level="nivel" :size="240" />
-->
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  state: { type: String, default: 'idle' },
  level: { type: Number, default: -1 },
  size: { type: Number, default: 240 },
})

const LABELS = {
  idle: 'Igris en reposo',
  listening: 'Igris escuchando',
  thinking: 'Igris pensando',
  speaking: 'Igris hablando',
}

// amp: amplitud del ondeo · speed: velocidad · eye: brillo base de los ojos · lean: inclinación hacia atrás
const PROFILE = {
  idle: { amp: 5, speed: 1.1, eye: 0.4, lean: 22 },
  listening: { amp: 8, speed: 1.7, eye: 0.7, lean: 10 },
  thinking: { amp: 11, speed: 1.3, eye: 0.5, lean: 26 },
  speaking: { amp: 9, speed: 2.6, eye: 0.6, lean: 20 },
}

const head = ref(null)
const plumeBack = ref(null)
const plumeFront = ref(null)
const eyes = ref(null)

const reduceMotion =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

const cur = { amp: 5, speed: 1.1, eye: 0.4, lean: 22, level: 0 }
let raf = 0

const N = 22
const BASE_X = 100
const BASE_Y = 42

// Construye el contorno de la pluma: una columna que ondea y se afina hacia la punta.
function plume(t, { amp, speed, phase, width, lean, length }) {
  const spine = []
  for (let i = 0; i <= N; i++) {
    const s = i / N
    const y = BASE_Y - length * s * (1 - 0.1 * s)
    const x = BASE_X + lean * s * s + Math.sin(t * speed - s * 3.2 + phase) * amp * s * s
    spine.push([x, y, s])
  }
  const left = []
  const right = []
  spine.forEach(([x, y, s], i) => {
    const a = spine[Math.max(i - 1, 0)]
    const b = spine[Math.min(i + 1, N)]
    const dx = b[0] - a[0]
    const dy = b[1] - a[1]
    const len = Math.hypot(dx, dy) || 1
    const nx = -dy / len
    const ny = dx / len
    const w = (12 * Math.sin(Math.PI * Math.pow(s, 0.75)) * (1 - 0.3 * s) + 2.5 * (1 - s)) * width
    left.push(`${(x + nx * w).toFixed(1)} ${(y + ny * w).toFixed(1)}`)
    right.push(`${(x - nx * w).toFixed(1)} ${(y - ny * w).toFixed(1)}`)
  })
  return `M${left.join('L')}L${right.reverse().join('L')}Z`
}

function frame(now) {
  const t = now / 1000
  const p = PROFILE[props.state] || PROFILE.idle
  const k = reduceMotion ? 0.25 : 1

  // Volumen real o simulado
  let target = props.level
  if (target < 0) {
    if (props.state === 'speaking') target = 0.5 + 0.4 * Math.sin(t * 7) * Math.sin(t * 2.3)
    else if (props.state === 'listening') target = 0.3 + 0.3 * Math.sin(t * 5.1)
    else target = 0
  }
  target = Math.max(0, Math.min(1, target))

  // Suavizado para que los cambios de estado no sean bruscos
  cur.level += (target - cur.level) * 0.2
  cur.amp += (p.amp - cur.amp) * 0.06
  cur.speed += (p.speed - cur.speed) * 0.06
  cur.eye += (p.eye - cur.eye) * 0.08
  cur.lean += (p.lean - cur.lean) * 0.06

  const amp = (cur.amp + cur.level * 30) * k

  plumeBack.value?.setAttribute(
    'd',
    plume(t, { amp: amp * 0.8, speed: cur.speed, phase: 0.9, width: 1.15, lean: cur.lean + 6, length: 112 }),
  )
  plumeFront.value?.setAttribute(
    'd',
    plume(t, { amp, speed: cur.speed, phase: 0, width: 0.85, lean: cur.lean, length: 125 }),
  )

  // Brillo de los ojos: respira en reposo, pulsa al pensar, sigue la voz al hablar
  let glow = cur.eye
  if (props.state === 'thinking') glow += 0.35 * Math.sin(t * 3.2)
  else if (props.state === 'idle') glow += 0.08 * Math.sin(t * 1.1)
  else glow += cur.level * 0.4
  if (eyes.value) eyes.value.style.opacity = Math.max(0.15, Math.min(1, glow)).toFixed(2)

  head.value?.setAttribute(
    'transform',
    `translate(0 ${reduceMotion ? 0 : (Math.sin(t * 1.3) * 1.4).toFixed(2)})`,
  )

  raf = requestAnimationFrame(frame)
}

onMounted(() => frame(performance.now()))
onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>

<template>
  <svg
    class="igris"
    :data-state="state"
    :width="size"
    :height="(size * 370) / 240"
    viewBox="-20 -110 240 370"
    role="img"
    :aria-label="LABELS[state] || LABELS.idle"
  >
    <defs>
      <linearGradient id="igris-shell" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" style="stop-color: var(--shell-hi)" />
        <stop offset="1" style="stop-color: var(--shell-lo)" />
      </linearGradient>
      <linearGradient id="igris-plume-back" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0" style="stop-color: var(--plume-lo)" />
        <stop offset="1" style="stop-color: var(--plume-mid)" />
      </linearGradient>
      <linearGradient id="igris-plume-front" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0" style="stop-color: var(--plume-mid)" />
        <stop offset="1" style="stop-color: var(--plume-hi)" />
      </linearGradient>
      <filter id="igris-glow" x="-60%" y="-200%" width="220%" height="500%">
        <feGaussianBlur stdDeviation="3.5" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>

    <g ref="head">
      <!-- Gola -->
      <path d="M62 200 C70 232 130 232 138 200 L152 252 L48 252 Z" fill="url(#igris-shell)" class="edge" />

      <!-- Yelmo -->
      <path
        d="M52 122 C52 62 76 34 100 34 C124 34 148 62 148 122 L148 168 C148 198 126 220 100 228 C74 220 52 198 52 168 Z"
        fill="url(#igris-shell)"
        class="edge"
      />
      <path d="M60 120 C60 70 80 46 100 43" class="rim" fill="none" />

      <!-- Visera -->
      <path
        d="M54 98 L146 98 L146 136 C128 142 112 144 100 150 C88 144 72 142 54 136 Z"
        class="void"
      />
      <g ref="eyes" filter="url(#igris-glow)" class="eyes">
        <polygon points="64,110 91,119 89,126 66,120" />
        <polygon points="136,110 109,119 111,126 134,120" />
      </g>

      <!-- Cresta y rejilla -->
      <path d="M100 43 L100 96" class="rim" fill="none" stroke-width="3" />
      <g class="grille">
        <path d="M84 158 V186 M92 160 V194 M100 161 V198 M108 160 V194 M116 158 V186" />
      </g>
      <circle cx="62" cy="150" r="2" class="rivet" />
      <circle cx="138" cy="150" r="2" class="rivet" />

      <!-- Pluma roja -->
      <path ref="plumeBack" fill="url(#igris-plume-back)" />
      <path ref="plumeFront" fill="url(#igris-plume-front)" />

      <!-- Soporte de la pluma -->
      <path d="M87 40 L113 40 L108 53 L92 53 Z" class="mount edge" />
    </g>
  </svg>
</template>

<style scoped>
.igris {
  --shell-hi: #3b3950;
  --shell-lo: #15141d;
  --edge: #4d4a6b;
  --void: #0b0a11;
  --plume-lo: #6e0a1c;
  --plume-mid: #c01531;
  --plume-hi: #ff4560;
  --eye: #b9a4ff;
  display: block;
  overflow: visible;
}

.edge {
  stroke: var(--edge);
  stroke-width: 1;
}
.rim {
  stroke: var(--edge);
  stroke-width: 2;
  stroke-linecap: round;
  opacity: 0.7;
}
.void {
  fill: var(--void);
}
.eyes polygon {
  fill: var(--eye);
}
.grille path {
  stroke: var(--void);
  stroke-width: 3;
  stroke-linecap: round;
  fill: none;
}
.rivet {
  fill: var(--edge);
}
.mount {
  fill: #3a3852;
}
</style>
