export type ModuleLevel = "beginner" | "intermediate" | "advanced";

export interface Lesson {
  id: string;
  title: string;
  content: string;
  position: number;
  is_active: boolean;
}

export interface Module {
  id: string;
  title: string;
  level: ModuleLevel;
  position: number;
  is_active: boolean;
  lessons: Lesson[];
}

export interface Track {
  id: string;
  title: string;
  description: string;
  competency: string;
  published: boolean;
  is_active: boolean;
  modules: Module[];
}

export const MODULE_LEVELS: { value: ModuleLevel; label: string }[] = [
  { value: "beginner", label: "Iniciante" },
  { value: "intermediate", label: "Intermediário" },
  { value: "advanced", label: "Avançado" },
];

export function levelLabel(level: ModuleLevel): string {
  return MODULE_LEVELS.find((l) => l.value === level)?.label ?? level;
}

export function sortedModules(track: Track): Module[] {
  return [...track.modules].sort((a, b) => a.position - b.position);
}

export function sortedLessons(module: Module): Lesson[] {
  return [...module.lessons].sort((a, b) => a.position - b.position);
}

export function nextModulePosition(track: Track): number {
  if (track.modules.length === 0) return 1;
  return Math.max(...track.modules.map((m) => m.position)) + 1;
}

export function nextLessonPosition(module: Module): number {
  if (module.lessons.length === 0) return 1;
  return Math.max(...module.lessons.map((l) => l.position)) + 1;
}

export function totalLessons(track: Track): number {
  return track.modules.reduce((n, m) => n + m.lessons.length, 0);
}

export function activeLessonsCount(track: Track): number {
  return track.modules
    .filter((m) => m.is_active)
    .reduce((n, m) => n + m.lessons.filter((l) => l.is_active).length, 0);
}
