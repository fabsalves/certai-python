/** A teaching class: one professor of one module, with their own students.
 *  student_ids is empty when the module has a single professor -- then the
 *  whole cohort is their class. */
export interface ModuleProfessor {
  id: string;
  module_id: string;
  module_title: string;
  professor_id: string;
  professor_name: string;
  student_ids: string[];
}

export interface Cohort {
  id: string;
  name: string;
  track_id: string;
  track_title: string;
  enrollment_count: number;
  module_professors: ModuleProfessor[];
}

export interface Enrollment {
  id: string;
  student_id: string;
  student_name: string;
  student_email: string;
  student_whatsapp?: string | null;
  enrolled_at: string;
}

export interface LessonClassStatus {
  module_professor_id: string;
  professor_id: string;
  professor_name: string;
  closed: boolean;
  closed_at: string | null;
  /** What this class actually taught of the lesson. */
  covered: string;
  /** What is still owed. Non-empty = part of the plan was not taught. */
  pending: string;
  /** "" when the session reported nothing beyond the plan. */
  extent: "" | "full" | "partial";
}

export interface LessonClasses {
  lesson_id: string;
  classes: LessonClassStatus[];
  /** Some class closed it while another is still pending on an earlier lesson. */
  delayed: boolean;
}

export interface CohortProgress {
  /** Closed by every class of the module. */
  completed_lesson_ids: string[];
  /** Closed by at least one class, pending for another. */
  partial_lesson_ids: string[];
  current_lesson_id: string | null;
  lesson_classes: LessonClasses[];
}

export interface CohortLessonNote {
  lesson_id: string;
  module_professor_id: string;
  professor_id: string;
  professor_name: string;
  attachment_filename: string | null;
  has_attachment: boolean;
  has_audio: boolean;
  /** Real upload/recording name; null on legacy notes. */
  audio_filename?: string | null;
  /** "recording" | "file"; null on legacy notes. */
  audio_source?: "recording" | "file" | null;
  ingestion_status: string;
}

export interface TrackOption {
  id: string;
  title: string;
  is_active: boolean;
  modules: {
    id: string;
    title: string;
    level: string;
    position: number;
    is_active: boolean;
    lessons: unknown[];
  }[];
}

export interface ProfessorOption {
  id: string;
  name: string;
  email: string;
}

export interface ModuleProfessorAssignment {
  module_id: string;
  professor_id: string;
  student_ids: string[];
}

/** One class being edited in the Professores tab. */
export interface ModuleClassDraft {
  professorId: string;
  studentIds: string[];
}

/** module_id -> its classes, in display order. */
export type ModuleAssignments = Record<string, ModuleClassDraft[]>;

export function uniqueProfessorNames(cohort: Cohort): string {
  return [...new Set(cohort.module_professors.map((mp) => mp.professor_name))].join(", ");
}

export function professorsForModule(
  cohort: Cohort | null,
  moduleId: string,
): ModuleProfessor[] {
  return cohort?.module_professors.filter((mp) => mp.module_id === moduleId) ?? [];
}

/** The class a student studies a module with. With a single professor, everyone
 *  is in it -- the same shortcut the backend applies. */
export function classForStudent(
  classes: ModuleProfessor[],
  studentId: string | null,
): ModuleProfessor | undefined {
  if (classes.length === 0) return undefined;
  if (classes.length === 1) return classes[0];
  if (!studentId) return undefined;
  return classes.find((item) => item.student_ids.includes(studentId));
}

/** One teaching class (or unassigned bucket) in the Alunos tab list. */
export interface StudentClassSection {
  key: string;
  moduleId: string;
  moduleTitle: string;
  professorId: string | null;
  professorName: string | null;
  /** Viewer professor's class inside a split module — show "Sua turma". */
  isOwnClass: boolean;
  isUnassigned: boolean;
  isSplitModule: boolean;
  studentIds: string[];
}

/**
 * Build Alunos-tab sections from module classes.
 * - 1 professor/module → one section with all enrollments (no unassigned).
 * - N professors → one section per class; optional unassigned for admin.
 * - Professor viewer → only their own classes.
 */
export function buildStudentSections(options: {
  moduleProfessors: ModuleProfessor[];
  enrollments: Enrollment[];
  moduleOrder: { id: string; title: string; position: number }[];
  viewerProfessorId?: string | null;
  includeUnassigned?: boolean;
}): StudentClassSection[] {
  const {
    moduleProfessors,
    enrollments,
    moduleOrder,
    viewerProfessorId = null,
    includeUnassigned = false,
  } = options;

  const enrolledIds = enrollments.map((item) => item.student_id);
  const enrolledSet = new Set(enrolledIds);
  const byModule = new Map<string, ModuleProfessor[]>();
  for (const mp of moduleProfessors) {
    const list = byModule.get(mp.module_id) ?? [];
    list.push(mp);
    byModule.set(mp.module_id, list);
  }

  const order =
    moduleOrder.length > 0
      ? [...moduleOrder].sort((a, b) => a.position - b.position)
      : [...byModule.keys()].map((id, index) => ({
          id,
          title: byModule.get(id)?.[0]?.module_title ?? "Módulo",
          position: index,
        }));

  const sections: StudentClassSection[] = [];

  for (const mod of order) {
    const classes = byModule.get(mod.id) ?? [];
    if (classes.length === 0) continue;

    const moduleTitle = classes[0]?.module_title || mod.title;
    const split = classes.length > 1;

    if (!split) {
      const only = classes[0];
      if (viewerProfessorId && only.professor_id !== viewerProfessorId) continue;
      sections.push({
        key: `${mod.id}:${only.professor_id}`,
        moduleId: mod.id,
        moduleTitle,
        professorId: only.professor_id,
        professorName: only.professor_name,
        // Professor viewer: always "Sua turma" on their class, even with 1 professor.
        isOwnClass: Boolean(
          viewerProfessorId && only.professor_id === viewerProfessorId,
        ),
        isUnassigned: false,
        isSplitModule: false,
        studentIds: [...enrolledIds],
      });
      continue;
    }

    for (const cls of classes) {
      if (viewerProfessorId && cls.professor_id !== viewerProfessorId) continue;
      const studentIds = cls.student_ids.filter((id) => enrolledSet.has(id));
      sections.push({
        key: `${mod.id}:${cls.professor_id}`,
        moduleId: mod.id,
        moduleTitle,
        professorId: cls.professor_id,
        professorName: cls.professor_name,
        isOwnClass: Boolean(
          viewerProfessorId && cls.professor_id === viewerProfessorId,
        ),
        isUnassigned: false,
        isSplitModule: true,
        studentIds,
      });
    }

    if (includeUnassigned && !viewerProfessorId) {
      const allAssigned = new Set(
        classes.flatMap((cls) =>
          cls.student_ids.filter((id) => enrolledSet.has(id)),
        ),
      );
      const unassignedIds = enrolledIds.filter((id) => !allAssigned.has(id));
      if (unassignedIds.length > 0) {
        sections.push({
          key: `${mod.id}:unassigned`,
          moduleId: mod.id,
          moduleTitle,
          professorId: null,
          professorName: null,
          isOwnClass: false,
          isUnassigned: true,
          isSplitModule: true,
          studentIds: unassignedIds,
        });
      }
    }
  }

  return sections;
}

/** Alunos tab starts with every class section collapsed. */
export function defaultOpenSectionKeys(_sections: StudentClassSection[]): string[] {
  return [];
}

/** Whether one professor already closed this lesson for their own class. */
export function lessonClosedByProfessor(
  progress: CohortProgress | null | undefined,
  lessonId: string,
  professorId: string,
): boolean {
  const entry = progress?.lesson_classes.find((item) => item.lesson_id === lessonId);
  return (
    entry?.classes.some(
      (item) => item.professor_id === professorId && item.closed,
    ) ?? false
  );
}

/**
 * First active lesson this professor still owes on modules they teach.
 * Independent of other professors of the same module.
 */
export function nextLessonIdForProfessor(
  progress: CohortProgress | null | undefined,
  lessons: { id: string; moduleId: string }[],
  professorId: string,
  taughtModuleIds: Set<string>,
): string | null {
  if (!progress || !professorId) return null;
  for (const lesson of lessons) {
    if (!taughtModuleIds.has(lesson.moduleId)) continue;
    if (!lessonClosedByProfessor(progress, lesson.id, professorId)) {
      return lesson.id;
    }
  }
  return null;
}

export type PathProgressView = {
  completedLessonIds: string[];
  partialLessonIds: string[];
  delayedLessonIds: string[];
  currentLessonId: string | null;
  doneCount: number;
  scope: "class" | "cohort" | "student";
};

/**
 * Path / counters for the logged-in viewer.
 * Professors see their own class; admins/designers see the whole cohort.
 * Class scope omits partial/delayed — those are cohort coordination signals.
 */
export function pathProgressForViewer(
  progress: CohortProgress,
  viewerProfessorId?: string | null,
): PathProgressView {
  if (viewerProfessorId) {
    const completedLessonIds = progress.lesson_classes
      .filter((entry) =>
        entry.classes.some(
          (item) => item.professor_id === viewerProfessorId && item.closed,
        ),
      )
      .map((entry) => entry.lesson_id);
    return {
      completedLessonIds,
      partialLessonIds: [],
      delayedLessonIds: [],
      currentLessonId: progress.current_lesson_id,
      doneCount: completedLessonIds.length,
      scope: "class",
    };
  }

  return {
    completedLessonIds: progress.completed_lesson_ids,
    partialLessonIds: progress.partial_lesson_ids,
    delayedLessonIds: progress.lesson_classes
      .filter((item) => item.delayed)
      .map((item) => item.lesson_id),
    currentLessonId: progress.current_lesson_id,
    doneCount: progress.completed_lesson_ids.length,
    scope: "cohort",
  };
}

/**
 * Path for one student: unlocks of their own class per module.
 * No cohort partial/delayed — another professor being late is not their path.
 */
export function pathProgressForStudent(
  progress: CohortProgress,
  cohort: Cohort,
  studentId: string,
  lessons: { id: string; moduleId: string }[],
): PathProgressView {
  const completedLessonIds: string[] = [];
  for (const lesson of lessons) {
    if (
      lessonUnlockedForStudent(
        progress,
        cohort,
        lesson.id,
        lesson.moduleId,
        studentId,
      )
    ) {
      completedLessonIds.push(lesson.id);
    }
  }
  const completed = new Set(completedLessonIds);
  let currentLessonId: string | null = null;
  for (const lesson of lessons) {
    const studentClass = classForStudent(
      professorsForModule(cohort, lesson.moduleId),
      studentId,
    );
    if (!studentClass) continue;
    if (!completed.has(lesson.id)) {
      currentLessonId = lesson.id;
      break;
    }
  }
  return {
    completedLessonIds,
    partialLessonIds: [],
    delayedLessonIds: [],
    currentLessonId,
    doneCount: completedLessonIds.length,
    scope: "student",
  };
}

/** Context unlock for one student: their own class closed the lesson. */
export function lessonUnlockedForStudent(
  progress: CohortProgress | null | undefined,
  cohort: Cohort | null | undefined,
  lessonId: string,
  moduleId: string,
  studentId: string | null,
): boolean {
  if (!progress || !cohort || !studentId) return false;
  const studentClass = classForStudent(professorsForModule(cohort, moduleId), studentId);
  if (!studentClass) return false;
  const entry = progress.lesson_classes.find((item) => item.lesson_id === lessonId);
  return (
    entry?.classes.some(
      (item) => item.module_professor_id === studentClass.id && item.closed,
    ) ?? false
  );
}

export function assignmentsFromCohort(cohort: Cohort): ModuleAssignments {
  const next: ModuleAssignments = {};
  for (const mp of cohort.module_professors) {
    (next[mp.module_id] ??= []).push({
      professorId: mp.professor_id,
      studentIds: [...mp.student_ids],
    });
  }
  return next;
}

export function assignmentsPayload(
  assignments: ModuleAssignments,
): ModuleProfessorAssignment[] {
  return Object.entries(assignments).flatMap(([module_id, classes]) =>
    classes
      .filter((item) => item.professorId)
      .map((item) => ({
        module_id,
        professor_id: item.professorId,
        student_ids: classes.length > 1 ? item.studentIds : [],
      })),
  );
}

export function assignmentsEqual(
  current: ModuleAssignments,
  saved: ModuleProfessor[],
): boolean {
  const savedAssignments: ModuleAssignments = {};
  for (const mp of saved) {
    (savedAssignments[mp.module_id] ??= []).push({
      professorId: mp.professor_id,
      studentIds: [...mp.student_ids],
    });
  }
  const serialize = (assignments: ModuleAssignments) =>
    Object.entries(assignments)
      .map(([moduleId, classes]) => {
        const rendered = classes
          .map((item) => `${item.professorId}:${[...item.studentIds].sort().join(",")}`)
          .sort()
          .join("|");
        return `${moduleId}=${rendered}`;
      })
      .sort()
      .join(";");
  return serialize(current) === serialize(savedAssignments);
}

/** Students of a module with no professor yet -- what blocks lesson completion. */
export function unassignedStudentIds(
  classes: ModuleClassDraft[],
  enrolledIds: string[],
): string[] {
  if (classes.length <= 1) return [];
  const assigned = new Set(classes.flatMap((item) => item.studentIds));
  return enrolledIds.filter((id) => !assigned.has(id));
}

/** Split suggested when a module gains a second professor: reuse the previous
 *  module's division when the professors match, otherwise divide in order. */
export function suggestSplit(
  classes: ModuleClassDraft[],
  enrolledIds: string[],
  previousClasses: ModuleClassDraft[] = [],
): ModuleClassDraft[] {
  if (classes.length <= 1) {
    return classes.map((item) => ({ ...item, studentIds: [] }));
  }

  const remaining = new Set(enrolledIds);
  const next = classes.map((item) => {
    const inherited = previousClasses.find(
      (previous) => previous.professorId === item.professorId,
    );
    const studentIds = (inherited?.studentIds ?? []).filter((id) => remaining.has(id));
    for (const id of studentIds) remaining.delete(id);
    return { ...item, studentIds };
  });

  const leftover = enrolledIds.filter((id) => remaining.has(id));
  const inheritedAny = next.some((item) => item.studentIds.length > 0);
  leftover.forEach((id, index) => {
    const target = inheritedAny ? next[0] : next[index % next.length];
    target.studentIds = [...target.studentIds, id];
  });
  return next;
}

/** Move students to one professor (or null = Sem grupo). Exclusivity preserved. */
export function moveStudentsToProfessor(
  classes: ModuleClassDraft[],
  studentIds: string[],
  toProfessorId: string | null,
): ModuleClassDraft[] {
  const moving = new Set(studentIds);
  if (moving.size === 0) return classes;

  return classes.map((item) => {
    const without = item.studentIds.filter((id) => !moving.has(id));
    if (toProfessorId != null && item.professorId === toProfessorId) {
      return {
        ...item,
        studentIds: [...without, ...studentIds.filter((id) => !without.includes(id))],
      };
    }
    return { ...item, studentIds: without };
  });
}

/** Split enrolled students evenly across the module's professors. */
export function splitEvenly(
  classes: ModuleClassDraft[],
  enrolledIds: string[],
): ModuleClassDraft[] {
  return suggestSplit(classes, enrolledIds, []);
}

/** Reuse the previous module's division for matching professors; leftovers go to Sem grupo. */
export function copyDivisionFromPrevious(
  classes: ModuleClassDraft[],
  previousClasses: ModuleClassDraft[],
  enrolledIds: string[],
): ModuleClassDraft[] {
  if (classes.length <= 1) {
    return classes.map((item) => ({ ...item, studentIds: [] }));
  }

  const enrolled = new Set(enrolledIds);
  return classes.map((item) => {
    const inherited = previousClasses.find(
      (previous) => previous.professorId === item.professorId,
    );
    return {
      ...item,
      studentIds: (inherited?.studentIds ?? []).filter((id) => enrolled.has(id)),
    };
  });
}
