import type { Role } from "./auth";

/** Papéis com acesso a cada área — espelha o RBAC do backend. */
export const ACCESS = {
  /** Trilhas: CRUD de conteúdo (admin, designer). */
  tracks: ["admin", "designer"] as Role[],
  /** Turmas: gestão (admin, designer) ou leitura das próprias (professor). */
  cohorts: ["admin", "designer", "professor"] as Role[],
  /** Cadastro de professores (admin, designer). */
  professors: ["admin", "designer"] as Role[],
  /** Aulas do aluno matriculado. */
  learn: ["student"] as Role[],
  /** Playground de testes da IA — somente admin. */
  playground: ["admin"] as Role[],
} as const;

export function canAccess(role: Role, area: keyof typeof ACCESS): boolean {
  return ACCESS[area].includes(role);
}
