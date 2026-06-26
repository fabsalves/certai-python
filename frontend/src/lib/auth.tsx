import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api, tokens } from "./api";

export type Role = "admin" | "designer" | "professor" | "student";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState>(null!);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokens.access) {
      setLoading(false);
      return;
    }
    api
      .get<User>("/users/me")
      .then((r) => setUser(r.data))
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const form = new URLSearchParams({ username: email, password });
    const { data } = await api.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    tokens.set(data.access_token, data.refresh_token);
    const me = await api.get<User>("/users/me");
    setUser(me.data);
  }

  function logout() {
    tokens.clear();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

// Keys in English (code); labels in Portuguese (shown to the user).
export const roleLabel: Record<Role, string> = {
  admin: "Administrador",
  designer: "Designer de conteúdo",
  professor: "Professor",
  student: "Aluno",
};
