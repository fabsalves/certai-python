import {
  ASSESSMENT_STATE_HINTS,
  assessmentLevelLabel,
  type AssessmentLevel,
} from "../../lib/assessments";
import { Tooltip } from "../ui/Tooltip";

type BadgeKind = AssessmentLevel | "no_evidence" | "no_assessment";

interface Props {
  /** Assessment level, null = insufficient evidence, undefined = no assessment yet. */
  level?: AssessmentLevel | null;
  /** Force the "sem avaliação" state (no track assessment row). */
  missing?: boolean;
  /**
   * In compact lists, use the short "Sem evidência" label.
   * Detail panels keep the full "Sem evidência suficiente".
   */
  compact?: boolean;
  className?: string;
}

function kindFor(level: AssessmentLevel | null | undefined, missing?: boolean): BadgeKind {
  if (missing || level === undefined) return "no_assessment";
  if (level === null) return "no_evidence";
  return level;
}

function labelFor(kind: BadgeKind, compact?: boolean): string {
  if (kind === "no_assessment") return "Sem avaliação";
  if (kind === "no_evidence") {
    return compact ? "Sem evidência" : assessmentLevelLabel(null);
  }
  return assessmentLevelLabel(kind);
}

function hintFor(kind: BadgeKind): string | null {
  if (kind === "no_assessment") return ASSESSMENT_STATE_HINTS.no_assessment;
  if (kind === "no_evidence") return ASSESSMENT_STATE_HINTS.no_evidence;
  return null;
}

export function AssessmentLevelBadge({ level, missing, compact, className }: Props) {
  const kind = kindFor(level, missing);
  const label = labelFor(kind, compact);
  const hint = hintFor(kind);
  const tone =
    kind === "high"
      ? "high"
      : kind === "medium"
        ? "medium"
        : kind === "low"
          ? "low"
          : kind === "very_low"
            ? "very-low"
            : "neutral";

  const badge = (
    <span
      className={`assessment-level-badge assessment-level-badge--${tone}${
        className ? ` ${className}` : ""
      }`}
    >
      {label}
    </span>
  );

  if (!hint) return badge;
  return <Tooltip content={hint}>{badge}</Tooltip>;
}

/** Placeholder while track levels are still loading. Never implies "Sem avaliação". */
export function AssessmentLevelBadgeSkeleton({ className }: { className?: string }) {
  return (
    <span
      className={`assessment-level-badge assessment-level-badge--skeleton${
        className ? ` ${className}` : ""
      }`}
      aria-hidden
    />
  );
}
