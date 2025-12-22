import React, { createContext, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { decodeJwt } from '../utils/base64'
import { useLogin } from '../api/hooks'

export type UserInfo = {
  tenant_id?: string
  role?: string
  email?: string
  exp?: number
}

type AuthContextValue = {
  token: string | null
  user: UserInfo | null
  login: (payload: { email: string; password: string; tenant_id: string }) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const loginMutation = useLogin()
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'))
  const [user, setUser] = useState<UserInfo | null>(() => {
    const stored = localStorage.getItem('token')
    return stored ? decodeJwt(stored) : null
  })

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
  }, [token])

  const login = async (payload: { email: string; password: string; tenant_id: string }) => {
    const res = await loginMutation.mutateAsync(payload)
    localStorage.setItem('token', res.access_token)
    setToken(res.access_token)
    setUser(decodeJwt(res.access_token))
    navigate('/')
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
    navigate('/login')
  }

  const value = useMemo(() => ({ token, user, login, logout }), [token, user])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
