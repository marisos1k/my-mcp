import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, clearToken, getToken, setToken } from "./api";

interface AuthState {
  email: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    api
      .me()
      .then((u) => setEmail(u.email))
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (e: string, p: string) => {
    const res = await api.login(e, p);
    setToken(res.access_token);
    setEmail(res.email);
  }, []);

  const register = useCallback(async (e: string, p: string) => {
    const res = await api.register(e, p);
    setToken(res.access_token);
    setEmail(res.email);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setEmail(null);
  }, []);

  const value = useMemo(
    () => ({ email, loading, login, register, logout }),
    [email, loading, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside provider");
  return ctx;
}
