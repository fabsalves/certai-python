import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../lib/api";
import {
  ASSESSMENT_OVERVIEW_HINT,
  ASSESSMENT_STATE_HINTS,
  assessmentLevelLabel,
  countTrackLevels,
  matchesLevelFilter,
  trackLevelFromBatch,
  trackLevelNeedsAttention,
  trackLevelSortRank,
  type CohortTrackLevels,
  type LevelFilter,
  type TrackLevelCounts,
  type TrackLevelSummary,
} from "../../lib/assessments";
import {
  buildStudentSections,
  defaultOpenSectionKeys,
  pendingDivisions,
  type Cohort,
  type Enrollment,
  type ModuleAssignments,
  type ModuleClassDraft,
  type ProfessorOption,
  type StudentClassSection,
} from "../../lib/cohorts";
import { sortedModules, type Track } from "../../lib/tracks";
import { useAuth } from "../../lib/auth";
import { useConfirm } from "../../lib/confirm";
import { useApiAction } from "../../lib/useApiAction";
import { Tooltip } from "../ui/Tooltip";
import {
  AssessmentLevelBadge,
  AssessmentLevelBadgeSkeleton,
} from "./AssessmentLevelBadge";
import { CohortStudentsSkeleton } from "./CohortStudentsSkeleton";
import { StudentAssessmentsPanel } from "./StudentAssessmentsPanel";
import { ModuleClassDivisionModal } from "./ModuleClassDivisionModal";
import { StudentEnrollModal } from "./StudentEnrollModal";

interface Props {
  cohortId: string;
  cohort: Cohort;
  track: Track;
  viewerProfessorId?: string;
  /** Select this student when landing from Andamento (dossier bridge). */
  focusStudentId?: string | null;
  onFocusStudentHandled?: () => void;
  onChanged: () => void;
  /** Current division per module, and the professors it can draw from. Present
   *  only for whoever may edit it, which is who sees the pending warning. */
  assignments?: ModuleAssignments;
  professors?: ProfessorOption[];
  onApplyDivision?: (
    moduleId: string,
    classes: ModuleClassDraft[],
  ) => Promise<boolean>;
}

type SortMode = "name" | "level";

const LEVEL_FILTERS: {
  value: LevelFilter;
  label: string;
  hint?: string;
}[] = [
  { value: "all", label: "Todos" },
  { value: "high", label: "Alto" },
  { value: "medium", label: "Médio" },
  { value: "low", label: "Baixo" },
  { value: "very_low", label: "Muito baixo" },
  {
    value: "no_evidence",
    label: "Sem evidência",
    hint: ASSESSMENT_STATE_HINTS.no_evidence,
  },
  {
    value: "no_assessment",
    label: "Sem avaliação",
    hint: ASSESSMENT_STATE_HINTS.no_assessment,
  },
];

function isNarrowViewport(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(max-width: 900px)").matches;
}

function sectionTitle(section: StudentClassSection): string {
  if (section.isUnassigned) return "Sem grupo";
  if (section.isOwnClass) return "Sua turma";
  return section.professorName ?? "Professor";
}

const MIX_ITEMS: {
  key: keyof TrackLevelCounts;
  short: string;
  label: string;
  tone: string;
  hint?: string;
}[] = [
  { key: "high", short: "A", label: assessmentLevelLabel("high"), tone: "high" },
  { key: "medium", short: "M", label: assessmentLevelLabel("medium"), tone: "medium" },
  { key: "low", short: "B", label: assessmentLevelLabel("low"), tone: "low" },
  {
    key: "very_low",
    short: "MB",
    label: assessmentLevelLabel("very_low"),
    tone: "very-low",
  },
  {
    key: "no_evidence",
    short: "SE",
    label: "Sem evidência",
    tone: "neutral",
    hint: ASSESSMENT_STATE_HINTS.no_evidence,
  },
  {
    key: "no_assessment",
    short: "SA",
    label: "Sem avaliação",
    tone: "neutral",
    hint: ASSESSMENT_STATE_HINTS.no_assessment,
  },
];

function SectionLevelMix({
  studentIds,
  trackLevels,
  loading,
}: {
  studentIds: string[];
  trackLevels: Record<string, TrackLevelSummary>;
  loading: boolean;
}) {
  const counts = useMemo(
    () => countTrackLevels(studentIds, trackLevels),
    [studentIds, trackLevels],
  );
  const items = MIX_ITEMS.filter((item) => counts[item.key] > 0);

  if (loading && items.length === 0) {
    return (
      <span className="cohort-students__level-mix" aria-hidden>
        <span className="cohort-students__level-mix-pill cohort-students__level-mix-pill--skeleton" />
        <span className="cohort-students__level-mix-pill cohort-students__level-mix-pill--skeleton" />
      </span>
    );
  }

  if (items.length === 0) return null;

  return (
    <span className="cohort-students__level-mix" aria-label="Distribuição de níveis">
      {items.map((item) => {
        const pill = (
          <span
            className={`cohort-students__level-mix-pill cohort-students__level-mix-pill--${item.tone}`}
          >
            <span className="cohort-students__level-mix-count">{counts[item.key]}</span>
            <span className="cohort-students__level-mix-short">{item.short}</span>
          </span>
        );
        return (
          <Tooltip
            key={item.key}
            content={item.hint ? `${item.label}: ${item.hint}` : item.label}
          >
            {pill}
          </Tooltip>
        );
      })}
    </span>
  );
}

export function CohortEnrollments({
  cohortId,
  cohort,
  track,
  viewerProfessorId,
  focusStudentId = null,
  onFocusStudentHandled,
  onChanged,
  assignments,
  professors,
  onApplyDivision,
}: Props) {
  const { user } = useAuth();
  const confirm = useConfirm();
  const runAction = useApiAction();
  const canManageEnrollments =
    user?.role === "org_admin";
  const detailRef = useRef<HTMLDivElement>(null);

  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sortMode, setSortMode] = useState<SortMode>("name");
  const [levelFilter, setLevelFilter] = useState<LevelFilter>("all");
  const [selectedStudentId, setSelectedStudentId] = useState<string | null>(null);
  const [staleSelectionNotice, setStaleSelectionNotice] = useState<string | null>(null);
  const [trackLevels, setTrackLevels] = useState<Record<string, TrackLevelSummary>>({});
  const [levelsLoading, setLevelsLoading] = useState(false);
  const [openKeys, setOpenKeys] = useState<Set<string>>(new Set());
  const [sectionsFingerprint, setSectionsFingerprint] = useState("");

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
      setLevelsLoading(false);
      return;
    }
    let cancelled = false;
    setLevelsLoading(true);
    api
      .get<CohortTrackLevels>(`/cohorts/${cohortId}/students/track-levels`)
      .then(({ data }) => {
        if (cancelled) return;
        const next: Record<string, TrackLevelSummary> = {};
        for (const row of data.students) {
          next[row.student_id] = trackLevelFromBatch(row);
        }
        setTrackLevels(next);
      })
      .catch(() => {
        if (cancelled) return;
        const next: Record<string, TrackLevelSummary> = {};
        for (const enrollment of enrollments) {
          next[enrollment.student_id] = { kind: "missing" };
        }
        setTrackLevels(next);
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

  const enrollmentById = useMemo(
    () => new Map(enrollments.map((item) => [item.student_id, item])),
    [enrollments],
  );

  const moduleOrder = useMemo(
    () =>
      sortedModules(track)
        .filter((mod) => mod.is_active)
        .map((mod) => ({ id: mod.id, title: mod.title, position: mod.position })),
    [track],
  );

  // Only for whoever can fix it. A professor sees the roster, not the warning.
  const pending = useMemo(
    () =>
      canManageEnrollments && assignments
        ? pendingDivisions(assignments, enrollments, moduleOrder)
        : [],
    [canManageEnrollments, assignments, enrollments, moduleOrder],
  );
  const [divisionModuleId, setDivisionModuleId] = useState<string | null>(null);
  const divisionModule = pending.find((item) => item.moduleId === divisionModuleId);

  const sections = useMemo(
    () =>
      buildStudentSections({
        moduleProfessors: cohort.module_professors,
        enrollments,
        moduleOrder,
        viewerProfessorId: viewerProfessorId ?? null,
        includeUnassigned: canManageEnrollments,
      }),
    [
      cohort.module_professors,
      enrollments,
      moduleOrder,
      viewerProfessorId,
      canManageEnrollments,
    ],
  );

  useEffect(() => {
    const fingerprint = sections.map((item) => item.key).join("|");
    if (fingerprint === sectionsFingerprint) return;
    setSectionsFingerprint(fingerprint);
    setOpenKeys(new Set(defaultOpenSectionKeys(sections)));
  }, [sections, sectionsFingerprint]);

  const filteredByStudent = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matched = new Set<string>();
    for (const e of enrollments) {
      if (
        q &&
        !e.student_name.toLowerCase().includes(q) &&
        !e.student_email.toLowerCase().includes(q)
      ) {
        continue;
      }
      if (!matchesLevelFilter(trackLevels[e.student_id], levelFilter)) continue;
      matched.add(e.student_id);
    }
    return matched;
  }, [enrollments, query, levelFilter, trackLevels]);

  const visibleSections = useMemo(() => {
    return sections
      .map((section) => {
        let studentIds = section.studentIds.filter((id) => filteredByStudent.has(id));
        studentIds = [...studentIds].sort((a, b) => {
          const ea = enrollmentById.get(a);
          const eb = enrollmentById.get(b);
          if (!ea || !eb) return 0;
          if (sortMode === "level") {
            const rankDiff =
              trackLevelSortRank(trackLevels[a]) - trackLevelSortRank(trackLevels[b]);
            if (rankDiff !== 0) return rankDiff;
          }
          return ea.student_name.localeCompare(eb.student_name, "pt-BR");
        });
        return { ...section, studentIds };
      })
      .filter((section) => section.studentIds.length > 0);
  }, [sections, filteredByStudent, enrollmentById, sortMode, trackLevels]);

  const visibleStudentCount = useMemo(() => {
    const ids = new Set<string>();
    for (const section of visibleSections) {
      for (const id of section.studentIds) ids.add(id);
    }
    return ids.size;
  }, [visibleSections]);

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

  useEffect(() => {
    if (!focusStudentId) return;
    if (loading) return;

    const enrolled = enrollments.some((e) => e.student_id === focusStudentId);
    if (!enrolled) {
      onFocusStudentHandled?.();
      return;
    }

    setQuery("");
    setLevelFilter("all");
    setStaleSelectionNotice(null);
    setSelectedStudentId(focusStudentId);

    const preferred =
      sections.find(
        (section) =>
          section.isOwnClass && section.studentIds.includes(focusStudentId),
      ) ??
      sections.find((section) => section.studentIds.includes(focusStudentId));
    if (preferred) {
      setOpenKeys((current) => {
        const next = new Set(current);
        next.add(preferred.key);
        return next;
      });
    }

    requestAnimationFrame(() => {
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    onFocusStudentHandled?.();
  }, [
    focusStudentId,
    loading,
    enrollments,
    sections,
    onFocusStudentHandled,
  ]);

  function selectStudent(studentId: string) {
    setStaleSelectionNotice(null);
    setSelectedStudentId(studentId);
    if (isNarrowViewport()) {
      requestAnimationFrame(() => {
        detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  function toggleSection(key: string) {
    setOpenKeys((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  const handleAssessmentsNotEnrolled = useCallback(() => {
    setSelectedStudentId(null);
    setStaleSelectionNotice(
      "Este aluno não está mais nesta turma. Recarregue a página para atualizar a lista.",
    );
  }, []);

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

  const filterActive = query.trim().length > 0 || levelFilter !== "all";

  if (loading) return <CohortStudentsSkeleton />;

  return (
    <section className="cohort-students">
      <div className="cohort-students__toolbar">
        <div className="muted cohort-students__hint">
          <p className="cohort-students__hint-text">
            Pessoas na jornada. Veja quem está na sua turma e abra alguém para ler a
            compreensão na trilha.
          </p>
          <Tooltip content={ASSESSMENT_OVERVIEW_HINT}>
            <button
              type="button"
              className="ui-help-icon"
              aria-label="O que é a avaliação"
            >
              ?
            </button>
          </Tooltip>
        </div>
        {canManageEnrollments && (
          <button type="button" className="btn btn-primary" onClick={() => setModalOpen(true)}>
            Adicionar alunos
          </button>
        )}
      </div>

      {pending.length > 0 && (
        <div className="pending-division">
          {pending.map((item) => (
            <div key={item.moduleId} className="pending-division__row">
              <p className="pending-division__text">
                <strong>
                  {item.studentIds.length} aluno
                  {item.studentIds.length > 1 ? "s" : ""}
                </strong>{" "}
                ainda sem professor em <strong>{item.moduleTitle}</strong>. Esse
                módulo tem mais de um professor, então é preciso dizer quem estuda
                com quem. Sem isso o professor não consegue encerrar aula.
              </p>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setDivisionModuleId(item.moduleId)}
              >
                Dividir alunos
              </button>
            </div>
          ))}
        </div>
      )}

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
            {LEVEL_FILTERS.map((item) => {
              const chip = (
                <button
                  type="button"
                  className={`cohort-students__chip${levelFilter === item.value ? " is-active" : ""}`}
                  onClick={() => setLevelFilter(item.value)}
                >
                  {item.label}
                </button>
              );
              return item.hint ? (
                <Tooltip key={item.value} content={item.hint}>
                  {chip}
                </Tooltip>
              ) : (
                <Fragment key={item.value}>{chip}</Fragment>
              );
            })}
          </div>

          <p className="muted cohort-students__count">
            {visibleStudentCount} aluno{visibleStudentCount === 1 ? "" : "s"}
            {" · "}
            {visibleSections.length} turma{visibleSections.length === 1 ? "" : "s"}
            {filterActive ? " · filtrado" : ""}
            {levelsLoading ? " · carregando níveis…" : ""}
          </p>

          <div className="cohort-students__layout">
            <div className="cohort-students__list-col">
              {visibleSections.length === 0 ? (
                <p className="muted cohort-students__filter-empty">Nenhum aluno encontrado.</p>
              ) : (
                <div className="cohort-students__sections">
                  {visibleSections.map((section) => {
                    const open = openKeys.has(section.key);
                    return (
                      <section
                        key={section.key}
                        className={[
                          "cohort-students__section",
                          section.isOwnClass ? "is-own" : "",
                          section.isUnassigned ? "is-unassigned" : "",
                          open ? "is-open" : "",
                        ]
                          .filter(Boolean)
                          .join(" ")}
                      >
                        <button
                          type="button"
                          className="cohort-students__section-head"
                          onClick={() => toggleSection(section.key)}
                          aria-expanded={open}
                        >
                          <span className="cohort-students__section-head-main">
                            <span className="cohort-students__section-copy">
                              <span className="cohort-students__section-module">
                                {section.moduleTitle}
                              </span>
                              <span
                                className={`cohort-students__section-title${
                                  section.isUnassigned
                                    ? " cohort-students__section-title--pending"
                                    : ""
                                }`}
                              >
                                {sectionTitle(section)}
                              </span>
                            </span>
                            <span className="cohort-students__section-meta">
                              <span className="cohort-students__section-count">
                                {section.studentIds.length}
                              </span>
                              <span
                                className={`cohort-students__section-chevron${open ? " is-open" : ""}`}
                                aria-hidden
                              >
                                ▾
                              </span>
                            </span>
                          </span>
                          <SectionLevelMix
                            studentIds={section.studentIds}
                            trackLevels={trackLevels}
                            loading={levelsLoading}
                          />
                        </button>

                        {open && (
                          <ul className="cohort-students__list">
                            {section.studentIds.map((studentId) => {
                              const e = enrollmentById.get(studentId);
                              if (!e) return null;
                              const selected = e.student_id === selectedStudentId;
                              const summary = trackLevels[e.student_id];
                              const attention = trackLevelNeedsAttention(summary);
                              return (
                                <li key={`${section.key}:${e.id}`}>
                                  <div
                                    className={[
                                      "cohort-students__row",
                                      selected ? "is-selected" : "",
                                      attention ? "is-attention" : "",
                                      canManageEnrollments
                                        ? "cohort-students__row--manageable"
                                        : "",
                                    ]
                                      .filter(Boolean)
                                      .join(" ")}
                                  >
                                    <button
                                      type="button"
                                      className="cohort-students__select"
                                      onClick={() => selectStudent(e.student_id)}
                                    >
                                      <span className="cohort-students__name-slot">
                                        <Tooltip content={e.student_name}>
                                          <span className="cohort-students__name">
                                            {e.student_name}
                                          </span>
                                        </Tooltip>
                                      </span>
                                      <span className="cohort-students__badge-slot">
                                        {levelsLoading && summary == null ? (
                                          <AssessmentLevelBadgeSkeleton />
                                        ) : summary?.kind === "level" ? (
                                          <AssessmentLevelBadge
                                            level={summary.level}
                                            compact
                                          />
                                        ) : (
                                          <AssessmentLevelBadge missing compact />
                                        )}
                                      </span>
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
                      </section>
                    );
                  })}
                </div>
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
                  onNotEnrolled={handleAssessmentsNotEnrolled}
                  onStudentUpdated={() => {
                    load();
                    onChanged();
                  }}
                />
              ) : (
                <div className="cohort-students__detail-empty">
                  {staleSelectionNotice ? (
                    <p className="muted">{staleSelectionNotice}</p>
                  ) : (
                    <>
                      <p className="cohort-students__detail-empty-title">
                        Avaliações do aluno
                      </p>
                      <p className="muted">
                        Selecione um aluno na lista para ver o parecer da trilha, módulos e
                        aulas.
                      </p>
                    </>
                  )}
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

      {divisionModule && assignments && professors && onApplyDivision && (
        <ModuleClassDivisionModal
          open
          moduleTitle={divisionModule.moduleTitle}
          classes={assignments[divisionModule.moduleId] ?? []}
          enrollments={enrollments}
          professors={professors}
          previousClasses={[]}
          persist
          onClose={() => setDivisionModuleId(null)}
          onApply={async (next) => {
            // Same path the Professores tab uses, so every server-side rule
            // (only enrolled students, one class per module, a class that has
            // already taught cannot be dropped) applies unchanged.
            const ok = await onApplyDivision(divisionModule.moduleId, next);
            if (ok) {
              setDivisionModuleId(null);
              onChanged();
            }
          }}
        />
      )}
    </section>
  );
}
