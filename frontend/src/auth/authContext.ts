import { createContext } from 'react'

export type UserInfo = {
  tenant_id?: string
  role?: string
  email?: string
  exp?: number
}

export type AuthContextValue = {
  token: string | null
  user: UserInfo | null
  login: (payload: { email: string; password: string; tenant_id: string }) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
