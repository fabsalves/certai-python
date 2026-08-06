import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import {
  ASSESSMENT_LEVEL_ORDER,
  ASSESSMENT_STATE_HINTS,
  assessmentLevelLabel,
  type AssessmentLevel,
  type LessonAssessments,
} from "../../lib/assessments";
import { Tooltip } from "../ui/Tooltip";
import { LessonAssessmentDistSkeleton } from "./LessonAssessmentDistSkeleton";

interface Props {
  cohortId: string;
  lessonId: string;
}

interface CountItem {
  key: string;
  label: string;
  count: number;
  hint?: string;
}

function DistributionHeading() {
  return (
    <div className="cohort-assessment-dist__heading">
      <div className="cohort-assessment-dist__heading-row">
        <p className="cohort-assessment-dist__label">Como a turma foi nesta aula</p>
        <Tooltip
          content={
            <>
              <p>
                <strong>Sem evidência suficiente:</strong> {ASSESSMENT_STATE_HINTS.no_evidence}
              </p>
              <p>
                <strong>Sem avaliação:</strong> {ASSESSMENT_STATE_HINTS.no_assessment}
              </p>
              <p>
                <strong>Avaliação pendente:</strong> {ASSESSMENT_STATE_HINTS.pending}
              </p>
            </>
          }
        >
          <button
            type="button"
            className="ui-help-icon"
            aria-label="O que significam os estados de avaliação"
          >
            ?
          </button>
        </Tooltip>
      </div>
    </div>
  );
}

export function LessonAssessmentDistribution({ cohortId, lessonId }: Props) {
  const [data, setData] = useState<LessonAssessments | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .get<LessonAssessments>(`/cohorts/${cohortId}/lessons/${lessonId}/assessments`)
      .then(({ data: payload }) => {
        if (!cancelled) setData(payload);
      })
      .catch(() => {
        if (!cancelled) {
          setData(null);
          setError("Não foi possível carregar as avaliações da aula.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cohortId, lessonId]);

  const items = useMemo((): CountItem[] => {
    if (!data) return [];
    const byLevel: Record<AssessmentLevel, number> = {
      very_low: 0,
      low: 0,
      medium: 0,
      high: 0,
    };
    let noEvidence = 0;
    for (const row of data.assessments) {
      if (row.level == null) {
        noEvidence += 1;
      } else {
        byLevel[row.level] += 1;
      }
    }
    const result: CountItem[] = [];
    for (const level of ASSESSMENT_LEVEL_ORDER) {
      if (byLevel[level] > 0) {
        result.push({
          key: level,
          label: assessmentLevelLabel(level),
          count: byLevel[level],
        });
      }
    }
    if (noEvidence > 0) {
      result.push({
        key: "no_evidence",
        label: "Sem evidência suficiente",
        count: noEvidence,
        hint: ASSESSMENT_STATE_HINTS.no_evidence,
      });
    }
    if (data.pending.length > 0) {
      result.push({
        key: "pending",
        label: "Avaliação pendente",
        count: data.pending.length,
        hint: ASSESSMENT_STATE_HINTS.pending,
      });
    }
    return result;
  }, [data]);

  if (loading) {
    return <LessonAssessmentDistSkeleton />;
  }

  if (error) {
    return (
      <div className="cohort-assessment-dist">
        <p className="form-error" style={{ margin: 0 }}>
          {error}
        </p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="cohort-assessment-dist">
        <DistributionHeading />
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>
          Ainda não há alunos que concluíram esta aula.
        </p>
      </div>
    );
  }

  return (
    <div className="cohort-assessment-dist">
      <DistributionHeading />
      <ul className="cohort-assessment-dist__list">
        {items.map((item) => (
          <li key={item.key} className="cohort-assessment-dist__item">
            <span className="cohort-assessment-dist__count">{item.count}</span>
            {item.hint ? (
              <Tooltip content={item.hint}>
                <span>{item.label}</span>
              </Tooltip>
            ) : (
              <span>{item.label}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
