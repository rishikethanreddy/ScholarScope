import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, tokenStore } from './api';
import type { SessionUser } from './types';

interface AuthState {
  user: SessionUser | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<SessionUser>;
  signUp: (email: string, password: string) => Promise<SessionUser>;
  signOut: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);
  const qc = useQueryClient();

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      tokenStore.set(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      refresh,
      signIn: async (email, password) => {
        const r = await api.login(email, password);
        tokenStore.set(r.token);
        setUser(r.user);
        qc.clear();
        return r.user;
      },
      signUp: async (email, password) => {
        const r = await api.register(email, password);
        tokenStore.set(r.token);
        setUser(r.user);
        qc.clear();
        return r.user;
      },
      signOut: () => {
        tokenStore.set(null);
        setUser(null);
        qc.clear();
      },
    }),
    [user, loading, refresh, qc],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
