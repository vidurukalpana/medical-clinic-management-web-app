import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, setUnauthorizedHandler, tokenStore, type AuthUser } from "./api";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  isStaff: boolean;
  isAdmin: boolean;
  login: (username: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
  clear: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(() => Boolean(tokenStore.get()));

  const clear = useCallback(() => {
    tokenStore.set(null);
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => {
    setUnauthorizedHandler(clear);
    if (tokenStore.get()) {
      api
        .me()
        .then(setUser)
        .catch(clear)
        .finally(() => setLoading(false));
    }
    return () => setUnauthorizedHandler(null);
  }, [clear]);

  const login = useCallback(
    async (username: string, password: string) => {
      const response = await api.login(username, password);
      queryClient.clear();
      tokenStore.set(response.access_token);
      setUser(response.user);
      return response.user;
    },
    [queryClient],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      clear();
    }
  }, [clear]);

  const refreshUser = useCallback(async () => setUser(await api.me()), []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      isStaff: user?.role === "administrator" || user?.role === "doctor",
      isAdmin: user?.role === "administrator",
      login,
      logout,
      clear,
      refreshUser,
    }),
    [user, loading, login, logout, clear, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function homePathFor(user: AuthUser | null): string {
  if (!user) return "/";
  return user.role === "patient" ? "/my-bookings" : "/staff";
}
