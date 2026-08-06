import { useMemo } from "react";
import { TrackPath } from "../tracks/TrackPath";
import { buildPathFromTrackWithProgress } from "../tracks/trackPathUtils";
import type { Track } from "../../lib/tracks";
import type { CohortProgress, ModuleProfessor, PathProgressView } from "../../lib/cohorts";
import { pathProgressForViewer } from "../../lib/cohorts";

interface Props {
  track: Track;
  progress: CohortProgress;
  selectedLessonId: string | null;
  moduleProfessors?: ModuleProfessor[];
  onSelectLesson: (lessonId: string, moduleId: string) => void;
  compact?: boolean;
  embedded?: boolean;
  /** When set, path mirrors that professor's class instead of the cohort. */
  viewerProfessorId?: string | null;
  /**
   * Full path view override (e.g. playground student session). Wins over
   * viewerProfessorId when provided.
   */
  pathView?: PathProgressView;
  /**
   * Override for playground (admin token + simulated professor): API current
   * is cohort-scoped, so the caller passes the class-scoped next lesson.
   */
  currentLessonId?: string | null;
}

export function CohortPathPreview({
  track,
  progress,
  selectedLessonId,
  moduleProfessors = [],
  onSelectLesson,
  compact = false,
  embedded = false,
  viewerProfessorId,
  pathView: pathViewProp,
  currentLessonId,
}: Props) {
  const moduleProfessorByModuleId = useMemo(() => {
    const names: Record<string, string[]> = {};
    for (const item of moduleProfessors) {
      (names[item.module_id] ??= []).push(item.professor_name);
    }
    return Object.fromEntries(
      Object.entries(names).map(([moduleId, list]) => [moduleId, list.join(" / ")]),
    );
  }, [moduleProfessors]);

  const derivedView = useMemo(
    () => pathProgressForViewer(progress, viewerProfessorId),
    [progress, viewerProfessorId],
  );
  const view = pathViewProp ?? derivedView;

  const resolvedCurrentId =
    currentLessonId !== undefined ? currentLessonId : view.currentLessonId;

  const nodes = buildPathFromTrackWithProgress(
    track,
    new Set(view.completedLessonIds),
    {
      selectedLessonId,
      onSelectLesson,
      showInactive: false,
      allowLockedSelect: true,
      moduleProfessorByModuleId,
      partialLessonIds: new Set(view.partialLessonIds),
      delayedLessonIds: new Set(view.delayedLessonIds),
      currentLessonId: resolvedCurrentId,
    },
  );

  if (nodes.length === 0) {
    return (
      <div className={`path-preview path-preview--empty${embedded ? " path-preview--embedded" : " card"}`}>
        <p className="muted" style={{ margin: 0 }}>
          A trilha ainda não possui módulos ativos.
        </p>
      </div>
    );
  }

  const doneCount = view.doneCount;
  const allDone = resolvedCurrentId === null && doneCount > 0;
  const rootClass = [
    "path-preview",
    embedded ? "path-preview--embedded" : "card",
    compact ? "path-preview--compact" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const summary =
    view.scope === "student"
      ? allDone
        ? "Todas as aulas da sua turma já foram liberadas."
        : `${doneCount} aula(s) liberada(s) · clique para abrir`
      : view.scope === "class"
        ? allDone
          ? "Você encerrou todas as suas aulas."
          : `${doneCount} aula(s) encerrada(s) com a sua turma · clique para abrir`
        : allDone
          ? "Turma concluiu todas as aulas."
          : `${doneCount} aula(s) concluída(s) · clique para abrir a aula`;

  const compactSummary =
    view.scope === "student"
      ? allDone
        ? "Liberadas"
        : `${doneCount} liberada(s)`
      : view.scope === "class"
        ? allDone
          ? "Suas aulas ok"
          : `${doneCount} encerrada(s)`
        : allDone
          ? "Concluída"
          : `${doneCount} concluída(s)`;

  return (
    <div className={rootClass}>
      <div className="path-preview__head">
        <h3 style={{ margin: 0 }}>Trilha</h3>
        {!compact && (
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
            {summary}
          </p>
        )}
        {compact && (
          <p className="muted path-preview__meta">{compactSummary}</p>
        )}
      </div>

      <div className="path-preview__body">
        <TrackPath nodes={nodes} selectedId={selectedLessonId} />
      </div>
    </div>
  );
}
