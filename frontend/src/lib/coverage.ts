import { api } from "./api";

/** Where a covered segment sits relative to the session's anchor lesson. */
export type CoverageKind = "planned" | "carryover" | "advance";
export type CoverageExtent = "full" | "partial";

export interface CoverageSegment {
  lesson_id: string;
  kind: CoverageKind;
  extent: CoverageExtent;
  covered: string;
  pending: string;
  source: "ai" | "professor";
  lesson_title: string;
}

export interface CoverageCandidate {
  lesson_id: string;
  lesson_title: string;
  is_anchor: boolean;
  /** What this lesson already owed before this session. */
  standing_pending: string;
}

export interface CoverageProposal {
  anchor_lesson_id: string;
  segments: CoverageSegment[];
  /** The window a lesson may be added from, when the AI missed one. */
  candidates: CoverageCandidate[];
  /** False when the AI call failed and the anchor-only default came back. */
  from_ai: boolean;
}

export const COVERAGE_TEXT_MAX = 2000;

export function coverageProposePath(cohortId: string): string {
  return `/cohorts/${cohortId}/propose-coverage`;
}

export function playgroundCoverageProposePath(
  cohortId: string,
  professorId: string,
): string {
  return `/admin/playground/cohorts/${cohortId}/professors/${professorId}/propose-coverage`;
}

/** Ask the AI what the session actually covered, from the professor's report. */
export async function proposeCoverage(
  path: string,
  lessonId: string,
  transcript: string,
): Promise<CoverageProposal> {
  const form = new FormData();
  form.append("lesson_id", lessonId);
  form.append("transcript", transcript);
  const { data } = await api.post<CoverageProposal>(path, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

const ORIGIN_LABELS: Record<CoverageKind, string> = {
  planned: "Aula do dia",
  carryover: "Pendência da aula anterior",
  advance: "Adiantado da aula seguinte",
};

export function originLabel(kind: CoverageKind): string {
  return ORIGIN_LABELS[kind];
}

export function extentLabel(extent: CoverageExtent): string {
  return extent === "full" ? "coberta por completo" : "coberta em parte";
}

/** True when the session went exactly as planned -- nothing worth showing. */
export function isPlainCoverage(segments: CoverageSegment[]): boolean {
  return (
    segments.length <= 1 &&
    segments.every(
      (item) =>
        item.kind === "planned" &&
        item.extent === "full" &&
        !item.covered.trim() &&
        !item.pending.trim(),
    )
  );
}

/** The payload the completion form carries; titles stay client-side. */
export function toSubmitPayload(segments: CoverageSegment[]) {
  return segments.map(({ lesson_title: _title, ...rest }) => rest);
}
