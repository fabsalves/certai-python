export interface ModuleProfessor {
  module_id: string;
  module_title: string;
  professor_id: string;
  professor_name: string;
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

export interface CohortProgress {
  completed_lesson_ids: string[];
  current_lesson_id: string | null;
}

export interface CohortLessonNote {
  lesson_id: string;
  attachment_filename: string | null;
  has_attachment: boolean;
  has_audio: boolean;
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
}

export function uniqueProfessorNames(cohort: Cohort): string {
  return [...new Set(cohort.module_professors.map((mp) => mp.professor_name))].join(", ");
}

export function professorForModule(
  cohort: Cohort | null,
  moduleId: string,
): ModuleProfessor | undefined {
  return cohort?.module_professors.find((mp) => mp.module_id === moduleId);
}
