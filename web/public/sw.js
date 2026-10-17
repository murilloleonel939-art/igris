/**
 * sw.js — Service worker de IGRIS.
 *
 * Estrategia: red primero, caché como red de rescate.
 *
 *   - Cada petición intenta llegar al servidor. Si responde, se devuelve esa
 *     respuesta (y se guarda una copia para poder abrir la app sin conexión).
 *   - Si la red falla, se sirve la copia guardada.
 *
 * Se eligió "red primero" y no "caché primero" a propósito: con caché primero,
 * los usuarios seguirían viendo la versión antigua de la aplicación después de
 * cada despliegue. Así siempre se llevan lo último que haya publicado el
 * servidor, y la caché solo evita la pantalla en blanco cuando no hay conexión.
 *
 * Lo que NUNCA se guarda:
 *   - /api/... y /auth/...  -> son datos privados (usuarios, chat, tokens) y no
 *                              deben quedar en disco ni reutilizarse sin conexión.
 *   - Cualquier otro origen    -> solo se gestiona lo propio.
 */
const CACHE = 'igris-v4'

// Mínimo imprescindible para que la app abra sin conexión.
// Se guardan las dos pantallas de acceso y los dos manifests, porque son dos
// aplicaciones instalables distintas (administrador y usuarios).
const PRECACHE = [
  '/',
  '/acceso',
  '/u',
  '/u/login',
  '/manifest-admin.webmanifest',
  '/manifest.webmanifest',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .catch(() => {
        // Si algún recurso falla, la instalación no debe romperse por eso:
        // la caché se irá llenando sola con el uso normal.
      })
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event

  // Solo GET: no tiene sentido cachear envíos
  if (request.method !== 'GET') return

  const url = new URL(request.url)

  // Solo lo propio: el backend es otro origen y no se toca
  if (url.origin !== self.location.origin) return

  // Nunca cachear datos privados ni el propio service worker
  if (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/auth/') ||
    url.pathname.startsWith('/telegram/') ||
    url.pathname === '/sw.js'
  ) {
    return
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        // Solo se guardan respuestas correctas y completas
        if (response && response.status === 200 && response.type === 'basic') {
          const copy = response.clone()
          caches.open(CACHE).then((cache) => cache.put(request, copy)).catch(() => {})
        }
        return response
      })
      .catch(() =>
        caches.match(request).then((cached) => {
          if (cached) return cached
          // Navegación sin conexión y sin copia guardada: se abre la pantalla
          // de acceso del área que corresponda. Nunca la del administrador
          // para quien venía de /u.
          if (request.mode === 'navigate') {
            const isUserArea =
              url.pathname === '/u' || url.pathname.startsWith('/u/')
            return caches.match(isUserArea ? '/u/login' : '/acceso')
          }
          return Response.error()
        })
      )
  )
})
