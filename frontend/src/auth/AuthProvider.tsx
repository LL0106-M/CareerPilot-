import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import { api, ApiError, type Account } from '../data/api'
import { AUTH_EXPIRED_EVENT } from './auth-events'

type AuthStatus = 'loading' | 'authenticated' | 'guest'

interface AuthContextValue {
  account: Account | null
  status: AuthStatus
  login: (identifier: string, password: string, rememberMe: boolean) => Promise<Account>
  logout: () => Promise<void>
  register: (input: { username: string; email: string; verificationCode: string; password: string }) => Promise<Account>
  requestVerificationCode: (email: string) => Promise<{ retry_after_seconds: number }>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [account, setAccount] = useState<Account | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  useEffect(() => {
    let active = true
    api.getCurrentAccount()
      .then((current) => { if (active) { setAccount(current); setStatus('authenticated') } })
      .catch((reason) => {
        if (!active) return
        setAccount(null)
        setStatus(reason instanceof ApiError && reason.status === 401 ? 'guest' : 'guest')
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const expire = () => { setAccount(null); setStatus('guest') }
    window.addEventListener(AUTH_EXPIRED_EVENT, expire)
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expire)
  }, [])

  const login = useCallback(async (identifier: string, password: string, rememberMe: boolean) => {
    const current = await api.login(identifier, password, rememberMe)
    setAccount(current)
    setStatus('authenticated')
    return current
  }, [])

  const logout = useCallback(async () => {
    try { await api.logout() } finally { setAccount(null); setStatus('guest') }
  }, [])

  const register = useCallback((input: { username: string; email: string; verificationCode: string; password: string }) => api.register(input), [])
  const requestVerificationCode = useCallback((email: string) => api.requestVerificationCode(email), [])

  const value = useMemo(() => ({ account, status, login, logout, register, requestVerificationCode }), [account, status, login, logout, register, requestVerificationCode])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
