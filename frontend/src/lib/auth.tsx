"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  getMe,
  getToken,
  login as apiLogin,
  register as apiRegister,
  setToken,
  type UserOut,
} from "./api";
import { AuthModal } from "@/components/AuthModal";

type AuthContextValue = {
  user: UserOut | null;
  ready: boolean;
  isAuthed: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  openAuth: () => void;
  closeAuth: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [ready, setReady] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);

  // Restore session from a stored token on first load.
  useEffect(() => {
    (async () => {
      if (getToken()) {
        try {
          setUser(await getMe());
        } catch {
          setToken(null);
        }
      }
      setReady(true);
    })();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiLogin(email, password);
    setToken(res.token);
    setUser(res.user);
    setAuthOpen(false);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const res = await apiRegister(email, password);
    setToken(res.token);
    setUser(res.user);
    setAuthOpen(false);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    user,
    ready,
    isAuthed: user !== null,
    login,
    register,
    logout,
    openAuth: () => setAuthOpen(true),
    closeAuth: () => setAuthOpen(false),
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
      {authOpen && <AuthModal onClose={() => setAuthOpen(false)} login={login} register={register} />}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
