import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { loginUser, registerUser, getMyProfile } from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const token       = ref(localStorage.getItem('token') || null)
  const user        = ref(null)
  const loading     = ref(false)
  const error       = ref(null)
  // true while the initial token validation is still in-flight
  const validating  = ref(!!token.value)

  const isLoggedIn = computed(() => !!token.value)

  async function login(email, password) {
    loading.value = true
    error.value   = null
    try {
      const res = await loginUser(email, password)
      token.value = res.data.access_token
      localStorage.setItem('token', token.value)
      await fetchProfile()
      return true
    } catch (e) {
      error.value = e.response?.data?.detail || 'Login failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function register(payload) {
    loading.value = true
    error.value   = null
    try {
      await registerUser(payload)
      return true
    } catch (e) {
      error.value = e.response?.data?.detail || 'Registration failed'
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchProfile() {
    try {
      const res = await getMyProfile()
      user.value = res.data
    } catch (_) { /* ignore */ }
  }

  function logout() {
    token.value  = null
    user.value   = null
    localStorage.removeItem('token')
  }

  /**
   * Called once on app start when a token already exists in localStorage.
   * Hits /users/me — if it returns 401/403 (expired or invalid token) we
   * clear everything so the router guard redirects to /auth.
   */
  async function validateStoredToken() {
    if (!token.value) {
      validating.value = false
      return
    }
    try {
      const res  = await getMyProfile()
      user.value = res.data
    } catch (e) {
      const status = e.response?.status
      if (status === 401 || status === 403 || status === 422) {
        // Token is expired or invalid — clear it
        logout()
      }
      // Any other error (network down etc.) we keep the token and let
      // the user try — the backend will reject individual requests if needed.
    } finally {
      validating.value = false
    }
  }

  // Kick off validation immediately on store creation
  validateStoredToken()

  return {
    token, user, loading, error, validating,
    isLoggedIn, login, register, logout, fetchProfile, validateStoredToken
  }
})
