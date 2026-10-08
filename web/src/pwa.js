/**
 * pwa.js — Instalación de IGRIS como aplicación (PWA).
 *
 * Un navegador solo permite instalar la web si se cumplen tres cosas:
 *   1. Hay un manifest con nombre, iconos y display: standalone.
 *   2. Hay un service worker registrado en el ámbito ("scope") de la página.
 *   3. Se sirve por HTTPS (o en localhost).
 *
 * El service worker solo se registra en producción. En desarrollo estorba:
 * guarda en caché el HTML y los módulos, y al recargar se siguen viendo
 * versiones antiguas del código.
 */
import { ref, computed } from 'vue'

// Evento que dispara el navegador cuando la app SE PUEDE instalar. Solo llega
// si no está instalada ya y si el manifest + service worker son correctos.
const deferredPrompt = ref(null)
const isStandalone = ref(false)
const installed = ref(false)

// ¿Se puede mostrar el botón "Instalar"?
export const canInstall = computed(() => !!deferredPrompt.value)

export function useIsStandalone() {
  return isStandalone
}

export function useInstalled() {
  return installed
}

function detectStandalone() {
  if (typeof window === 'undefined') return false
  // iOS no soporta display-mode en navegadores antiguos: navigator.standalone
  // es la forma de saber si se abrió desde el icono de la pantalla de inicio.
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true
  )
}

/**
 * Muestra el diálogo nativo de instalación.
 * Devuelve true si el usuario aceptó instalar.
 */
export async function promptInstall() {
  const prompt = deferredPrompt.value
  if (!prompt) return false

  prompt.prompt()
  const { outcome } = await prompt.userChoice

  // El evento solo se puede usar una vez, se acepte o no
  deferredPrompt.value = null
  if (outcome === 'accepted') {
    installed.value = true
    return true
  }
  return false
}

export function initPwa() {
  if (typeof window === 'undefined') return

  isStandalone.value = detectStandalone()

  window.addEventListener('beforeinstallprompt', (event) => {
    // Sin preventDefault, Chrome muestra su propio aviso y no deja usar el botón
    event.preventDefault()
    deferredPrompt.value = event
  })

  window.addEventListener('appinstalled', () => {
    deferredPrompt.value = null
    installed.value = true
    isStandalone.value = true
  })

  if (detectStandalone()) {
    // Ya está instalada: no tiene sentido ofrecerla otra vez
    deferredPrompt.value = null
    return
  }

  // El service worker solo en producción (ver la nota de arriba)
  if (import.meta.env.PROD && 'serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch((err) => {
        console.warn('No se pudo registrar el service worker:', err)
      })
    })
  }
}
