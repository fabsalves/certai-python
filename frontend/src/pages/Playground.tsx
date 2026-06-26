import { useCallback, useEffect, useMemo, useState } from "react";
import { CohortPathPreview } from "../components/cohorts/CohortPathPreview";
import { LessonReportCapture } from "../components/cohorts/LessonReportCapture";
import { PageHeader } from "../components/layout/PageHeader";
import { PlaygroundChat } from "../components/playground/PlaygroundChat";
import { api } from "../lib/api";
import type { Cohort, CohortProgress, Enrollment } from "../lib/cohorts";
import { professorForModule } from "../lib/cohorts";
import {
  playgroundCompletePath,
  playgroundTranscribePath,
} from "../lib/playground";
import { sortedLessons, sortedModules, type Track } from "../lib/tracks";

type SessionMode = "student" | "professor";

function findLessonModule(track: Track, lessonId: string) {
  for (const mod of sortedModules(track)) {
    const lesson = sortedLessons(mod).find((l) => l.id === lessonId);
    if (lesson) return { module: mod, lesson };
  }
  return null;
}

export function Playground() {
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [cohortId, setCohortId] = useState("");
  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [track, setTrack] = useState<Track | null>(null);
  const [progress, setProgress] = useState<CohortProgress | null>(null);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [mode, setMode] = useState<SessionMode>("student");
  const [studentId, setStudentId] = useState("");
  const [professorId, setProfessorId] = useState("");
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const refreshProgress = useCallback(async (id: string) => {
    const { data } = await api.get<CohortProgress>(`/cohorts/${id}/progress`);
    setProgress(data);
    return data;
  }, []);

  useEffect(() => {
    api
      .get<Cohort[]>("/cohorts")
      .then((res) => {
        setCohorts(res.data);
        if (res.data.length > 0) setCohortId(res.data[0].id);
      })
      .catch(() => setLoadError("Não foi possível carregar as turmas."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!cohortId) return;

    let cancelled = false;
    setLoadError("");

    Promise.all([
      api.get<Cohort>(`/cohorts/${cohortId}`),
      api.get<Track>(`/cohorts/${cohortId}/track`),
      api.get<CohortProgress>(`/cohorts/${cohortId}/progress`),
      api.get<Enrollment[]>(`/cohorts/${cohortId}/enrollments`),
    ])
      .then(([cohortRes, trackRes, progressRes, enrollmentsRes]) => {
        if (cancelled) return;
        setCohort(cohortRes.data);
        setTrack(trackRes.data);
        setProgress(progressRes.data);
        setEnrollments(enrollmentsRes.data);
        setSelectedLessonId(
          progressRes.data.current_lesson_id ?? progressRes.data.completed_lesson_ids.at(-1) ?? null,
        );
        setStudentId((prev) => {
          if (prev && enrollmentsRes.data.some((e) => e.student_id === prev)) return prev;
          return enrollmentsRes.data[0]?.student_id ?? "";
        });
        setProfessorId((prev) => {
          const ids = cohortRes.data.module_professors.map((mp) => mp.professor_id);
          if (prev && ids.includes(prev)) return prev;
          return ids[0] ?? "";
        });
      })
      .catch(() => {
        if (!cancelled) setLoadError("Não foi possível carregar os dados da turma.");
      });

    return () => {
      cancelled = true;
    };
  }, [cohortId]);

  const professors = useMemo(() => {
    if (!cohort) return [];
    const seen = new Set<string>();
    return cohort.module_professors.filter((mp) => {
      if (seen.has(mp.professor_id)) return false;
      seen.add(mp.professor_id);
      return true;
    });
  }, [cohort]);

  const selectedLesson = useMemo(() => {
    if (!track || !selectedLessonId) return null;
    return findLessonModule(track, selectedLessonId);
  }, [track, selectedLessonId]);

  const lessonProfessor = useMemo(() => {
    if (!cohort || !selectedLesson) return undefined;
    return professorForModule(cohort, selectedLesson.module.id);
  }, [cohort, selectedLesson]);

  useEffect(() => {
    if (mode === "professor" && lessonProfessor) {
      setProfessorId(lessonProfessor.professor_id);
    }
  }, [mode, lessonProfessor, selectedLessonId]);

  const completedSet = useMemo(
    () => new Set(progress?.completed_lesson_ids ?? []),
    [progress],
  );

  const canStudentChat =
    !!selectedLessonId &&
    (selectedLessonId === progress?.current_lesson_id || completedSet.has(selectedLessonId));

  const canProfessorComplete =
    mode === "professor" &&
    !!selectedLessonId &&
    selectedLessonId === progress?.current_lesson_id &&
    !!lessonProfessor &&
    professorId === lessonProfessor.professor_id;

  const selectedStudent = enrollments.find((e) => e.student_id === studentId);
  const selectedProfessor = professors.find((p) => p.professor_id === professorId);

  if (loading) {
    return <p className="muted">Carregando playground…</p>;
  }

  if (cohorts.length === 0) {
    return (
      <>
        <PageHeader
          title="Playground"
          description="Ambiente de testes da IA. Crie uma turma com alunos matriculados para começar."
        />
        <div className="empty-state card">
          <p>Nenhuma turma disponível.</p>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Playground"
        description="Teste a Lira como aluno ou professor. A sessão é direcionada pelo backend com segregação por turma e papel."
      />

      {loadError && <div className="form-error" style={{ marginBottom: 16 }}>{loadError}</div>}

      <div className="playground-toolbar card">
        <div className="playground-toolbar__row">
          <div className="field playground-toolbar__field">
            <label htmlFor="playground-cohort">Turma</label>
            <select
              id="playground-cohort"
              className="input"
              value={cohortId}
              onChange={(ev) => setCohortId(ev.target.value)}
            >
              {cohorts.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} — {item.track_title}
                </option>
              ))}
            </select>
          </div>

          <div className="field playground-toolbar__field">
            <label htmlFor="playground-mode">Papel da sessão</label>
            <select
              id="playground-mode"
              className="input"
              value={mode}
              onChange={(ev) => setMode(ev.target.value as SessionMode)}
            >
              <option value="student">Aluno — chat com a Lira</option>
              <option value="professor">Professor — encerrar aula</option>
            </select>
          </div>

          {mode === "student" ? (
            <div className="field playground-toolbar__field">
              <label htmlFor="playground-student">Agir como</label>
              <select
                id="playground-student"
                className="input"
                value={studentId}
                onChange={(ev) => setStudentId(ev.target.value)}
                disabled={enrollments.length === 0}
              >
                {enrollments.length === 0 ? (
                  <option value="">Sem alunos matriculados</option>
                ) : (
                  enrollments.map((item) => (
                    <option key={item.student_id} value={item.student_id}>
                      {item.student_name} ({item.student_email})
                    </option>
                  ))
                )}
              </select>
            </div>
          ) : (
            <div className="field playground-toolbar__field">
              <label htmlFor="playground-professor">Agir como</label>
              <select
                id="playground-professor"
                className="input"
                value={professorId}
                onChange={(ev) => setProfessorId(ev.target.value)}
                disabled={professors.length === 0}
              >
                {professors.map((item) => (
                  <option key={item.professor_id} value={item.professor_id}>
                    {item.professor_name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <p className="muted playground-toolbar__note">
          {mode === "student"
            ? "As mensagens são persistidas na conversa do aluno selecionado, segregada por turma e aula."
            : "O encerramento usa o fluxo real do professor — avança a turma e libera contexto para os alunos."}
        </p>
      </div>

      {track && progress && cohort && (
        <div className="playground-layout">
          <CohortPathPreview
            track={track}
            progress={progress}
            selectedLessonId={selectedLessonId}
            moduleProfessors={cohort.module_professors}
            onSelectLesson={(lessonId) => setSelectedLessonId(lessonId)}
          />

          <div className="playground-session">
            {!selectedLesson ? (
              <div className="card playground-session__empty">
                <p className="muted">Selecione uma aula na trilha para iniciar a sessão.</p>
              </div>
            ) : mode === "student" ? (
              studentId && selectedStudent ? (
                <PlaygroundChat
                  key={`${studentId}-${selectedLessonId}`}
                  cohortId={cohortId}
                  studentId={studentId}
                  studentName={selectedStudent.student_name}
                  lessonId={selectedLessonId!}
                  lessonTitle={selectedLesson.lesson.title}
                  canChat={canStudentChat}
                />
              ) : (
                <div className="card playground-session__empty">
                  <p className="muted">Matricule pelo menos um aluno nesta turma para testar o chat.</p>
                </div>
              )
            ) : (
              <section className="card playground-professor-panel">
                <header className="playground-professor-panel__head">
                  <span className="tag">Sessão de professor</span>
                  <h2 style={{ margin: "8px 0 0" }}>{selectedLesson.lesson.title}</h2>
                  <p className="muted" style={{ marginTop: 6, fontSize: 14 }}>
                    Agindo como{" "}
                    <strong>{selectedProfessor?.professor_name ?? "professor"}</strong>
                    {lessonProfessor && professorId !== lessonProfessor.professor_id && (
                      <> — esta aula pertence ao módulo de {lessonProfessor.professor_name}</>
                    )}
                  </p>
                </header>

                {selectedLessonId === progress.current_lesson_id ? (
                  <LessonReportCapture
                    key={`${professorId}-${selectedLessonId}`}
                    cohortId={cohortId}
                    lessonId={selectedLessonId!}
                    canComplete={canProfessorComplete}
                    professorName={selectedProfessor?.professor_name}
                    transcribePath={playgroundTranscribePath(cohortId, professorId)}
                    completePath={playgroundCompletePath(cohortId, professorId)}
                    onCompleted={() => refreshProgress(cohortId)}
                  />
                ) : completedSet.has(selectedLessonId!) ? (
                  <p className="muted" style={{ margin: 0 }}>
                    Aula já encerrada. Selecione a aula atual da turma para testar o encerramento.
                  </p>
                ) : (
                  <p className="muted" style={{ margin: 0 }}>
                    Esta aula ainda não foi liberada. Encerre as anteriores ou avance a turma pelo fluxo normal.
                  </p>
                )}
              </section>
            )}
          </div>
        </div>
      )}
    </>
  );
}
