// useAudioLevel.js — mide el volumen (0..1) de un micrófono o de un <audio>.
// Ubicación sugerida: web/src/composables/useAudioLevel.js
import { ref, onBeforeUnmount } from 'vue'

export function useAudioLevel() {
  const level = ref(0)
  let ctx = null
  let analyser = null
  let data = null
  let raf = 0

  function tick() {
    analyser.getByteTimeDomainData(data)
    let sum = 0
    for (const v of data) {
      const x = (v - 128) / 128
      sum += x * x
    }
    level.value = Math.min(1, Math.sqrt(sum / data.length) * 3)
    raf = requestAnimationFrame(tick)
  }

  // input: MediaStream (micrófono) o HTMLMediaElement (<audio> con la voz de Igris).
  // Un <audio> solo puede conectarse una vez: guarda la instancia y reutilízala.
  function attach(input) {
    stop()
    ctx = new (window.AudioContext || window.webkitAudioContext)()
    analyser = ctx.createAnalyser()
    analyser.fftSize = 512
    data = new Uint8Array(analyser.fftSize)

    const isStream = typeof MediaStream !== 'undefined' && input instanceof MediaStream
    const source = isStream ? ctx.createMediaStreamSource(input) : ctx.createMediaElementSource(input)
    source.connect(analyser)
    // Con un <audio>, hay que reconectarlo a la salida para que siga sonando
    if (!isStream) analyser.connect(ctx.destination)
    tick()
  }

  function stop() {
    cancelAnimationFrame(raf)
    if (ctx) ctx.close()
    ctx = null
    level.value = 0
  }

  onBeforeUnmount(stop)
  return { level, attach, stop }
}
