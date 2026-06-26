import type { ReactNode } from "react";
import { ProtectedRoute } from "./ProtectedRoute";
import { ACCESS } from "../lib/access";

type Area = keyof typeof ACCESS;

interface Props {
  area: Area;
  children: ReactNode;
}

/** Rota privada com RBAC centralizado em `lib/access.ts`. */
export function RoleRoute({ area, children }: Props) {
  return <ProtectedRoute roles={[...ACCESS[area]]}>{children}</ProtectedRoute>;
}
