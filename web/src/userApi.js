/**
 * userApi.js — Cliente HTTP del área de usuarios (/u).
 *
 * Es un axios SEPARADO del de api.js (el del administrador) a propósito:
 *
 *   api.js     -> X-Igris-Key, guardada en localStorage  (administrador)
 *   userApi.js -> Authorization: Bearer <token>, en localStorage  (usuarios)
 *
 * Al ser clientes distintos, un 401 de un usuario no puede borrar la clave del
 * administrador, y al revés. Cada uno limpia solo lo suyo.
 *
 * El token va en localStorage con fecha de expiración explícita (TOKEN_TTL_MS)
 * para que la sesión sobreviva al cierre de la app en móvil sin durar para
 * siempre. Si el token del servidor caduca antes, el 401 limpia la sesión igual.
 */
import axios from 'axios'

// Mismo backend que el panel. El dominio va escrito aquí a propósito: el
// bundle del navegador NO lee VITE_API_URL (esa variable solo la usa el proxy
// del servidor de desarrollo en vite.config.js). Si cambia el backend hay que
// cambiar esta línea y la de api.js, y volver a compilar.
const API_URL = 'https://igris.zottagroup.com'

const TOKEN_STORAGE = 'igris_user_token'
const USER_STORAGE  = 'igris_user_data'
const EXPIRY_STORAGE = 'igris_user_token_exp'

// Cuánto tiempo se recuerda la sesión en el dispositivo (7 días).
// Si el JWT del servidor caduca antes, el 401 limpia la sesión de todas formas.
const TOKEN_TTL_MS = 7 * 24 * 60 * 60 * 1000

export function getToken() {
  try {
    const exp = localStorage.getItem(EXPIRY_STORAGE)
    if (exp && Date.now() > Number(exp)) {
      // Caducó el plazo local: limpiar para no dejar basura
      clearSession()
      return ''
    }
    return localStorage.getItem(TOKEN_STORAGE) || ''
  } catch {
    return ''
  }
}

export function getUser() {
  try {
    const raw = localStorage.getItem(USER_STORAGE)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setSession(token, user) {
  try {
    localStorage.setItem(TOKEN_STORAGE, token)
    localStorage.setItem(USER_STORAGE, JSON.stringify(user || {}))
    localStorage.setItem(EXPIRY_STORAGE, String(Date.now() + TOKEN_TTL_MS))
  } catch {
    // Almacenamiento no disponible (modo privado estricto): la sesión dura
    // solo lo que dure la pantalla abierta.
  }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_STORAGE)
    localStorage.removeItem(USER_STORAGE)
    localStorage.removeItem(EXPIRY_STORAGE)
  } catch {
    // ignorar
  }
}

export function isLoggedIn() {
  return !!getToken()
}

const userApi = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Añade el token a cada petición.
userApi.interceptors.request.use((config) => {
  const token = getToken()
  if (token && !config.headers['Authorization']) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

// Un 401 significa que el token caducó o ya no vale: se borra la sesión y se
// avisa al router (que llevará a /u/login). El aviso se hace con un evento para
// no importar el router desde aquí y evitar dependencias circulares.
userApi.interceptors.response.use(
  (response) => response,
  (error) => {
    const onLoginScreen = window.location.pathname.startsWith('/u/login')
    if (error.response?.status === 401 && !onLoginScreen) {
      clearSession()
      window.dispatchEvent(new CustomEvent('igris:user-unauthorized'))
    }
    return Promise.reject(error)
  }
)

export { errorMessage } from './errors'

export default userApi
