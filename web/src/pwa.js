/**
 * pwa.js — Instalación de IGRIS como aplicación (PWA).
 *
 * Hay DOS aplicaciones instalables y no una, porque el administrador y los
 * usuarios entran por pantallas distintas:
 *
 *   /manifest-admin.webmanifest -> start_url /acceso   (administrador)
 *   /manifest.webmanifest       -> start_url /u/login  (usuarios)
 *
 * El navegador elige leyendo el <link rel="manifest"> del HTML, así que lo
 * principal lo hace server.js al servir la página. syncManifest() es el
 * complemento para la navegación interna de la SPA: si se pasa de /acceso a
 * /u/login sin recargar, el enlace se corrige aquí para que una instalación
 * hecha justo después apunte al área correcta.
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

const MANIFEST_ADMIN = '/manifest-admin.webmanifest'
const MANIFEST_USER = '/manifest.webmanifest'

/** ¿Esta ruta pertenece al área de usuarios (/u y /u/login)? */
function isUserPath(pathname) {
  return pathname === '/u' || pathname.startsWith('/u/')
}

/**
 * Pone en el <link rel="manifest"> el manifest que corresponde a la ruta.
 * Devuelve el href que quedó puesto.
 */
export function syncManifest(pathname = window.location.pathname) {
  if (typeof document === 'undefined') return MANIFEST_ADMIN

  const link = document.querySelector('link[rel="manifest"]')
  if (!link) return MANIFEST_ADMIN

  const want = isUserPath(pathname) ? MANIFEST_USER : MANIFEST_ADMIN
  if (link.getAttribute('href') !== want) {
    link.setAttribute('href', want)
  }

  // El nombre que iOS usa bajo el icono de la pantalla de inicio también
  // distingue las dos apps.
  const title = document.querySelector('meta[name="apple-mobile-web-app-title"]')
  if (title) {
    const wantTitle = isUserPath(pathname) ? 'IGRIS' : 'IGRIS Admin'
    if (title.getAttribute('content') !== wantTitle) {
      title.setAttribute('content', wantTitle)
    }
  }

  return want
}

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
