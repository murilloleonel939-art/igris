// useIgris.js — estado compartido entre el chat y el avatar.
// Ubicación sugerida: web/src/composables/useIgris.js
import { reactive } from 'vue'

// state: 'idle' | 'listening' | 'thinking' | 'speaking'
// level: volumen 0..1 (-1 = simulado por el avatar)
export const igris = reactive({ state: 'idle', level: -1 })

export function setIgrisState(state) {
  igris.state = state
  if (state === 'idle' || state === 'thinking') igris.level = -1
}
