import type { Role } from "../../lib/auth";
import { ACCESS } from "../../lib/access";

export interface NavItem {
  to: string;
  label: string;
  description?: string;
  roles?: Role[];
  icon: "overview" | "tracks" | "cohorts" | "professors" | "learn" | "playground";
}

export const NAV: NavItem[] = [
  { to: "/", label: "Início", description: "Resumo do dia", icon: "overview" },
  { to: "/tracks", label: "Trilhas", description: "Conteúdo e sequência", roles: ACCESS.tracks, icon: "tracks" },
  { to: "/cohorts", label: "Turmas", description: "Grupos e andamento", roles: ACCESS.cohorts, icon: "cohorts" },
  {
    to: "/professors",
    label: "Professores",
    description: "Contas de leitores",
    roles: ACCESS.professors,
    icon: "professors",
  },
  { to: "/learn", label: "Minhas aulas", description: "Material da turma", roles: ACCESS.learn, icon: "learn" },
  {
    to: "/admin/playground",
    label: "Playground",
    description: "Simular conversas como aluno ou professor",
    roles: ACCESS.playground,
    icon: "playground",
  },
];

export function navForRole(role: Role): NavItem[] {
  return NAV.filter((n) => !n.roles || n.roles.includes(role)).map((item) => {
    if (item.to === "/cohorts" && role === "professor") {
      return { ...item, label: "Minhas turmas", description: "Andamento e encerramento de aulas" };
    }
    return item;
  });
}

export function navItemForPath(pathname: string, role: Role): NavItem | undefined {
  const items = navForRole(role);
  return items.find((n) => (n.to === "/" ? pathname === "/" : pathname.startsWith(n.to)));
}
