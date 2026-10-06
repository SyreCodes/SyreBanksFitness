import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, csrfToken, setAccessToken } from './api';

export type User = { id: string; name: string; email: string; role: 'SUPER_ADMIN' | 'ADMIN' | 'COACH' | 'CLIENT' | 'LEAD'; timezone?: string };
type AuthResponse = { access_token: string; user: User };
type AuthValue = { user: User | null; loading: boolean; login: (email: string, password: string) => Promise<User>; register: (values: { name: string; email: string; password: string }) => Promise<User>; logout: () => Promise<void> };
const AuthContext = createContext<AuthValue | null>(null);
let pendingRestore: Promise<AuthResponse> | null = null;
function restoreSession() {
  pendingRestore ??= api<AuthResponse>('/auth/refresh', { method: 'POST' }).finally(() => { pendingRestore = null; });
  return pendingRestore;
}
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const queryClient = useQueryClient();
  const acceptSession = useCallback((data: AuthResponse) => { setAccessToken(data.access_token); setUser(data.user); return data.user; }, []);
  useEffect(() => {
    let cancelled = false;
    if (!csrfToken()) { setLoading(false); return; }
    restoreSession().then(data => { if (!cancelled) acceptSession(data); }).catch(() => { if (!cancelled) { setUser(null); setAccessToken(null); } }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [acceptSession]);
  useEffect(() => {
    if (!user) return;
    const interval = window.setInterval(() => { void restoreSession().then(acceptSession).catch(() => { setUser(null); setAccessToken(null); queryClient.clear(); }); }, 12 * 60_000);
    return () => window.clearInterval(interval);
  }, [user, acceptSession, queryClient]);
  const login = async (email: string, password: string) => acceptSession(await api<AuthResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }));
  const register = async (values: { name: string; email: string; password: string }) => acceptSession(await api<AuthResponse>('/auth/register', { method: 'POST', body: JSON.stringify(values) }));
  const logout = async () => {
    try { await api('/auth/logout', { method: 'POST' }); } finally { setUser(null); setAccessToken(null); queryClient.clear(); }
  };
  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>;
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('AuthProvider is required'); return value; }
