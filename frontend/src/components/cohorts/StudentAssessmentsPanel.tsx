import axios from "axios";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import type { StudentAssessment, StudentAssessments } from "../../lib/assessments";
import { sortedLessons, sortedModules, type Track } from "../../lib/tracks";
import { maskPhoneBR } from "../../lib/validation";
import { AssessmentLevelBadge } from "./AssessmentLevelBadge";
import { StudentAssessmentsSkeleton } from "./StudentAssessmentsSkeleton";

interface Props {
  cohortId: string;
  studentId: string;
  studentName: string;
  studentEmail: string;
  studentWhatsapp?: string | null;
  track: Track;
  /** 404: student no longer enrolled (stale page / removed). Parent clears selection. */
  onNotEnrolled?: () => void;
}

type ScopeEyebrow = "Trilha" | "Módulo" | "Aula";

function AssessmentScopeCard({
  eyebrow,
  title,
  row,
  defaultOpen,
  nested,
}: {
  eyebrow: ScopeEyebrow;
  title: string;
  row: StudentAssessment | null;
  defaultOpen: boolean;
  /** Lesson cards (or other nested scope cards) rendered inside this card when open. */
  nested?: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const hasNested = nested != null;
  const canExpand = row != null || hasNested;

  return (
    <article
      className={`student-assessment-card${open ? " is-open" : ""}${
        row == null ? " student-assessment-card--missing" : ""
      }${hasNested ? " student-assessment-card--parent" : ""}`}
    >
      <button
        type="button"
        className="student-assessment-card__toggle"
        onClick={() => {
          if (canExpand) setOpen((v) => !v);
        }}
        aria-expanded={open}
        disabled={!canExpand}
      >
        <div className="student-assessment-card__toggle-main">
          <span className="student-assessment-card__eyebrow">{eyebrow}</span>
          <h4 className="student-assessment-card__title">{title}</h4>
        </div>
        <div className="student-assessment-card__toggle-meta">
          {row ? (
            <AssessmentLevelBadge level={row.level} />
          ) : (
            <AssessmentLevelBadge missing />
          )}
          {canExpand && (
            <span className={`student-assessment-card__chevron${open ? " is-open" : ""}`} aria-hidden>
              ▾
            </span>
          )}
        </div>
      </button>

      {canExpand && (
        <div
          className={`student-assessment-card__collapse${open ? " is-open" : ""}`}
          aria-hidden={!open}
        >
          <div className="student-assessment-card__collapse-inner">
            {row && (
              <div className="student-assessment-card__body">
                <div className="student-assessment-card__field">
                  <span className="student-assessment-card__label">Parecer</span>
                  {row.assessment.trim() ? (
                    <p className="student-assessment-card__text">{row.assessment.trim()}</p>
                  ) : (
                    <p className="muted student-assessment-card__empty">Nenhum</p>
                  )}
                </div>
                {row.level != null && (
                  <div className="student-assessment-card__field">
                    <span className="student-assessment-card__label">Lacunas</span>
                    {row.gaps.trim() ? (
                      <p className="student-assessment-card__text">{row.gaps.trim()}</p>
                    ) : (
                      <p className="muted student-assessment-card__empty">Nenhuma</p>
                    )}
                  </div>
                )}
              </div>
            )}
            {hasNested && (
              <div className="student-assessment-card__nested">{nested}</div>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

export function StudentAssessmentsPanel({
  cohortId,
  studentId,
  studentName,
  studentEmail,
  studentWhatsapp,
  track,
  onNotEnrolled,
}: Props) {
  const [data, setData] = useState<StudentAssessments | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let notEnrolled = false;
    setLoading(true);
    setError("");
    api
      .get<StudentAssessments>(`/cohorts/${cohortId}/students/${studentId}/assessments`)
      .then(({ data: payload }) => {
        if (!cancelled) setData(payload);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setData(null);
        // 404: not enrolled anymore (stale list after seed/removal), not a hard failure.
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          notEnrolled = true;
          onNotEnrolled?.();
          return;
        }
        setError("Não foi possível carregar as avaliações do aluno.");
      })
      .finally(() => {
        // Keep loading until parent clears selection on 404 (avoids empty-tree flash).
        if (!cancelled && !notEnrolled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cohortId, studentId, onNotEnrolled]);

  const byKey = useMemo(() => {
    const map = new Map<string, StudentAssessment>();
    for (const row of data?.assessments ?? []) {
      if (row.scope === "track" && row.track_id) map.set(`track:${row.track_id}`, row);
      if (row.scope === "module" && row.module_id) map.set(`module:${row.module_id}`, row);
      if (row.scope === "lesson" && row.lesson_id) map.set(`lesson:${row.lesson_id}`, row);
    }
    return map;
  }, [data]);

  if (loading) {
    return <StudentAssessmentsSkeleton />;
  }

  if (error) {
    return (
      <div className="student-assessments-panel">
        <p className="form-error">{error}</p>
      </div>
    );
  }

  const trackAssessment = byKey.get(`track:${track.id}`) ?? null;
  const modules = sortedModules(track).filter((mod) => mod.is_active);

  return (
    <div className="student-assessments-panel">
      <header className="student-assessments-panel__head">
        <h3 className="student-assessments-panel__name">{studentName}</h3>
        <p className="muted student-assessments-panel__contact">
          {studentEmail}
          {studentWhatsapp
            ? ` · WhatsApp ${maskPhoneBR(studentWhatsapp.replace(/^55/, ""))}`
            : ""}
        </p>
      </header>

      <div className="student-assessments-panel__tree">
        <AssessmentScopeCard
          eyebrow="Trilha"
          title={track.title}
          row={trackAssessment}
          defaultOpen
        />

        {modules.map((mod) => {
          const moduleAssessment = byKey.get(`module:${mod.id}`) ?? null;
          const lessons = sortedLessons(mod).filter((lesson) => lesson.is_active);
          return (
            <AssessmentScopeCard
              key={mod.id}
              eyebrow="Módulo"
              title={mod.title}
              row={moduleAssessment}
              defaultOpen={false}
              nested={
                lessons.length > 0 ? (
                  <>
                    {lessons.map((lesson) => (
                      <AssessmentScopeCard
                        key={lesson.id}
                        eyebrow="Aula"
                        title={lesson.title}
                        row={byKey.get(`lesson:${lesson.id}`) ?? null}
                        defaultOpen={false}
                      />
                    ))}
                  </>
                ) : undefined
              }
            />
          );
        })}
      </div>
    </div>
  );
}
