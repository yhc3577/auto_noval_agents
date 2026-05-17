import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const userId = ref('')
  const username = ref('')

  async function register(user: string, pass: string) {
    const { data } = await api.post('/auth/register', {
      username: user,
      password: pass
    })
    token.value = data.token
    userId.value = data.id
    username.value = data.username
    localStorage.setItem('token', data.token)
  }

  async function login(user: string, pass: string) {
    const { data } = await api.post('/auth/login', {
      username: user,
      password: pass
    })
    token.value = data.token
    userId.value = data.id
    username.value = data.username
    localStorage.setItem('token', data.token)
  }

  function logout() {
    token.value = ''
    userId.value = ''
    username.value = ''
    localStorage.removeItem('token')
  }

  return { token, userId, username, register, login, logout }
})
