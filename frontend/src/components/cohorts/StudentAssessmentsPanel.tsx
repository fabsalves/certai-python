import { useEffect, useMemo, useState } from "react";
import { api } from "../../lib/api";
import {
  assessmentLevelLabel,
  type StudentAssessment,
  type StudentAssessments,
} from "../../lib/assessments";
import { sortedLessons, sortedModules, type Track } from "../../lib/tracks";

interface Props {
  cohortId: string;
  studentId: string;
  studentName: string;
  track: Track;
}

function AssessmentCard({ row }: { row: StudentAssessment }) {
  return (
    <article className="student-assessment-card">
      <div className="student-assessment-card__head">
        <h4 className="student-assessment-card__title">{row.scope_title || "Avaliação"}</h4>
        <span className="tag">{assessmentLevelLabel(row.level)}</span>
      </div>
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
    </article>
  );
}

function MissingCard({ title }: { title: string }) {
  return (
    <article className="student-assessment-card student-assessment-card--missing">
      <div className="student-assessment-card__head">
        <h4 className="student-assessment-card__title">{title}</h4>
        <span className="muted" style={{ fontSize: 13 }}>
          Ainda sem avaliação
        </span>
      </div>
    </article>
  );
}

export function StudentAssessmentsPanel({
  cohortId,
  studentId,
  studentName,
  track,
}: Props) {
  const [data, setData] = useState<StudentAssessments | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .get<StudentAssessments>(`/cohorts/${cohortId}/students/${studentId}/assessments`)
      .then(({ data: payload }) => {
        if (!cancelled) setData(payload);
      })
      .catch(() => {
        if (!cancelled) {
          setData(null);
          setError("Não foi possível carregar as avaliações do aluno.");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cohortId, studentId]);

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
    return (
      <div className="student-assessments-panel">
        <p className="muted">Carregando avaliações de {studentName}…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="student-assessments-panel">
        <p className="form-error">{error}</p>
      </div>
    );
  }

  const trackAssessment = byKey.get(`track:${track.id}`);
  const modules = sortedModules(track).filter((mod) => mod.is_active);

  return (
    <div className="student-assessments-panel">
      <header className="student-assessments-panel__head">
        <h3 style={{ margin: 0 }}>Avaliações de {studentName}</h3>
        <p className="muted" style={{ marginTop: 6, fontSize: 14 }}>
          Parecer, nível e lacunas por trilha, módulo e aula.
        </p>
      </header>

      <section className="student-assessments-panel__section">
        <h4 className="student-assessments-panel__section-title">Trilha</h4>
        {trackAssessment ? (
          <AssessmentCard row={trackAssessment} />
        ) : (
          <MissingCard title={track.title} />
        )}
      </section>

      {modules.map((mod) => {
        const moduleAssessment = byKey.get(`module:${mod.id}`);
        const lessons = sortedLessons(mod).filter((lesson) => lesson.is_active);
        return (
          <section key={mod.id} className="student-assessments-panel__section">
            <h4 className="student-assessments-panel__section-title">Módulo · {mod.title}</h4>
            {moduleAssessment ? (
              <AssessmentCard row={moduleAssessment} />
            ) : (
              <MissingCard title={mod.title} />
            )}
            <div className="student-assessments-panel__lessons">
              {lessons.map((lesson) => {
                const lessonAssessment = byKey.get(`lesson:${lesson.id}`);
                return lessonAssessment ? (
                  <AssessmentCard key={lesson.id} row={lessonAssessment} />
                ) : (
                  <MissingCard key={lesson.id} title={lesson.title} />
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
