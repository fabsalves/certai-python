import type { Role } from "./auth";

/** Papéis com acesso a cada área — espelha o RBAC do backend. */
export const ACCESS = {
  tracks: ["org_admin"] as Role[],
  cohorts: ["org_admin", "professor"] as Role[],
  professors: ["org_admin"] as Role[],
  learn: ["student"] as Role[],
  playground: ["org_admin", "superadmin"] as Role[],
  costs: ["org_admin", "superadmin"] as Role[],
  admin: ["superadmin"] as Role[],
  settings: ["org_admin"] as Role[],
} as const;

export function canAccess(role: Role, area: keyof typeof ACCESS): boolean {
  return ACCESS[area].includes(role);
}

export function homePathForRole(role: Role): string {
  if (role === "superadmin") return "/admin";
  if (role === "student") return "/learn";
  return "/";
}
