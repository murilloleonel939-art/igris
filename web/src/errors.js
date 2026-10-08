/**
 * errors.js — Convierte cualquier error en un mensaje legible.
 *
 * Los mensajes de error que devuelve FastAPI no siempre tienen la misma forma:
 *
 *   401/409/429  { "detail": "Usuario o contraseña incorrectos" }
 *   422          { "detail": [ { "loc": [...], "msg": "..." } ] }   (validación)
 *   otros        { "detail": "..." } o el cuerpo entero sin "detail"
 *
 * Si se pinta el objeto tal cual, el usuario ve "[object Object]" o un JSON
 * crudo. Esta función normaliza los tres casos a una sola frase.
 */

export function errorMessage(error, fallback = 'Ha ocurrido un error') {
  // Sin respuesta: red caída, CORS bloqueado o servidor apagado
  if (!error || !error.response) {
    if (error && error.message === 'Network Error') {
      return 'No se pudo conectar con el servidor'
    }
    return fallback
  }

  const { status, data } = error.response

  // FastAPI devuelve el detalle como texto en la mayoría de los casos
  if (data && typeof data.detail === 'string' && data.detail.trim()) {
    return data.detail
  }

  // Errores de validación (422): detail es una lista de problemas
  if (data && Array.isArray(data.detail) && data.detail.length) {
    const primero = data.detail[0]
    if (primero && typeof primero.msg === 'string' && primero.msg.trim()) {
      // Pydantic antepone "Value error, " a los mensajes de los validadores
      return primero.msg.replace(/^Value error,\s*/i, '')
    }
    return 'Los datos enviados no son válidos'
  }

  // Respuestas propias del servidor de estáticos o del proxy
  if (data && typeof data.error === 'string' && data.error.trim()) {
    return data.error
  }
  if (data && typeof data.message === 'string' && data.message.trim()) {
    return data.message
  }

  // Mensajes por defecto según el código, por si el cuerpo viniera vacío
  if (status === 401) return 'Usuario o contraseña incorrectos'
  if (status === 403) return 'No tienes permiso para hacer esto'
  if (status === 404) return 'No se encontró el recurso'
  if (status === 409) return 'Ese dato ya está en uso'
  if (status === 429) return 'Demasiados intentos, espera unos minutos'
  if (status >= 500) return 'El servidor ha fallado, inténtalo más tarde'

  return fallback
}

export default errorMessage
