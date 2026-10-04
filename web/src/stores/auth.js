import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token'))
  const refreshToken = ref(localStorage.getItem('refresh_token'))
  const isAuthenticated = computed(() => !!accessToken.value)
  const requires2FA = ref(false)

  const register = async (username, email, password, confirmPassword) => {
    try {
      const response = await api.post('/auth/register', {
        username,
        email,
        password,
        confirm_password: confirmPassword
      })
      return response.data
    } catch (error) {
      throw error.response?.data || { error: 'Error en registro' }
    }
  }

  const login = async (username, password, otpCode = null) => {
    try {
      const response = await api.post('/auth/login', {
        username,
        password,
        otp_code: otpCode
      })
      
      accessToken.value = response.data.access_token
      refreshToken.value = response.data.refresh_token
      requires2FA.value = response.data.requires_2fa
      
      localStorage.setItem('access_token', accessToken.value)
      localStorage.setItem('refresh_token', refreshToken.value)
      
      return response.data
    } catch (error) {
      if (error.response?.status === 403) {
        requires2FA.value = true
      }
      throw error.response?.data || { error: 'Error en login' }
    }
  }

  const logout = () => {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    requires2FA.value = false
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  const getMe = async () => {
    try {
      const response = await api.get('/auth/me')
      user.value = response.data
      return response.data
    } catch (error) {
      logout()
      throw error
    }
  }

  const checkAuth = async () => {
    if (accessToken.value) {
      try {
        await getMe()
      } catch (error) {
        logout()
      }
    }
  }

  const setup2FA = async () => {
    try {
      const response = await api.post('/auth/2fa/setup')
      return response.data
    } catch (error) {
      throw error.response?.data || { error: 'Error en setup 2FA' }
    }
  }

  const verify2FA = async (code) => {
    try {
      const response = await api.post('/auth/2fa/verify', { code })
      return response.data
    } catch (error) {
      throw error.response?.data || { error: 'Código 2FA inválido' }
    }
  }

  const disable2FA = async (password) => {
    try {
      const response = await api.post('/auth/2fa/disable', { password })
      return response.data
    } catch (error) {
      throw error.response?.data || { error: 'Error desactivando 2FA' }
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    requires2FA,
    register,
    login,
    logout,
    getMe,
    checkAuth,
    setup2FA,
    verify2FA,
    disable2FA
  }
})
