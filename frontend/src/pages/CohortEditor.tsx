import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { CohortEditorSkeleton } from "../components/cohorts/CohortEditorSkeleton";
import { CohortEnrollments } from "../components/cohorts/CohortEnrollments";
import { CohortModuleProfessors } from "../components/cohorts/CohortModuleProfessors";
import { CohortPathPreview } from "../components/cohorts/CohortPathPreview";
import { CohortProgressPanel } from "../components/cohorts/CohortProgressPanel";
import { ProfessorCreateModal } from "../components/cohorts/ProfessorCreateModal";
import { EditorTabPanel, EditorTabs } from "../components/tracks/EditorTabs";
import { Select } from "../components/ui/Select";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useFeedback } from "../lib/feedback";
import { useApiAction } from "../lib/useApiAction";
import { isNonEmpty, trimmed } from "../lib/validation";
import type {
  Cohort,
  CohortProgress,
  Enrollment,
  ModuleAssignments,
  ModuleClassDraft,
  ModuleProfessor,
  ProfessorOption,
  TrackOption,
} from "../lib/cohorts";
import {
  assignmentsEqual,
  assignmentsFromCohort,
  assignmentsPayload,
  pathProgressForViewer,
  professorsForModule,
  suggestSplit,
  uniqueProfessorNames,
} from "../lib/cohorts";
import { activeLessonsCount, sortedLessons, sortedModules, type Module, type ModuleLevel, type Track } from "../lib/tracks";

type EditorTab = "meta" | "professors" | "students" | "progress";

function buildModuleAssignments(
  modules: Module[],
  professors: ProfessorOption[],
  previous: ModuleAssignments = {},
): ModuleAssignments {
  const defaultProfessorId = professors[0]?.id ?? "";
  const next: ModuleAssignments = {};
  for (const mod of modules) {
    if (!mod.is_active) continue;
    next[mod.id] = previous[mod.id] ?? [{ professorId: defaultProfessorId, studentIds: [] }];
  }
  return next;
}

function buildPreviewModuleProfessors(
  modules: Module[],
  assignments: ModuleAssignments,
  professors: ProfessorOption[],
): ModuleProfessor[] {
  return modules.flatMap((mod) =>
    (assignments[mod.id] ?? []).flatMap((item, index) => {
      const professor = professors.find((option) => option.id === item.professorId);
      if (!professor) return [];
      return [
        {
          id: `${mod.id}-${index}`,
          module_id: mod.id,
          module_title: mod.title,
          professor_id: professor.id,
          professor_name: professor.name,
          student_ids: item.studentIds,
        },
      ];
    }),
  );
}

export function CohortEditor() {
  const { cohortId } = useParams<{ cohortId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const runAction = useApiAction();
  const feedback = useFeedback();
  const isNew = cohortId === "new";
  const canManage = user?.role === "admin" || user?.role === "designer";
  const isProfessor = user?.role === "professor";

  const [cohort, setCohort] = useState<Cohort | null>(null);
  const [track, setTrack] = useState<Track | null>(null);
  const [progress, setProgress] = useState<CohortProgress | null>(null);
  const [tracks, setTracks] = useState<TrackOption[]>([]);
  const [professors, setProfessors] = useState<ProfessorOption[]>([]);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(!isNew);
  const [name, setName] = useState("");
  const [trackId, setTrackId] = useState("");
  const [moduleAssignments, setModuleAssignments] = useState<ModuleAssignments>({});
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState("");
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

  const reloadEnrollments = useCallback(async (id: string) => {
    const { data } = await api.get<Enrollment[]>(`/cohorts/${id}/enrollments`);
    setEnrollments(data);
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
        reloadEnrollments(data.id),
      ]);
      setTrack(trackRes.data);
    } catch (err) {
      if (axios.isCancel(err)) return;
      setLoadError("Turma não encontrada.");
    }
  }, [cohortId, isNew, reloadProgress, reloadEnrollments]);

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
        const [trackRes, progressRes, enrollmentsRes] = await Promise.all([
          api.get<Track>(`/cohorts/${data.id}/track`, { signal: controller.signal }),
          api.get<CohortProgress>(`/cohorts/${data.id}/progress`, {
            signal: controller.signal,
          }),
          api.get<Enrollment[]>(`/cohorts/${data.id}/enrollments`, {
            signal: controller.signal,
          }),
        ]);
        setCohort(data);
        setName(data.name);
        setTrackId(data.track_id);
        setModuleAssignments(assignmentsFromCohort(data));
        setTrack(trackRes.data);
        setProgress(progressRes.data);
        setSelectedLessonId(progressRes.data.current_lesson_id);
        setEnrollments(enrollmentsRes.data);
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
  const activeModuleClasses = useMemo(() => {
    if (!track || !activeLessonId) return [];
    for (const mod of sortedModules(track)) {
      if (sortedLessons(mod).some((lesson) => lesson.id === activeLessonId)) {
        return professorsForModule(cohort, mod.id);
      }
    }
    return [];
  }, [track, activeLessonId, cohort]);

  const ownClass = useMemo(
    () =>
      user != null
        ? activeModuleClasses.find((item) => item.professor_id === user.id)
        : undefined,
    [activeModuleClasses, user],
  );

  const canCompleteLesson = isProfessor && ownClass != null;

  const enrolledIds = useMemo(
    () => enrollments.map((item) => item.student_id),
    [enrollments],
  );

  const previousModuleId = useCallback(
    (moduleId: string) => {
      const index = formModules.findIndex((mod) => mod.id === moduleId);
      return index > 0 ? formModules[index - 1].id : null;
    },
    [formModules],
  );

  function updateModuleClasses(
    moduleId: string,
    update: (classes: ModuleClassDraft[], current: ModuleAssignments) => ModuleClassDraft[],
  ) {
    setModuleAssignments((current) => ({
      ...current,
      [moduleId]: update(current[moduleId] ?? [], current),
    }));
  }

  function changeProfessor(moduleId: string, index: number, professorId: string) {
    updateModuleClasses(moduleId, (classes) =>
      classes.map((item, position) =>
        position === index ? { ...item, professorId } : item,
      ),
    );
  }

  function addProfessor(moduleId: string) {
    updateModuleClasses(moduleId, (classes, current) => {
      const used = new Set(classes.map((item) => item.professorId));
      const nextProfessor = professors.find((prof) => !used.has(prof.id));
      if (!nextProfessor) return classes;

      const previousId = previousModuleId(moduleId);
      const previousClasses = previousId ? (current[previousId] ?? []) : [];
      return suggestSplit(
        [...classes, { professorId: nextProfessor.id, studentIds: [] }],
        enrolledIds,
        previousClasses,
      );
    });
  }

  function removeProfessor(moduleId: string, index: number) {
    updateModuleClasses(moduleId, (classes) => {
      const remaining = classes.filter((_item, position) => position !== index);
      if (remaining.length <= 1) {
        return remaining.map((item) => ({ ...item, studentIds: [] }));
      }
      const orphans = classes[index]?.studentIds ?? [];
      return remaining.map((item, position) =>
        position === 0 ? { ...item, studentIds: [...item.studentIds, ...orphans] } : item,
      );
    });
  }

  async function applyDivision(
    moduleId: string,
    classes: ModuleClassDraft[],
  ): Promise<boolean> {
    const nextAssignments: ModuleAssignments = {
      ...moduleAssignments,
      [moduleId]: classes.map((item) => ({
        ...item,
        studentIds: [...item.studentIds],
      })),
    };
    setModuleAssignments(nextAssignments);

    // New cohort: draft only — persisted when the turma is created.
    if (isNew || !cohort) return true;

    setSaving(true);
    const result = await runAction({
      run: () =>
        api.patch<Cohort>(`/cohorts/${cohort.id}`, {
          module_professors: assignmentsPayload(nextAssignments),
        }),
      successMessage: "Divisão salva.",
      errorMessage: "Não foi possível salvar a divisão.",
      onSuccess: ({ data }) => {
        setCohort(data);
        setModuleAssignments(assignmentsFromCohort(data));
      },
    });
    setSaving(false);
    return result != null;
  }

  const previewTrack = track ?? (selectedTrack as Track | null);
  const previewProgress = progress ?? {
    completed_lesson_ids: [],
    partial_lesson_ids: [],
    current_lesson_id: null,
    lesson_classes: [],
  };
  const previewModuleProfessors =
    cohort?.module_professors ??
    buildPreviewModuleProfessors(formModules, moduleAssignments, professors);

  async function continueToProfessors(e?: FormEvent) {
    e?.preventDefault();
    if (!isNonEmpty(name)) {
      feedback.error("Informe o nome da turma.");
      return;
    }
    if (!trackId) return;
    setTab("professors");
  }

  async function saveMeta(e?: FormEvent) {
    e?.preventDefault();

    if (isNew) {
      await continueToProfessors();
      return;
    }

    const nextName = trimmed(name);
    if (!nextName) {
      feedback.error("Informe o nome da turma.");
      return;
    }

    if (!cohort || !metaDirty) return;
    setSaving(true);
    await runAction({
      run: () => api.patch<Cohort>(`/cohorts/${cohort.id}`, { name: nextName }),
      successMessage: "Dados da turma salvos.",
      errorMessage: "Não foi possível salvar a turma.",
      onSuccess: ({ data }) => setCohort(data),
    });
    setSaving(false);
  }

  async function saveProfessors(e?: FormEvent) {
    e?.preventDefault();
    const nextName = trimmed(name);
    if (!nextName) {
      feedback.error("Informe o nome da turma.");
      return;
    }
    setSaving(true);
    const module_professors = assignmentsPayload(moduleAssignments);

    if (isNew) {
      await runAction({
        run: () =>
          api.post<Cohort>("/cohorts", { name: nextName, track_id: trackId, module_professors }),
        successMessage: "Turma criada.",
        errorMessage: "Não foi possível criar a turma.",
        onSuccess: ({ data }) => {
          navigate(`/cohorts/${data.id}`, { replace: true, state: { tab: "students" } });
        },
      });
      setSaving(false);
      return;
    }

    if (!cohort) {
      setSaving(false);
      return;
    }
    await runAction({
      run: () => api.patch<Cohort>(`/cohorts/${cohort.id}`, { module_professors }),
      successMessage: "Professores salvos.",
      errorMessage: "Não foi possível salvar os professores.",
      onSuccess: ({ data }) => {
        setCohort(data);
        setModuleAssignments(assignmentsFromCohort(data));
      },
    });
    setSaving(false);
  }

  function handleTabChange(id: string) {
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

  if (loading) {
    return <CohortEditorSkeleton tabCount={isProfessor ? 2 : 4} />;
  }
  if (loadError && !isNew && !cohort) return <p className="form-error">{loadError}</p>;

  const showSidebar = Boolean(
    previewTrack &&
      ((cohort && progress) || (isNew && tab === "professors")),
  );
  const completedCount = progress
    ? pathProgressForViewer(progress, isProfessor ? user?.id : undefined).doneCount
    : 0;

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
                    count: cohort ? enrollments.length : undefined,
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
                      <Select
                        id="cohort-track"
                        label="Trilha"
                        value={trackId}
                        options={(isNew
                          ? tracks
                          : [{ id: trackId, title: cohort?.track_title ?? "" }]
                        ).map((item) => ({ value: item.id, label: item.title }))}
                        onChange={setTrackId}
                        required
                        disabled={!isNew}
                      />
                      {!isNew && (
                        <p className="muted" style={{ marginTop: 6, fontSize: 13 }}>
                          A trilha não pode ser alterada após a criação.
                        </p>
                      )}
                    </div>

                    {(isNew || metaDirty) && (
                      <button
                        type="submit"
                        className="btn btn-primary"
                        disabled={saving || !isNonEmpty(name) || !trackId}
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
                    enrollments={enrollments}
                    trackTitle={trackTitle}
                    isNew={isNew}
                    saving={saving}
                    dirty={professorsDirty}
                    onProfessorChange={changeProfessor}
                    onAddProfessor={addProfessor}
                    onRemoveProfessor={removeProfessor}
                    onApplyDivision={applyDivision}
                    onCreateProfessor={() => setProfModalOpen(true)}
                    onSubmit={saveProfessors}
                  />
                </EditorTabPanel>

                <EditorTabPanel id="students" labelledBy="track-tab-students" hidden={tab !== "students" || !cohort}>
                  {cohort && track && (
                    <CohortEnrollments
                      cohortId={cohort.id}
                      track={track}
                      onChanged={reloadCohort}
                    />
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
                      professorName={ownClass?.professor_name}
                      viewerProfessorId={isProfessor ? user?.id : undefined}
                      onCompleted={onProgressChanged}
                    />
                  )}
                </EditorTabPanel>
              </EditorTabs>
            ) : (
              <EditorTabs
                tabs={[
                  {
                    id: "students",
                    label: "Alunos",
                    disabled: !cohort,
                    count: cohort ? enrollments.length : undefined,
                  },
                  {
                    id: "progress",
                    label: "Andamento",
                    disabled: !cohort,
                    count: cohort ? completedCount : undefined,
                  },
                ]}
                active={tab === "students" || tab === "progress" ? tab : "progress"}
                onChange={handleTabChange}
              >
                <EditorTabPanel
                  id="students"
                  labelledBy="track-tab-students"
                  hidden={tab !== "students" || !cohort}
                >
                  {cohort && track && (
                    <CohortEnrollments
                      cohortId={cohort.id}
                      track={track}
                      onChanged={reloadCohort}
                    />
                  )}
                </EditorTabPanel>

                <EditorTabPanel
                  id="progress"
                  labelledBy="track-tab-progress"
                  hidden={tab !== "progress" || !cohort}
                >
                  {cohort && track && progress && (
                    <CohortProgressPanel
                      cohortId={cohort.id}
                      track={track}
                      progress={progress}
                      selectedLessonId={selectedLessonId}
                      canComplete={canCompleteLesson}
                      professorName={ownClass?.professor_name}
                      viewerProfessorId={isProfessor ? user?.id : undefined}
                      onCompleted={onProgressChanged}
                    />
                  )}
                </EditorTabPanel>
              </EditorTabs>
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
              viewerProfessorId={isProfessor ? user?.id : undefined}
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
                if (!next[mod.id]?.length) {
                  next[mod.id] = [{ professorId: prof.id, studentIds: [] }];
                }
              }
              return next;
            });
          }}
        />
      )}
    </div>
  );
}
