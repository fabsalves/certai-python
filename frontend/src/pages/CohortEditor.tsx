import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { CohortEnrollments } from "../components/cohorts/CohortEnrollments";
import { CohortModuleProfessors } from "../components/cohorts/CohortModuleProfessors";
import { CohortPathPreview } from "../components/cohorts/CohortPathPreview";
import { CohortProgressPanel } from "../components/cohorts/CohortProgressPanel";
import { ProfessorCreateModal } from "../components/cohorts/ProfessorCreateModal";
import { EditorTabPanel, EditorTabs } from "../components/tracks/EditorTabs";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type {
  Cohort,
  CohortProgress,
  ModuleProfessor,
  ModuleProfessorAssignment,
  ProfessorOption,
  TrackOption,
} from "../lib/cohorts";
import { professorForModule, uniqueProfessorNames } from "../lib/cohorts";
import { activeLessonsCount, sortedLessons, sortedModules, type Module, type ModuleLevel, type Track } from "../lib/tracks";

type EditorTab = "meta" | "professors" | "students" | "progress";

function assignmentsFromCohort(cohort: Cohort): Record<string, string> {
  return Object.fromEntries(
    cohort.module_professors.map((mp) => [mp.module_id, mp.professor_id]),
  );
}

function assignmentsEqual(
  current: Record<string, string>,
  saved: Cohort["module_professors"],
): boolean {
  if (Object.keys(current).length !== saved.length) return false;
  return saved.every((mp) => current[mp.module_id] === mp.professor_id);
}

function buildModuleAssignments(
  modules: Module[],
  professors: ProfessorOption[],
  previous: Record<string, string> = {},
): Record<string, string> {
  const defaultProfessorId = professors[0]?.id ?? "";
  const next: Record<string, string> = {};
  for (const mod of modules) {
    if (!mod.is_active) continue;
    next[mod.id] = previous[mod.id] ?? defaultProfessorId;
  }
  return next;
}

function assignmentsPayload(assignments: Record<string, string>): ModuleProfessorAssignment[] {
  return Object.entries(assignments).map(([module_id, professor_id]) => ({
    module_id,
    professor_id,
  }));
}

function buildPreviewModuleProfessors(
  modules: Module[],
  assignments: Record<string, string>,
  professors: ProfessorOption[],
): ModuleProfessor[] {
  return modules
    .map((mod) => {
      const professorId = assignments[mod.id];
      const professor = professors.find((item) => item.id === professorId);
      if (!professor) return null;
      return {
        module_id: mod.id,
        module_title: mod.title,
        professor_id: professor.id,
        professor_name: professor.name,
      };
    })
    .filter((item): item is ModuleProfessor => item != null);
}

export function CohortEditor() {
  const { cohortId } = useParams<{ cohortId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const isNew = cohortId === "new";
  const canManage = user?.role === "admin" || user?.role === "designer";
  const isProfessor = user?.role === "professor";

  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [track, setTrack] = useState<Track | null>(null);
  const [progress, setProgress] = useState<CohortProgress | null>(null);
  const [tracks, setTracks] = useState<TrackOption[]>([]);
  const [professors, setProfessors] = useState<ProfessorOption[]>([]);
  const [loading, setLoading] = useState(!isNew);
  const [name, setName] = useState("");
  const [trackId, setTrackId] = useState("");
  const [moduleAssignments, setModuleAssignments] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [formError, setFormError] = useState("");
  const [tab, setTab] = useState<EditorTab>("meta");
  const [selectedLessonId, setSelectedLessonId] = useState<string | null>(null);
  const [profModalOpen, setProfModalOpen] = useState(false);

  const selectedTrack = useMemo(
    () => tracks.find((item) => item.id === trackId) ?? null,
    [tracks, trackId],
  );

  const formModules = useMemo((): Module[] => {
    if (track) return sortedModules(track).filter((mod) => mod.is_active);
    if (selectedTrack) {
      return [...selectedTrack.modules]
        .filter((mod) => mod.is_active)
        .sort((a, b) => a.position - b.position)
        .map((mod) => ({ ...mod, level: mod.level as ModuleLevel, lessons: mod.lessons as Module["lessons"] }));
    }
    return [];
  }, [track, selectedTrack]);

  const trackTitle = cohort?.track_title ?? selectedTrack?.title ?? "";
  const canOpenProfessorsTab = Boolean(!isNew || (name.trim() && trackId));

  const reloadProgress = useCallback(async (id: string) => {
    const { data } = await api.get<CohortProgress>(`/cohorts/${id}/progress`);
    setProgress(data);
    setSelectedLessonId((current) => current ?? data.current_lesson_id);
  }, []);

  const reloadCohort = useCallback(async () => {
    if (!cohortId || isNew) return;
    setLoadError("");
    try {
      const { data } = await api.get<Cohort>(`/cohorts/${cohortId}`);
      setCohort(data);
      setName(data.name);
      setTrackId(data.track_id);
      setModuleAssignments(assignmentsFromCohort(data));

      const [trackRes] = await Promise.all([
        api.get<Track>(`/cohorts/${data.id}/track`),
        reloadProgress(data.id),
      ]);
      setTrack(trackRes.data);
    } catch (err) {
      if (axios.isCancel(err)) return;
      setLoadError("Turma não encontrada.");
    }
  }, [cohortId, isNew, reloadProgress]);

  useEffect(() => {
    if (isNew) {
      if (!canManage) {
        navigate("/cohorts", { replace: true });
        return;
      }
      setLoading(true);
      Promise.all([
        api.get<TrackOption[]>("/tracks"),
        api.get<ProfessorOption[]>("/users", { params: { role: "professor" } }),
      ])
        .then(([tracksRes, professorsRes]) => {
          const activeTracks = tracksRes.data.filter((item) => item.is_active);
          const nextProfessors = professorsRes.data;
          const nextTrackId = activeTracks[0]?.id ?? "";
          setTracks(activeTracks);
          setProfessors(nextProfessors);
          setTrackId(nextTrackId);
          if (activeTracks[0]) {
            setModuleAssignments(
              buildModuleAssignments(
                activeTracks[0].modules as Module[],
                nextProfessors,
              ),
            );
          }
        })
        .finally(() => setLoading(false));
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setLoadError("");

    api
      .get<Cohort>(`/cohorts/${cohortId}`, { signal: controller.signal })
      .then(async ({ data }) => {
        setCohort(data);
        setName(data.name);
        setTrackId(data.track_id);
        setModuleAssignments(assignmentsFromCohort(data));
        const trackRes = await api.get<Track>(`/cohorts/${data.id}/track`, {
          signal: controller.signal,
        });
        setTrack(trackRes.data);
        const progressRes = await api.get<CohortProgress>(`/cohorts/${data.id}/progress`, {
          signal: controller.signal,
        });
        setProgress(progressRes.data);
        setSelectedLessonId(progressRes.data.current_lesson_id);
      })
      .catch((err) => {
        if (controller.signal.aborted || axios.isCancel(err)) return;
        setCohort(null);
        setLoadError("Turma não encontrada.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [cohortId, isNew, canManage, navigate]);

  useEffect(() => {
    if (!canManage) return;
    api
      .get<ProfessorOption[]>("/users", { params: { role: "professor" } })
      .then(({ data }) => setProfessors(data));
  }, [canManage, cohortId]);

  useEffect(() => {
    if (!isNew || !selectedTrack) return;
    setModuleAssignments((current) =>
      buildModuleAssignments(selectedTrack.modules as Module[], professors, current),
    );
  }, [isNew, selectedTrack, professors]);

  useEffect(() => {
    const nextTab = (location.state as { tab?: EditorTab } | null)?.tab;
    if (
      nextTab === "meta" ||
      nextTab === "professors" ||
      nextTab === "students" ||
      nextTab === "progress"
    ) {
      setTab(nextTab);
      return;
    }
    if (isProfessor) {
      setTab("progress");
      return;
    }
    setTab(isNew ? "meta" : "students");
  }, [cohortId, isNew, isProfessor, location.state]);

  const metaDirty = cohort ? name !== cohort.name : name.trim().length > 0 || trackId.length > 0;
  const professorsDirty = cohort
    ? !assignmentsEqual(moduleAssignments, cohort.module_professors)
    : Object.keys(moduleAssignments).length > 0;

  const activeLessonId = selectedLessonId ?? progress?.current_lesson_id ?? null;
  const activeModuleAssignment = useMemo(() => {
    if (!track || !activeLessonId) return undefined;
    for (const mod of sortedModules(track)) {
      if (sortedLessons(mod).some((lesson) => lesson.id === activeLessonId)) {
        return professorForModule(cohort, mod.id);
      }
    }
    return undefined;
  }, [track, activeLessonId, cohort]);

  const canCompleteLesson =
    isProfessor &&
    user != null &&
    activeModuleAssignment?.professor_id === user.id;

  const previewTrack = track ?? (selectedTrack as Track | null);
  const previewProgress = progress ?? { completed_lesson_ids: [], current_lesson_id: null };
  const previewModuleProfessors =
    cohort?.module_professors ??
    buildPreviewModuleProfessors(formModules, moduleAssignments, professors);

  async function continueToProfessors(e?: FormEvent) {
    e?.preventDefault();
    setFormError("");
    if (!name.trim() || !trackId) return;
    setTab("professors");
  }

  async function saveMeta(e?: FormEvent) {
    e?.preventDefault();
    setFormError("");

    if (isNew) {
      await continueToProfessors();
      return;
    }

    if (!cohort || !metaDirty) return;
    setSaving(true);
    try {
      const { data } = await api.patch<Cohort>(`/cohorts/${cohort.id}`, { name });
      setCohort(data);
    } catch {
      setFormError("Não foi possível salvar a turma.");
    } finally {
      setSaving(false);
    }
  }

  async function saveProfessors(e?: FormEvent) {
    e?.preventDefault();
    setFormError("");
    setSaving(true);
    try {
      const module_professors = assignmentsPayload(moduleAssignments);

      if (isNew) {
        const { data } = await api.post<Cohort>("/cohorts", {
          name,
          track_id: trackId,
          module_professors,
        });
        navigate(`/cohorts/${data.id}`, { replace: true, state: { tab: "students" } });
        return;
      }

      if (!cohort) return;
      const { data } = await api.patch<Cohort>(`/cohorts/${cohort.id}`, { module_professors });
      setCohort(data);
      setModuleAssignments(assignmentsFromCohort(data));
    } catch {
      setFormError("Não foi possível salvar os professores.");
    } finally {
      setSaving(false);
    }
  }

  function handleTabChange(id: string) {
    setFormError("");
    setTab(id as EditorTab);
  }

  function selectLesson(lessonId: string) {
    setTab("progress");
    setSelectedLessonId(lessonId);
    requestAnimationFrame(() => {
      document.getElementById("cohort-progress-panel")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  async function onProgressChanged() {
    if (!cohort) return;
    await reloadProgress(cohort.id);
    await reloadCohort();
  }

  if (loading) return <p className="muted">Carregando turma…</p>;
  if (loadError && !isNew && !cohort) return <p className="form-error">{loadError}</p>;

  const showSidebar = Boolean(
    previewTrack &&
      ((cohort && progress) || (isNew && tab === "professors")),
  );
  const completedCount = progress?.completed_lesson_ids.length ?? 0;

  return (
    <div className="track-editor cohort-editor">
      <div className="track-editor__toolbar">
        <Link to="/cohorts" className="track-editor__back">← Turmas</Link>
        <div className="track-editor__toolbar-actions">
          {cohort && (
            <>
              <span className="tag">{cohort.track_title}</span>
              {canManage && (
                <span className="muted" style={{ fontSize: 13 }}>
                  {uniqueProfessorNames(cohort)}
                </span>
              )}
            </>
          )}
        </div>
      </div>

      <div
        className={`track-editor__layout${
          showSidebar ? "" : " track-editor__layout--single"
        }`}
      >
        <div className="track-editor__main">
          <div className="card track-editor-panel">
            {canManage ? (
              <EditorTabs
                tabs={[
                  { id: "meta", label: isNew ? "Nova turma" : "Dados da turma" },
                  {
                    id: "professors",
                    label: "Professores",
                    disabled: !canOpenProfessorsTab,
                    count: formModules.length || undefined,
                  },
                  {
                    id: "students",
                    label: "Alunos",
                    disabled: !cohort,
                    count: cohort?.enrollment_count,
                  },
                  {
                    id: "progress",
                    label: "Andamento",
                    disabled: !cohort,
                    count: cohort ? completedCount : undefined,
                  },
                ]}
                active={tab}
                onChange={handleTabChange}
              >
                <EditorTabPanel id="meta" labelledBy="track-tab-meta" hidden={tab !== "meta"}>
                  <form className="track-meta" onSubmit={saveMeta}>
                    <p className="muted track-meta__hint">
                      {isNew
                        ? "Nome e trilha. Na próxima aba você define o professor de cada módulo."
                        : `${cohort?.enrollment_count ?? 0} aluno(s) · ${track ? activeLessonsCount(track) : 0} aula(s) na trilha`}
                    </p>

                    <div className="track-meta__fields">
                      <div className="field">
                        <label htmlFor="cohort-name">Nome da turma</label>
                        <input
                          id="cohort-name"
                          className="input"
                          value={name}
                          onChange={(e) => setName(e.target.value)}
                          required
                        />
                      </div>
                      <div className="field">
                        <label htmlFor="cohort-track">Trilha</label>
                        <select
                          id="cohort-track"
                          className="input"
                          value={trackId}
                          onChange={(e) => setTrackId(e.target.value)}
                          required
                          disabled={!isNew}
                        >
                          {(isNew ? tracks : [{ id: trackId, title: cohort?.track_title ?? "", is_active: true, modules: [] }]).map(
                            (item) => (
                              <option key={item.id} value={item.id}>{item.title}</option>
                            ),
                          )}
                        </select>
                        {!isNew && (
                          <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
                            A trilha não pode ser alterada após a criação.
                          </p>
                        )}
                      </div>
                    </div>

                    {formError && tab === "meta" && <div className="form-error">{formError}</div>}

                    {(isNew || metaDirty) && (
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={saving || !name.trim() || !trackId}
                      >
                        {saving
                          ? "Salvando…"
                          : isNew
                            ? "Continuar para professores"
                            : "Salvar dados"}
                      </button>
                    )}
                  </form>
                </EditorTabPanel>

                <EditorTabPanel id="professors" labelledBy="track-tab-professors" hidden={tab !== "professors"}>
                  <CohortModuleProfessors
                    modules={formModules}
                    professors={professors}
                    assignments={moduleAssignments}
                    trackTitle={trackTitle}
                    isNew={isNew}
                    saving={saving}
                    dirty={professorsDirty}
                    error={tab === "professors" ? formError : undefined}
                    onAssignmentChange={(moduleId, professorId) =>
                      setModuleAssignments((current) => ({
                        ...current,
                        [moduleId]: professorId,
                      }))
                    }
                    onCreateProfessor={() => setProfModalOpen(true)}
                    onSubmit={saveProfessors}
                  />
                </EditorTabPanel>

                <EditorTabPanel id="students" labelledBy="track-tab-students" hidden={tab !== "students" || !cohort}>
                  {cohort && (
                    <CohortEnrollments cohortId={cohort.id} onChanged={reloadCohort} />
                  )}
                </EditorTabPanel>

                <EditorTabPanel id="progress" labelledBy="track-tab-progress" hidden={tab !== "progress" || !cohort}>
                  {cohort && track && progress && (
                    <CohortProgressPanel
                      cohortId={cohort.id}
                      track={track}
                      progress={progress}
                      selectedLessonId={selectedLessonId}
                      canComplete={canCompleteLesson}
                      professorName={activeModuleAssignment?.professor_name}
                      onCompleted={onProgressChanged}
                    />
                  )}
                </EditorTabPanel>
              </EditorTabs>
            ) : (
              <div className="editor-tabs__panel cohort-editor__professor-panel">
                <div className="cohort-editor__professor-head">
                  <h2 style={{ margin: 0 }}>{cohort?.name}</h2>
                  <p className="muted" style={{ marginTop: 6 }}>
                    {cohort?.track_title} · confirme quando a turma terminar cada aula do seu módulo.
                  </p>
                </div>
                {cohort && track && progress && (
                  <CohortProgressPanel
                    cohortId={cohort.id}
                    track={track}
                    progress={progress}
                    selectedLessonId={selectedLessonId}
                    canComplete={canCompleteLesson}
                    professorName={activeModuleAssignment?.professor_name}
                    onCompleted={onProgressChanged}
                  />
                )}
              </div>
            )}
          </div>
        </div>

        {showSidebar && previewTrack && (
          <aside className="track-editor__preview">
            <CohortPathPreview
              track={previewTrack}
              progress={previewProgress}
              selectedLessonId={selectedLessonId}
              moduleProfessors={previewModuleProfessors}
              onSelectLesson={(lessonId) => {
                if (cohort) selectLesson(lessonId);
              }}
            />
          </aside>
        )}
      </div>

      {canManage && (
        <ProfessorCreateModal
          open={profModalOpen}
          onClose={() => setProfModalOpen(false)}
          onCreated={(prof) => {
            setProfessors((current) => [...current, prof].sort((a, b) => a.name.localeCompare(b.name)));
            setModuleAssignments((current) => {
              const next = { ...current };
              for (const mod of formModules) {
                if (!next[mod.id]) next[mod.id] = prof.id;
              }
              return next;
            });
          }}
        />
      )}
    </div>
  );
}
