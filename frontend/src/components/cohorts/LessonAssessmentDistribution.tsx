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
import { MicroScoresModal } from "./MicroScoresModal";

interface Props {
  cohortId: string;
  lessonId: string;
  /** Open Alunos dossier for this student (Andamento → Alunos bridge). */
  onOpenStudent?: (studentId: string) => void;
}

interface BucketStudent {
  student_id: string;
  student_name: string;
}

interface CountItem {
  key: string;
  label: string;
  count: number;
  hint?: string;
  students: BucketStudent[];
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

function sortByName(a: BucketStudent, b: BucketStudent): number {
  return a.student_name.localeCompare(b.student_name, "pt-BR");
}

export function LessonAssessmentDistribution({
  cohortId,
  lessonId,
  onOpenStudent,
}: Props) {
  const [data, setData] = useState<LessonAssessments | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [evidenceStudent, setEvidenceStudent] = useState<BucketStudent | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    setOpenKey(null);
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
    const byLevel: Record<AssessmentLevel, BucketStudent[]> = {
      very_low: [],
      low: [],
      medium: [],
      high: [],
    };
    const noEvidence: BucketStudent[] = [];
    for (const row of data.assessments) {
      const student = {
        student_id: row.student_id,
        student_name: row.student_name,
      };
      if (row.level == null) {
        noEvidence.push(student);
      } else {
        byLevel[row.level].push(student);
      }
    }
    const result: CountItem[] = [];
    for (const level of ASSESSMENT_LEVEL_ORDER) {
      const students = [...byLevel[level]].sort(sortByName);
      if (students.length > 0) {
        result.push({
          key: level,
          label: assessmentLevelLabel(level),
          count: students.length,
          students,
        });
      }
    }
    if (noEvidence.length > 0) {
      result.push({
        key: "no_evidence",
        label: "Sem evidência suficiente",
        count: noEvidence.length,
        hint: ASSESSMENT_STATE_HINTS.no_evidence,
        students: [...noEvidence].sort(sortByName),
      });
    }
    if (data.pending.length > 0) {
      const pendingStudents = [...data.pending]
        .map((row) => ({
          student_id: row.student_id,
          student_name: row.student_name,
        }))
        .sort(sortByName);
      result.push({
        key: "pending",
        label: "Avaliação pendente",
        count: pendingStudents.length,
        hint: ASSESSMENT_STATE_HINTS.pending,
        students: pendingStudents,
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
        {items.map((item) => {
          const open = openKey === item.key;
          const labelNode = item.hint ? (
            <Tooltip content={item.hint}>
              <span>{item.label}</span>
            </Tooltip>
          ) : (
            <span>{item.label}</span>
          );
          return (
            <li
              key={item.key}
              className={`cohort-assessment-dist__item${open ? " is-open" : ""}`}
            >
              <button
                type="button"
                className="cohort-assessment-dist__bucket"
                onClick={() => setOpenKey(open ? null : item.key)}
                aria-expanded={open}
              >
                <span className="cohort-assessment-dist__count">{item.count}</span>
                {labelNode}
                <span
                  className={`cohort-assessment-dist__chevron${open ? " is-open" : ""}`}
                  aria-hidden
                >
                  ▾
                </span>
              </button>
              {open && (
                <ul className="cohort-assessment-dist__students">
                  {item.students.map((student) => (
                    <li key={student.student_id} className="cohort-assessment-dist__student-row">
                      {onOpenStudent ? (
                        <button
                          type="button"
                          className="cohort-assessment-dist__student"
                          onClick={() => onOpenStudent(student.student_id)}
                        >
                          {student.student_name}
                        </button>
                      ) : (
                        <span className="cohort-assessment-dist__student-static">
                          {student.student_name}
                        </span>
                      )}
                      <button
                        type="button"
                        className="cohort-assessment-dist__evidence"
                        onClick={() => setEvidenceStudent(student)}
                        aria-label={`Ver evidências de ${student.student_name}`}
                      >
                        Evidências
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
      {onOpenStudent ? (
        <p className="muted cohort-assessment-dist__hint">
          Toque no nome para a trilha; em Evidências, os registros da Lira nesta aula.
        </p>
      ) : (
        <p className="muted cohort-assessment-dist__hint">
          Em Evidências, os registros da Lira nesta aula.
        </p>
      )}

      <MicroScoresModal
        open={evidenceStudent != null}
        onClose={() => setEvidenceStudent(null)}
        cohortId={cohortId}
        studentId={evidenceStudent?.student_id ?? ""}
        lessonId={lessonId}
        studentName={evidenceStudent?.student_name ?? ""}
      />
    </div>
  );
}
