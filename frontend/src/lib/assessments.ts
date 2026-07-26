export type AssessmentScope = "lesson" | "module" | "track";

export type AssessmentLevel = "very_low" | "low" | "medium" | "high";

export interface StudentAssessment {
  id: string;
  student_id: string;
  student_name: string;
  scope: AssessmentScope;
  lesson_id: string | null;
  module_id: string | null;
  track_id: string | null;
  scope_title: string;
  level: AssessmentLevel | null;
  assessment: string;
  gaps: string;
  created_at: string;
}

export interface PendingAssessmentStudent {
  student_id: string;
  student_name: string;
}

export interface LessonAssessments {
  lesson_id: string;
  assessments: StudentAssessment[];
  pending: PendingAssessmentStudent[];
}

export interface StudentAssessments {
  student_id: string;
  student_name: string;
  assessments: StudentAssessment[];
}

const LEVEL_LABELS: Record<AssessmentLevel, string> = {
  very_low: "Muito baixo",
  low: "Baixo",
  medium: "Médio",
  high: "Alto",
};

/** Null level = AI judged insufficient evidence (not an error, not zero). */
export function assessmentLevelLabel(level: string | null | undefined): string {
  if (level == null) return "Sem evidência suficiente";
  return LEVEL_LABELS[level as AssessmentLevel] ?? level;
}

export const ASSESSMENT_LEVEL_ORDER: AssessmentLevel[] = [
  "high",
  "medium",
  "low",
  "very_low",
];
