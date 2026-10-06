import axios from 'axios'

// URL del backend (dominio distinto al del frontend: el backend habilita CORS
// para https://webigris.zottagroup.com y http://localhost:5173)
const API_URL = 'https://igris.zottagroup.com'

// La clave de acceso vive SOLO en localStorage (nunca en VITE_*, ni en el código)
const KEY_STORAGE = 'igris_key'
const ACCESS_PATH = '/acceso'

export function getKey() {
  try {
    return localStorage.getItem(KEY_STORAGE) || ''
  } catch {
    return ''
  }
}

export function setKey(key) {
  try {
    localStorage.setItem(KEY_STORAGE, key)
  } catch {
    // Almacenamiento no disponible (modo privado estricto): no hay nada que hacer
  }
}

export function clearKey() {
  try {
    localStorage.removeItem(KEY_STORAGE)
  } catch {
    // ignorar
  }
}

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Interceptor de petición: añade la clave guardada.
// Si la petición ya trae su propio X-Igris-Key (pantalla de acceso), se respeta.
api.interceptors.request.use((config) => {
  if (!config.headers['X-Igris-Key']) {
    const key = getKey()
    if (key) {
      config.headers['X-Igris-Key'] = key
    }
  }
  return config
})

// Interceptor de respuesta: ante un 401 fuera de la pantalla de acceso,
// borra la clave y avisa al router para llevar al usuario a /acceso.
// La pantalla de acceso maneja su propio 401, así que aquí no hace nada.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const onAccessScreen = window.location.pathname === ACCESS_PATH
    if (error.response?.status === 401 && !onAccessScreen) {
      clearKey()
      window.dispatchEvent(new CustomEvent('igris:unauthorized'))
    }
    return Promise.reject(error)
  }
)

export default api
