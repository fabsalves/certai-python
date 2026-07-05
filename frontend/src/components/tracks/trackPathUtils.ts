import { levelLabel, sortedLessons, sortedModules, type Track } from "../../lib/tracks";

export type PathNodeState = "default" | "inactive" | "selected" | "done" | "current" | "locked";

export interface PathNodeItem {
  id: string;
  title: string;
  step: number | null;
  side: "left" | "right";
  state: PathNodeState;
  moduleLabel?: string;
  levelLabel?: string;
  professorLabel?: string;
  /** Módulo ainda sem aulas — placeholder no percurso. */
  emptyModule?: boolean;
  onClick?: () => void;
}

export function buildPathFromTrack(
  track: Track,
  options: {
    selectedLessonId?: string | null;
    onSelectLesson?: (lessonId: string, moduleId: string) => void;
    showInactive?: boolean;
  } = {},
): PathNodeItem[] {
  const { selectedLessonId, onSelectLesson, showInactive = true } = options;
  const items: PathNodeItem[] = [];
  let step = 0;

  for (const mod of sortedModules(track)) {
    if (!mod.is_active && !showInactive) continue;

    const lessons = sortedLessons(mod).filter((l) => showInactive || l.is_active);

    if (lessons.length === 0) {
      items.push({
        id: `module-${mod.id}`,
        title: mod.title,
        step: null,
        side: items.length % 2 === 0 ? "left" : "right",
        state: mod.is_active ? "default" : "inactive",
        moduleLabel: mod.title,
        levelLabel: levelLabel(mod.level),
        emptyModule: true,
      });
      continue;
    }

    lessons.forEach((lesson, li) => {
      const inactive = !mod.is_active || !lesson.is_active;
      if (!inactive) step += 1;

      items.push({
        id: lesson.id,
        title: lesson.title || "Sem título",
        step: inactive ? null : step,
        side: items.length % 2 === 0 ? "left" : "right",
        state: inactive
          ? "inactive"
          : selectedLessonId === lesson.id
            ? "selected"
            : "default",
        moduleLabel: li === 0 ? mod.title : undefined,
        levelLabel: li === 0 ? levelLabel(mod.level) : undefined,
        onClick: onSelectLesson ? () => onSelectLesson(lesson.id, mod.id) : undefined,
      });
    });
  }

  return items;
}

export function buildPathFromTrackWithProgress(
  track: Track,
  completedLessonIds: Set<string>,
  options: {
    selectedLessonId?: string | null;
    onSelectLesson?: (lessonId: string, moduleId: string) => void;
    showInactive?: boolean;
    allowLockedSelect?: boolean;
    moduleProfessorByModuleId?: Record<string, string>;
  } = {},
): PathNodeItem[] {
  const {
    selectedLessonId,
    onSelectLesson,
    showInactive = true,
    allowLockedSelect = false,
    moduleProfessorByModuleId,
  } = options;
  const items: PathNodeItem[] = [];
  let step = 0;
  let foundCurrent = false;

  for (const mod of sortedModules(track)) {
    if (!mod.is_active && !showInactive) continue;

    const lessons = sortedLessons(mod).filter((l) => showInactive || l.is_active);

    if (lessons.length === 0) {
      items.push({
        id: `module-${mod.id}`,
        title: mod.title,
        step: null,
        side: items.length % 2 === 0 ? "left" : "right",
        state: mod.is_active ? "default" : "inactive",
        moduleLabel: mod.title,
        levelLabel: levelLabel(mod.level),
        professorLabel: moduleProfessorByModuleId?.[mod.id],
        emptyModule: true,
      });
      continue;
    }

    lessons.forEach((lesson, li) => {
      const inactive = !mod.is_active || !lesson.is_active;
      if (!inactive) step += 1;

      let state: PathNodeState = "default";
      if (inactive) {
        state = "inactive";
      } else if (completedLessonIds.has(lesson.id)) {
        state = "done";
      } else if (!foundCurrent) {
        state = "current";
        foundCurrent = true;
      } else {
        state = "locked";
      }

      if (selectedLessonId === lesson.id && state !== "inactive") {
        if (state !== "locked" || allowLockedSelect) {
          state = "selected";
        }
      }

      const clickable =
        onSelectLesson &&
        state !== "inactive" &&
        (state !== "locked" || allowLockedSelect);

      items.push({
        id: lesson.id,
        title: lesson.title || "Sem título",
        step: inactive ? null : step,
        side: items.length % 2 === 0 ? "left" : "right",
        state,
        moduleLabel: li === 0 ? mod.title : undefined,
        levelLabel: li === 0 ? levelLabel(mod.level) : undefined,
        professorLabel:
          li === 0 ? moduleProfessorByModuleId?.[mod.id] : undefined,
        onClick: clickable ? () => onSelectLesson(lesson.id, mod.id) : undefined,
      });
    });
  }

  return items;
}

export function buildPathFromLearnLessons(
  lessons: { title: string; module: string; state: "done" | "current" | "locked" }[],
  options: { selectedIndex?: number; onSelect?: (index: number) => void } = {},
): PathNodeItem[] {
  let step = 0;
  let lastModule: string | undefined;

  return lessons.map((lesson, i) => {
    const newModule = lesson.module !== lastModule;
    if (newModule) lastModule = lesson.module;
    if (lesson.state !== "locked") step += 1;

    const state =
      options.selectedIndex === i && lesson.state !== "locked"
        ? "selected"
        : lesson.state;

    return {
      id: String(i),
      title: lesson.title,
      step: lesson.state === "locked" ? null : step,
      side: i % 2 === 0 ? "left" : "right",
      state,
      moduleLabel: newModule ? lesson.module : undefined,
      onClick:
        lesson.state !== "locked" && options.onSelect
          ? () => options.onSelect!(i)
          : undefined,
    };
  });
}
