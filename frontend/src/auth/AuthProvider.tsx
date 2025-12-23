import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { decodeJwt } from '../utils/base64'
import { useLogin } from '../api/hooks'
import { AuthContext, type UserInfo } from './authContext'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const { mutateAsync: loginAsync } = useLogin()
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [user, setUser] = useState<UserInfo | null>(() => {
    const stored = localStorage.getItem('token')
    return stored ? decodeJwt(stored) : null
  })

  const login = useCallback(async (payload: { email: string; password: string; tenant_id: string }) => {
    const res = await loginAsync(payload)
    localStorage.setItem('token', res.access_token)
    setToken(res.access_token)
    setUser(decodeJwt(res.access_token))
    navigate('/')
  }, [loginAsync, navigate])

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
    navigate('/login')
  }, [navigate])

  useEffect(() => {
    if (!token) return
    const payload = decodeJwt(token)
    setUser(payload)
    if (payload?.exp) {
      const now = Date.now() / 1000
      if (payload.exp < now) {
        logout()
      }
    }
  }, [token, logout])

  const value = useMemo(() => ({ token, user, login, logout }), [token, user, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
