import { type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth, type Role } from "../lib/auth";

interface Props {
  children: ReactNode;
  roles?: Role[]; // se omitido, basta estar autenticado
}

export function ProtectedRoute({ children, roles }: Props) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div style={{ padding: 48, color: "var(--text-muted)" }}>Carregando…</div>;
  }
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
