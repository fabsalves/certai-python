import type { Role } from "../../lib/auth";
import { ACCESS } from "../../lib/access";

export interface NavItem {
  to: string;
  label: string;
  description?: string;
  roles?: Role[];
  icon: "overview" | "tracks" | "cohorts" | "professors" | "learn" | "playground" | "costs" | "admin" | "settings";
}

export const NAV: NavItem[] = [
  { to: "/", label: "Início", description: "Resumo do dia", icon: "overview" },
  {
    to: "/settings",
    label: "Administração",
    description: "Membros e integrações",
    roles: ACCESS.settings,
    icon: "settings",
  },
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
    to: "/admin",
    label: "Organizações",
    description: "Console da plataforma",
    roles: ACCESS.admin,
    icon: "admin",
  },
  {
    to: "/costs",
    label: "Custos",
    description: "Consumo de IA por turma e aluno",
    roles: ACCESS.costs,
    icon: "costs",
  },
  {
    to: "/admin/playground",
    label: "Playground",
    description: "Simular conversas como aluno ou professor",
    roles: ACCESS.playground,
    icon: "playground",
  },
];

export function navForRole(role: Role): NavItem[] {
  return NAV.filter((n) => {
    if (n.to === "/" && role === "superadmin") return false;
    return !n.roles || n.roles.includes(role);
  }).map((item) => {
    if (item.to === "/cohorts" && role === "professor") {
      return { ...item, label: "Minhas turmas", description: "Andamento e encerramento de aulas" };
    }
    return item;
  });
}

function pathMatchesItem(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/";
  return pathname === to || pathname.startsWith(`${to}/`);
}

export function navItemForPath(pathname: string, role: Role): NavItem | undefined {
  const matches = navForRole(role).filter((n) => pathMatchesItem(pathname, n.to));
  if (matches.length === 0) return undefined;
  return matches.reduce((best, item) => (item.to.length > best.to.length ? item : best));
}

export function isNavActive(pathname: string, to: string, role: Role): boolean {
  return navItemForPath(pathname, role)?.to === to;
}
