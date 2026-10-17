import axios from 'axios'
import { USER_KEY } from '../offline/store'
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { endpoints, TOKEN_KEY } from '../../services/api'
import type { AuthResult, User } from '../../types'

interface AuthContextValue { user: User | null; loading: boolean; accept: (result: AuthResult) => void; logout: () => Promise<void> }
const AuthContext = createContext<AuthContextValue | null>(null)
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const clear = useCallback(() => { setUser(null); sessionStorage.removeItem(TOKEN_KEY); sessionStorage.removeItem(USER_KEY) }, [])
  useEffect(() => {
    if (sessionStorage.getItem(TOKEN_KEY)) endpoints.me().then(value => { sessionStorage.setItem(USER_KEY, JSON.stringify(value)); setUser(value) }).catch(error => {
      if(axios.isAxiosError(error) && !error.response) { try { setUser(JSON.parse(sessionStorage.getItem(USER_KEY) || 'null')) } catch { clear() } } else clear()
    }).finally(() => setLoading(false))
    else setLoading(false)
    window.addEventListener('auth:expired', clear)
    return () => window.removeEventListener('auth:expired', clear)
  }, [clear])
  const accept = (result: AuthResult) => { sessionStorage.setItem(TOKEN_KEY, result.access_token); sessionStorage.setItem(USER_KEY, JSON.stringify(result.user)); setUser(result.user) }
  const logout = async () => { try { await endpoints.logout() } finally { clear() } }
  return <AuthContext.Provider value={{ user, loading, accept, logout }}>{children}</AuthContext.Provider>
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('AuthProvider missing'); return value }
