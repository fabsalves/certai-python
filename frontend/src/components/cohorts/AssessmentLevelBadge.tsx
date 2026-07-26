import {
  assessmentLevelLabel,
  type AssessmentLevel,
} from "../../lib/assessments";

type BadgeKind = AssessmentLevel | "no_evidence" | "no_assessment";

interface Props {
  /** Assessment level, null = insufficient evidence, undefined = no assessment yet. */
  level?: AssessmentLevel | null;
  /** Force the "sem avaliação" state (no track assessment row). */
  missing?: boolean;
  className?: string;
}

function kindFor(level: AssessmentLevel | null | undefined, missing?: boolean): BadgeKind {
  if (missing || level === undefined) return "no_assessment";
  if (level === null) return "no_evidence";
  return level;
}

function labelFor(kind: BadgeKind): string {
  if (kind === "no_assessment") return "Sem avaliação";
  if (kind === "no_evidence") return assessmentLevelLabel(null);
  return assessmentLevelLabel(kind);
}

export function AssessmentLevelBadge({ level, missing, className }: Props) {
  const kind = kindFor(level, missing);
  const tone =
    kind === "high"
      ? "high"
      : kind === "medium"
        ? "medium"
        : kind === "low" || kind === "very_low"
          ? "low"
          : "neutral";

  return (
    <span
      className={`assessment-level-badge assessment-level-badge--${tone}${
        className ? ` ${className}` : ""
      }`}
    >
      {labelFor(kind)}
    </span>
  );
}
