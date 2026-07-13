import { useCallback, useEffect, useMemo, useState } from "react";
import { CohortPathPreview } from "../components/cohorts/CohortPathPreview";
import { LessonReportCapture } from "../components/cohorts/LessonReportCapture";
import { PlaygroundChat } from "../components/playground/PlaygroundChat";
import { PlaygroundContextPanel } from "../components/playground/PlaygroundContextPanel";
import { PlaygroundScoresPanel } from "../components/playground/PlaygroundScoresPanel";
import { PlaygroundSessionHead } from "../components/playground/PlaygroundSessionHead";
import { Select } from "../components/ui/Select";
import { api } from "../lib/api";
import type { Cohort, CohortProgress, Enrollment } from "../lib/cohorts";
import { professorForModule } from "../lib/cohorts";
import {
  playgroundCompletePath,
  playgroundTranscribePath,
} from "../lib/playground";
import {
  readPlaygroundSession,
  writePlaygroundSession,
  type PlaygroundRailTab,
} from "../lib/playgroundSession";
import { sortedLessons, sortedModules, type Track } from "../lib/tracks";

type SessionMode = "student" | "professor";
type RailTab = PlaygroundRailTab;

function initialRailTab(): RailTab {
  const tab = readPlaygroundSession()?.railTab;
  if (tab === "track" || tab === "context" || tab === "scores") return tab;
  return "track";
}

function findLessonModule(track: Track, lessonId: string) {
  for (const mod of sortedModules(track)) {
    const lesson = sortedLessons(mod).find((l) => l.id === lessonId);
    if (lesson) return { module: mod, lesson };
  }
  return null;
}

function SettingsIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <circle cx="10" cy="4" r="1.5" />
      <circle cx="10" cy="10" r="1.5" />
      <circle cx="10" cy="16" r="1.5" />
    </svg>
  );
}

export function Playground() {
  const [cohorts, setCohorts] = useState<Cohort[]>([]);
  const [cohortId, setCohortId] = useState(() => readPlaygroundSession()?.cohortId ?? "");
  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [track, setTrack] = useState<Track | null>(null);
  const [progress, setProgress] = useState<CohortProgress | null>(null);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [mode, setMode] = useState<SessionMode>(() =>
    readPlaygroundSession()?.mode === "professor" ? "professor" : "student",
  );
  const [studentId, setStudentId] = useState(() => readPlaygroundSession()?.studentId ?? "");
  const [professorId, setProfessorId] = useState(() => readPlaygroundSession()?.professorId ?? "");
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(
    () => readPlaygroundSession()?.selectedLessonId ?? null,
  );
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [railTab, setRailTab] = useState<RailTab>(initialRailTab);
  const [contextRefreshKey, setContextRefreshKey] = useState(0);

  const refreshProgress = useCallback(async (id: string) => {
    const { data } = await api.get<CohortProgress>(`/cohorts/${id}/progress`);
    setProgress(data);
    setContextRefreshKey((k) => k + 1);
    return data;
  }, []);

  useEffect(() => {
    api
      .get<Cohort[]>("/cohorts")
      .then((res) => {
        setCohorts(res.data);
        setCohortId((prev) => {
          if (prev && res.data.some((item) => item.id === prev)) return prev;
          return res.data[0]?.id ?? "";
        });
      })
      .catch(() => setLoadError("Não foi possível carregar as turmas."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!cohortId) return;

    writePlaygroundSession({
      cohortId,
      mode,
      studentId,
      professorId,
      selectedLessonId,
      railTab,
    });
  }, [cohortId, mode, studentId, professorId, selectedLessonId, railTab]);

  useEffect(() => {
    if (railTab === "scores" && (mode !== "student" || !studentId)) {
      setRailTab("track");
    }
  }, [mode, studentId, railTab]);

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
        setSelectedLessonId((prev) => {
          if (prev && findLessonModule(trackRes.data, prev)) return prev;
          return (
            progressRes.data.current_lesson_id ??
            progressRes.data.completed_lesson_ids.at(-1) ??
            null
          );
        });
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

  useEffect(() => {
    if (!settingsOpen) return;
    function onKeyDown(ev: KeyboardEvent) {
      if (ev.key === "Escape") setSettingsOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [settingsOpen]);

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

  const cohortOptions = useMemo(
    () =>
      cohorts.map((item) => ({
        value: item.id,
        label: `${item.name} — ${item.track_title}`,
      })),
    [cohorts],
  );

  const studentOptions = useMemo(
    () =>
      [...enrollments]
        .sort((a, b) => a.student_name.localeCompare(b.student_name, "pt-BR"))
        .map((item) => ({
          value: item.student_id,
          label: `${item.student_name} (${item.student_email})`,
        })),
    [enrollments],
  );

  const professorOptions = useMemo(
    () =>
      professors.map((item) => ({
        value: item.professor_id,
        label: item.professor_name,
      })),
    [professors],
  );

  const sessionMenu = (
    <button
      type="button"
      className="playground-stage__menu"
      onClick={() => setSettingsOpen(true)}
      aria-label="Configurações da sessão"
    >
      <SettingsIcon />
    </button>
  );

  if (loading) {
    return (
      <div className="playground-shell playground-shell--centered">
        <p className="muted">Carregando playground…</p>
      </div>
    );
  }

  if (cohorts.length === 0) {
    return (
      <div className="playground-shell playground-shell--centered">
        <div className="empty-state">
          <p>Nenhuma turma disponível.</p>
          <p className="muted" style={{ marginTop: 8, fontSize: 14 }}>
            Crie uma turma com alunos matriculados para começar.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="playground-shell">
      <div className="playground-stage">
        {!selectedLesson && (
          <div className="playground-stage__bar">
            {loadError && <p className="form-error playground-stage__error">{loadError}</p>}
            {sessionMenu}
          </div>
        )}

        <div className="playground-stage__body">
          {loadError && selectedLesson && (
            <p className="form-error playground-stage__inline-error">{loadError}</p>
          )}
          {!track || !progress || !cohort ? null : !selectedLesson ? (
            <div className="playground-stage__empty">
              <p className="muted">Selecione uma aula na trilha para iniciar.</p>
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
                headerActions={sessionMenu}
                onMessageSent={() => setContextRefreshKey((k) => k + 1)}
              />
            ) : (
              <div className="playground-stage__empty">
                <p className="muted">Matricule pelo menos um aluno nesta turma para testar o chat.</p>
              </div>
            )
          ) : (
            <section className="playground-professor">
              <PlaygroundSessionHead
                title={selectedLesson.lesson.title}
                participantName={selectedProfessor?.professor_name ?? "Professor"}
                roleLabel="Professor"
                actions={sessionMenu}
              />
              <div className="playground-professor__scroll">
                <div className="playground-professor__inner">
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
                </div>
              </div>
            </section>
          )}
        </div>
      </div>

      {track && progress && cohort && (
        <aside className="playground-rail">
          <div className="playground-rail__tabs" role="tablist" aria-label="Painel lateral">
            <button
              type="button"
              role="tab"
              aria-selected={railTab === "track"}
              className={`playground-rail__tab${railTab === "track" ? " is-active" : ""}`}
              onClick={() => setRailTab("track")}
            >
              Trilha
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={railTab === "context"}
              className={`playground-rail__tab${railTab === "context" ? " is-active" : ""}`}
              onClick={() => setRailTab("context")}
            >
              Contexto IA
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={railTab === "scores"}
              className={`playground-rail__tab${railTab === "scores" ? " is-active" : ""}`}
              onClick={() => setRailTab("scores")}
              disabled={mode !== "student" || !studentId}
              title={
                mode !== "student" || !studentId
                  ? "Disponível no modo aluno com aluno selecionado"
                  : undefined
              }
            >
              Scores
            </button>
          </div>
          {railTab === "track" ? (
            <CohortPathPreview
              embedded
              compact
              track={track}
              progress={progress}
              selectedLessonId={selectedLessonId}
              moduleProfessors={cohort.module_professors}
              onSelectLesson={(lessonId) => setSelectedLessonId(lessonId)}
            />
          ) : railTab === "context" ? (
            <PlaygroundContextPanel
              cohortId={cohortId}
              lessonId={selectedLessonId}
              refreshKey={contextRefreshKey}
            />
          ) : (
            <PlaygroundScoresPanel
              cohortId={cohortId}
              studentId={studentId}
              lessonId={selectedLessonId}
              refreshKey={contextRefreshKey}
            />
          )}
        </aside>
      )}

      {settingsOpen && (
        <div className="playground-drawer">
          <button
            type="button"
            className="playground-drawer__scrim"
            onClick={() => setSettingsOpen(false)}
            aria-label="Fechar configurações"
          />
          <aside className="playground-drawer__panel" aria-label="Configurações da sessão">
            <header className="playground-drawer__head">
              <h2 className="playground-drawer__title">Sessão</h2>
              <button
                type="button"
                className="playground-drawer__close"
                onClick={() => setSettingsOpen(false)}
                aria-label="Fechar"
              >
                ×
              </button>
            </header>

            <div className="playground-drawer__body">
              <Select
                id="playground-cohort"
                label="Turma"
                variant="drawer"
                value={cohortId}
                options={cohortOptions}
                onChange={setCohortId}
              />

              <div className="drawer-field">
                <span className="drawer-field__label">Papel</span>
                <div className="drawer-segment" role="radiogroup" aria-label="Papel da sessão">
                  <button
                    type="button"
                    role="radio"
                    aria-checked={mode === "student"}
                    className={`drawer-segment__btn${mode === "student" ? " is-active" : ""}`}
                    onClick={() => setMode("student")}
                  >
                    Aluno
                  </button>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={mode === "professor"}
                    className={`drawer-segment__btn${mode === "professor" ? " is-active" : ""}`}
                    onClick={() => setMode("professor")}
                  >
                    Professor
                  </button>
                </div>
              </div>

              {mode === "student" ? (
                <Select
                  id="playground-student"
                  label="Agir como"
                  variant="drawer"
                  value={studentId}
                  options={studentOptions}
                  disabled={enrollments.length === 0}
                  placeholder="Sem alunos matriculados"
                  onChange={setStudentId}
                />
              ) : (
                <Select
                  id="playground-professor"
                  label="Agir como"
                  variant="drawer"
                  value={professorId}
                  options={professorOptions}
                  disabled={professors.length === 0}
                  onChange={setProfessorId}
                />
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
