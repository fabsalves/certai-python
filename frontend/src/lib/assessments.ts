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

/** Batch track-level row from GET /cohorts/{id}/students/track-levels */
export interface CohortTrackLevel {
  student_id: string;
  level: AssessmentLevel | null;
  has_assessment: boolean;
}

export interface CohortTrackLevels {
  students: CohortTrackLevel[];
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

/** Short explanations for assessment states (native title / help copy). */
export const ASSESSMENT_STATE_HINTS = {
  no_evidence:
    "A IA avaliou e não encontrou demonstração suficiente para atribuir um nível.",
  no_assessment: "Ainda não há avaliação registrada para este escopo.",
  pending: "O aluno concluiu a aula, mas não há avaliação registrada.",
} as const;

/** What layered assessment is (Students tab help). */
export const ASSESSMENT_OVERVIEW_HINT =
  "A avaliação é feita por IA a partir das conversas do aluno, em três níveis: aula, módulo e trilha. Cada uma traz nível qualitativo, parecer e lacunas. Sem nota e sem percentual.";

export const ASSESSMENT_LEVEL_ORDER: AssessmentLevel[] = [
  "high",
  "medium",
  "low",
  "very_low",
];

/** Track-level summary for list panorama. */
export type TrackLevelSummary =
  | { kind: "level"; level: AssessmentLevel | null }
  | { kind: "missing" };

/** Lower rank = needs attention first when sorting by level. */
export function trackLevelSortRank(summary: TrackLevelSummary | undefined): number {
  // Missing assessment is absence of data: sort last, not first.
  if (summary == null || summary.kind === "missing") return 6;
  if (summary.level === null) return 1; // insufficient evidence: strongest alert
  const order: Record<AssessmentLevel, number> = {
    very_low: 2,
    low: 3,
    medium: 4,
    high: 5,
  };
  return order[summary.level] ?? 6;
}

export type LevelFilter =
  | "all"
  | AssessmentLevel
  | "no_evidence"
  | "no_assessment";

export function matchesLevelFilter(
  summary: TrackLevelSummary | undefined,
  filter: LevelFilter,
): boolean {
  if (filter === "all") return true;
  // Unknown while loading: don't treat as "Sem avaliação".
  if (summary == null) return false;
  if (filter === "no_assessment") {
    return summary.kind === "missing";
  }
  if (filter === "no_evidence") {
    return summary.kind === "level" && summary.level === null;
  }
  return summary.kind === "level" && summary.level === filter;
}

export function trackLevelFromBatch(row: CohortTrackLevel): TrackLevelSummary {
  if (!row.has_assessment) return { kind: "missing" };
  return { kind: "level", level: row.level };
}
