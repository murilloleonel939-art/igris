/**
 * userApi.js — Cliente HTTP del área de usuarios (/u).
 *
 * Es un axios SEPARADO del de api.js (el del administrador) a propósito:
 *
 *   api.js     -> X-Igris-Key, guardada en localStorage  (administrador)
 *   userApi.js -> Authorization: Bearer <token>, en sessionStorage  (usuarios)
 *
 * Al ser clientes distintos, un 401 de un usuario no puede borrar la clave del
 * administrador, y al revés. Cada uno limpia solo lo suyo.
 *
 * El token va en sessionStorage y no en localStorage: al cerrar el navegador la
 * sesión del usuario termina sola. Es lo adecuado para cuentas que se usan en
 * ordenadores compartidos.
 */
import axios from 'axios'

// Mismo backend que el panel. El dominio va escrito aquí a propósito: el
// bundle del navegador NO lee VITE_API_URL (esa variable solo la usa el proxy
// del servidor de desarrollo en vite.config.js). Si cambia el backend hay que
// cambiar esta línea y la de api.js, y volver a compilar.
const API_URL = 'https://igris.zottagroup.com'

const TOKEN_STORAGE = 'igris_user_token'
const USER_STORAGE = 'igris_user_data'

export function getToken() {
  try {
    return sessionStorage.getItem(TOKEN_STORAGE) || ''
  } catch {
    return ''
  }
}

export function getUser() {
  try {
    const raw = sessionStorage.getItem(USER_STORAGE)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setSession(token, user) {
  try {
    sessionStorage.setItem(TOKEN_STORAGE, token)
    sessionStorage.setItem(USER_STORAGE, JSON.stringify(user || {}))
  } catch {
    // Almacenamiento no disponible (modo privado estricto): la sesión dura
    // solo lo que dure la pantalla abierta.
  }
}

export function clearSession() {
  try {
    sessionStorage.removeItem(TOKEN_STORAGE)
    sessionStorage.removeItem(USER_STORAGE)
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
