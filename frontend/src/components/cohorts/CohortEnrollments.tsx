import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../lib/api";
import {
  matchesLevelFilter,
  trackLevelSortRank,
  type LevelFilter,
  type StudentAssessments,
  type TrackLevelSummary,
} from "../../lib/assessments";
import type { Enrollment } from "../../lib/cohorts";
import type { Track } from "../../lib/tracks";
import { useAuth } from "../../lib/auth";
import { useConfirm } from "../../lib/confirm";
import { useApiAction } from "../../lib/useApiAction";
import { AssessmentLevelBadge } from "./AssessmentLevelBadge";
import { StudentAssessmentsPanel } from "./StudentAssessmentsPanel";
import { StudentEnrollModal } from "./StudentEnrollModal";

interface Props {
  cohortId: string;
  track: Track;
  onChanged: () => void;
}

type SortMode = "name" | "level";

const LEVEL_FILTERS: { value: LevelFilter; label: string }[] = [
  { value: "all", label: "Todos" },
  { value: "high", label: "Alto" },
  { value: "medium", label: "Médio" },
  { value: "low", label: "Baixo" },
  { value: "very_low", label: "Muito baixo" },
  { value: "no_evidence", label: "Sem evidência" },
  { value: "no_assessment", label: "Sem avaliação" },
];

function isNarrowViewport(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(max-width: 900px)").matches;
}

export function CohortEnrollments({ cohortId, track, onChanged }: Props) {
  const { user } = useAuth();
  const confirm = useConfirm();
  const runAction = useApiAction();
  // Professor is read-only on this tab — never enroll/remove.
  const canManageEnrollments =
    user?.role === "admin" || user?.role === "designer";
  const detailRef = useRef<HTMLDivElement>(null);

  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("name");
  const [levelFilter, setLevelFilter] = useState<LevelFilter>("all");
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [trackLevels, setTrackLevels] = useState<Record<string, TrackLevelSummary>>({});
  const [levelsLoading, setLevelsLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<Enrollment[]>(`/cohorts/${cohortId}/enrollments`);
      setEnrollments(data);
    } finally {
      setLoading(false);
    }
  }, [cohortId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (enrollments.length === 0) {
      setTrackLevels({});
      return;
    }
    let cancelled = false;
    setLevelsLoading(true);
    Promise.all(
      enrollments.map(async (enrollment) => {
        try {
          const { data } = await api.get<StudentAssessments>(
            `/cohorts/${cohortId}/students/${enrollment.student_id}/assessments`,
          );
          const trackRow = data.assessments.find((row) => row.scope === "track");
          const summary: TrackLevelSummary = trackRow
            ? { kind: "level", level: trackRow.level }
            : { kind: "missing" };
          return [enrollment.student_id, summary] as const;
        } catch {
          return [enrollment.student_id, { kind: "missing" } as TrackLevelSummary] as const;
        }
      }),
    )
      .then((rows) => {
        if (cancelled) return;
        setTrackLevels(Object.fromEntries(rows));
      })
      .finally(() => {
        if (!cancelled) setLevelsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cohortId, enrollments]);

  const enrolledIds = useMemo(
    () => new Set(enrollments.map((e) => e.student_id)),
    [enrollments],
  );

  const filteredEnrollments = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = enrollments.filter((e) => {
      if (
        q &&
        !e.student_name.toLowerCase().includes(q) &&
        !e.student_email.toLowerCase().includes(q)
      ) {
        return false;
      }
      return matchesLevelFilter(trackLevels[e.student_id], levelFilter);
    });

    list = [...list].sort((a, b) => {
      if (sortMode === "level") {
        const rankDiff =
          trackLevelSortRank(trackLevels[a.student_id]) -
          trackLevelSortRank(trackLevels[b.student_id]);
        if (rankDiff !== 0) return rankDiff;
      }
      return a.student_name.localeCompare(b.student_name, "pt-BR");
    });
    return list;
  }, [enrollments, query, levelFilter, sortMode, trackLevels]);

  const selectedEnrollment = useMemo(
    () => enrollments.find((e) => e.student_id === selectedStudentId) ?? null,
    [enrollments, selectedStudentId],
  );

  useEffect(() => {
    if (
      selectedStudentId &&
      !enrollments.some((e) => e.student_id === selectedStudentId)
    ) {
      setSelectedStudentId(null);
    }
  }, [enrollments, selectedStudentId]);

  function selectStudent(studentId: string) {
    setSelectedStudentId(studentId);
    if (isNarrowViewport()) {
      requestAnimationFrame(() => {
        detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  async function removeEnrollment(studentIdToRemove: string) {
    const enrollment = enrollments.find((e) => e.student_id === studentIdToRemove);
    const ok = await confirm({
      title: "Remover aluno",
      message: "Remover este aluno da turma?",
      confirmLabel: "Remover",
      tone: "danger",
    });
    if (!ok) return;
    setRemovingId(studentIdToRemove);
    await runAction({
      run: () => api.delete(`/cohorts/${cohortId}/enrollments/${studentIdToRemove}`),
      successMessage: enrollment
        ? `${enrollment.student_name} removido(a) da turma.`
        : "Aluno removido da turma.",
      errorMessage: "Não foi possível remover o aluno.",
      onSuccess: async () => {
        await load();
        onChanged();
      },
    });
    setRemovingId(null);
  }

  if (loading) return <p className="muted">Carregando alunos…</p>;

  return (
    <section className="cohort-students">
      <div className="cohort-students__toolbar">
        <p className="muted cohort-students__hint">
          Selecione um aluno para ver as avaliações da trilha, módulos e aulas.
        </p>
        {canManageEnrollments && (
          <button type="button" className="btn btn-primary" onClick={() => setModalOpen(true)}>
            Adicionar alunos
          </button>
        )}
      </div>

      {enrollments.length === 0 ? (
        <div className="empty-state cohort-students__empty">
          <p>Nenhum aluno matriculado ainda.</p>
          {canManageEnrollments && (
            <p className="muted" style={{ marginTop: 6 }}>
              Use o botão acima para matricular ou cadastrar alunos.
            </p>
          )}
        </div>
      ) : (
        <>
          <div className="cohort-students__controls">
            <div className="field cohort-students__search">
              <label htmlFor="cohort-students-search">Buscar</label>
              <input
                id="cohort-students-search"
                className="input"
                value={query}
                onChange={(ev) => setQuery(ev.target.value)}
                placeholder="Nome ou e-mail…"
              />
            </div>

            <div className="cohort-students__sort">
              <span className="cohort-students__control-label">Ordenar</span>
              <div className="cohort-students__chip-row" role="group" aria-label="Ordenação">
                <button
                  type="button"
                  className={`cohort-students__chip${sortMode === "name" ? " is-active" : ""}`}
                  onClick={() => setSortMode("name")}
                >
                  Nome
                </button>
                <button
                  type="button"
                  className={`cohort-students__chip${sortMode === "level" ? " is-active" : ""}`}
                  onClick={() => setSortMode("level")}
                >
                  Nível
                </button>
              </div>
            </div>
          </div>

          <div className="cohort-students__filters" role="group" aria-label="Filtrar por nível">
            {LEVEL_FILTERS.map((item) => (
              <button
                key={item.value}
                type="button"
                className={`cohort-students__chip${levelFilter === item.value ? " is-active" : ""}`}
                onClick={() => setLevelFilter(item.value)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <p className="muted cohort-students__count">
            {filteredEnrollments.length} de {enrollments.length}
            {levelsLoading ? " · carregando níveis…" : ""}
          </p>

          <div className="cohort-students__layout">
            <div className="cohort-students__list-col">
              {filteredEnrollments.length === 0 ? (
                <p className="muted cohort-students__filter-empty">Nenhum aluno encontrado.</p>
              ) : (
                <ul className="cohort-students__list">
                  {filteredEnrollments.map((e) => {
                    const selected = e.student_id === selectedStudentId;
                    const summary = trackLevels[e.student_id];
                    return (
                      <li key={e.id}>
                        <div
                          className={`cohort-students__row${selected ? " is-selected" : ""}${
                            canManageEnrollments ? " cohort-students__row--manageable" : ""
                          }`}
                        >
                          <button
                            type="button"
                            className="cohort-students__select"
                            onClick={() => selectStudent(e.student_id)}
                          >
                            <span className="cohort-students__name">{e.student_name}</span>
                            {summary?.kind === "level" ? (
                              <AssessmentLevelBadge level={summary.level} />
                            ) : (
                              <AssessmentLevelBadge missing />
                            )}
                          </button>
                          {canManageEnrollments ? (
                            <button
                              type="button"
                              className="cohort-students__remove"
                              disabled={removingId === e.student_id}
                              onClick={(ev) => {
                                ev.preventDefault();
                                ev.stopPropagation();
                                void removeEnrollment(e.student_id);
                              }}
                              aria-label={`Remover ${e.student_name}`}
                              title="Remover da turma"
                            >
                              {removingId === e.student_id ? "…" : "×"}
                            </button>
                          ) : null}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            <div
              ref={detailRef}
              id="cohort-student-assessments"
              className="cohort-students__detail-col"
            >
              {selectedEnrollment ? (
                <StudentAssessmentsPanel
                  key={selectedEnrollment.student_id}
                  cohortId={cohortId}
                  studentId={selectedEnrollment.student_id}
                  studentName={selectedEnrollment.student_name}
                  studentEmail={selectedEnrollment.student_email}
                  studentWhatsapp={selectedEnrollment.student_whatsapp}
                  track={track}
                />
              ) : (
                <div className="cohort-students__detail-empty">
                  <p>Selecione um aluno para ver as avaliações</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {canManageEnrollments && (
        <StudentEnrollModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          cohortId={cohortId}
          enrolledIds={enrolledIds}
          canCreate={canManageEnrollments}
          onEnrolled={() => {
            load();
            onChanged();
          }}
        />
      )}
    </section>
  );
}
