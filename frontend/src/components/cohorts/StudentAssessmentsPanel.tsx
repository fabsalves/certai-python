import axios from "axios";
import { type ReactNode, useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import {
  ASSESSMENT_STATE_HINTS,
  formatAssessmentWhen,
  type StudentAssessment,
  type StudentAssessments,
} from "../../lib/assessments";
import { sortedLessons, sortedModules, type Track } from "../../lib/tracks";
import { formatWhatsappDisplay } from "../../lib/validation";
import { useAuth } from "../../lib/auth";
import type { UserOption } from "../../lib/users";
import { AssessmentLevelBadge } from "./AssessmentLevelBadge";
import { MicroScoresModal } from "./MicroScoresModal";
import { StudentAssessmentsSkeleton } from "./StudentAssessmentsSkeleton";
import { StudentEditModal } from "./StudentEditModal";

interface Props {
  cohortId: string;
  studentId: string;
  studentName: string;
  studentEmail: string;
  studentWhatsapp?: string | null;
  track: Track;
  /** 404: student no longer enrolled (stale page / removed). Parent clears selection. */
  onNotEnrolled?: () => void;
  onStudentUpdated?: (student: UserOption) => void;
}

type ScopeEyebrow = "Módulo" | "Aula";

function AssessmentScopeCard({
  eyebrow,
  title,
  row,
  defaultOpen,
  nested,
  onViewEvidence,
}: {
  eyebrow: ScopeEyebrow;
  title: string;
  row: StudentAssessment | null;
  defaultOpen: boolean;
  /** Lesson cards rendered inside this card when open. */
  nested?: ReactNode;
  /** Lesson-only: open micro-scores modal. */
  onViewEvidence?: () => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const hasNested = nested != null;
  const canExpand = row != null || hasNested || Boolean(onViewEvidence);
  const gapsText = row?.gaps.trim() ?? "";
  const assessmentText = row?.assessment.trim() ?? "";

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
            {row && (assessmentText.length > 0 || gapsText.length > 0) && (
              <div className="student-assessment-card__body">
                {assessmentText ? (
                  <div className="student-assessment-card__field">
                    <span className="student-assessment-card__label">Parecer</span>
                    <p className="student-assessment-card__text">{assessmentText}</p>
                  </div>
                ) : null}
                {gapsText ? (
                  <div className="student-assessment-card__field">
                    <span className="student-assessment-card__label">Lacunas</span>
                    <p className="student-assessment-card__text">{gapsText}</p>
                  </div>
                ) : null}
              </div>
            )}
            {(row?.created_at || onViewEvidence) && (
              <div className="student-assessment-card__footer">
                {row?.created_at ? (
                  <p className="muted student-assessment-card__when">
                    Avaliado em {formatAssessmentWhen(row.created_at)}
                  </p>
                ) : (
                  <span />
                )}
                {onViewEvidence ? (
                  <button
                    type="button"
                    className="student-assessment-card__evidence"
                    onClick={(e) => {
                      e.stopPropagation();
                      onViewEvidence();
                    }}
                  >
                    Evidências
                  </button>
                ) : null}
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
  onStudentUpdated,
}: Props) {
  const { user } = useAuth();
  const canEditStudent = user?.role === "admin";
  const [editOpen, setEditOpen] = useState(false);
  const [data, setData] = useState<StudentAssessments | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [evidenceLesson, setEvidenceLesson] = useState<{
    id: string;
    title: string;
  } | null>(null);

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

  const modules = useMemo(
    () => sortedModules(track).filter((mod) => mod.is_active),
    [track],
  );

  const activeLessons = useMemo(
    () =>
      modules.flatMap((mod) =>
        sortedLessons(mod).filter((lesson) => lesson.is_active),
      ),
    [modules],
  );

  const lessonAssessedCount = useMemo(() => {
    let count = 0;
    for (const lesson of activeLessons) {
      if (byKey.has(`lesson:${lesson.id}`)) count += 1;
    }
    return count;
  }, [activeLessons, byKey]);

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
  const trackText = trackAssessment?.assessment.trim() ?? "";
  const trackGaps = trackAssessment?.gaps.trim() ?? "";

  return (
    <div className="student-assessments-panel">
      <header className="student-assessments-panel__head">
        <div className="student-assessments-panel__head-main">
          <h3 className="student-assessments-panel__name">{studentName}</h3>
          <p className="muted student-assessments-panel__contact">
            {studentEmail}
            {studentWhatsapp ? ` · WhatsApp ${formatWhatsappDisplay(studentWhatsapp)}` : ""}
          </p>
        </div>
        {canEditStudent && (
          <button
            type="button"
            className="btn btn-ghost btn-sm student-assessments-panel__edit"
            onClick={() => setEditOpen(true)}
          >
            Editar
          </button>
        )}
      </header>

      {canEditStudent && (
        <StudentEditModal
          open={editOpen}
          onClose={() => setEditOpen(false)}
          studentId={studentId}
          studentName={studentName}
          studentEmail={studentEmail}
          studentWhatsapp={studentWhatsapp}
          onUpdated={(student) => onStudentUpdated?.(student)}
        />
      )}

      <section className="student-assessments-panel__hero" aria-label="Avaliação da trilha">
        <div className="student-assessments-panel__hero-top">
          <span className="student-assessments-panel__hero-eyebrow">Trilha</span>
          {trackAssessment ? (
            <AssessmentLevelBadge level={trackAssessment.level} />
          ) : (
            <AssessmentLevelBadge missing />
          )}
        </div>
        <h4 className="student-assessments-panel__hero-title">{track.title}</h4>
        <p className="muted student-assessments-panel__hero-meta">
          {lessonAssessedCount}/{activeLessons.length} aulas com avaliação
        </p>

        {trackAssessment ? (
          <>
            {trackText ? (
              <div className="student-assessments-panel__hero-field">
                <span className="student-assessments-panel__hero-label">Parecer</span>
                <p className="student-assessments-panel__hero-text">{trackText}</p>
              </div>
            ) : trackAssessment.level === null ? (
              <p className="muted student-assessments-panel__hero-text">
                {ASSESSMENT_STATE_HINTS.no_evidence}
              </p>
            ) : null}
            {trackGaps ? (
              <div className="student-assessments-panel__hero-field">
                <span className="student-assessments-panel__hero-label">Lacunas</span>
                <p className="student-assessments-panel__hero-text">{trackGaps}</p>
              </div>
            ) : null}
            {trackAssessment.created_at ? (
              <p className="muted student-assessments-panel__hero-when">
                Avaliado em {formatAssessmentWhen(trackAssessment.created_at)}
              </p>
            ) : null}
          </>
        ) : (
          <p className="muted student-assessments-panel__hero-text">
            {ASSESSMENT_STATE_HINTS.no_assessment}
          </p>
        )}
      </section>

      <div className="student-assessments-panel__tree">
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
                        onViewEvidence={() =>
                          setEvidenceLesson({ id: lesson.id, title: lesson.title })
                        }
                      />
                    ))}
                  </>
                ) : undefined
              }
            />
          );
        })}
      </div>

      <MicroScoresModal
        open={evidenceLesson != null}
        onClose={() => setEvidenceLesson(null)}
        cohortId={cohortId}
        studentId={studentId}
        lessonId={evidenceLesson?.id ?? ""}
        studentName={studentName}
        lessonTitle={evidenceLesson?.title}
      />
    </div>
  );
}
