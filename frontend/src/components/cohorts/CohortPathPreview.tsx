import { useMemo } from "react";
import { TrackPath } from "../tracks/TrackPath";
import { buildPathFromTrackWithProgress } from "../tracks/trackPathUtils";
import type { Track } from "../../lib/tracks";
import type { CohortProgress, ModuleProfessor } from "../../lib/cohorts";

interface Props {
  track: Track;
  progress: CohortProgress;
  selectedLessonId: string | null;
  moduleProfessors?: ModuleProfessor[];
  onSelectLesson: (lessonId: string, moduleId: string) => void;
  compact?: boolean;
  embedded?: boolean;
}

export function CohortPathPreview({
  track,
  progress,
  selectedLessonId,
  moduleProfessors = [],
  onSelectLesson,
  compact = false,
  embedded = false,
}: Props) {
  const moduleProfessorByModuleId = useMemo(
    () =>
      Object.fromEntries(
        moduleProfessors.map((item) => [item.module_id, item.professor_name]),
      ),
    [moduleProfessors],
  );

  const completed = new Set(progress.completed_lesson_ids);
  const nodes = buildPathFromTrackWithProgress(track, completed, {
    selectedLessonId,
    onSelectLesson,
    showInactive: false,
    allowLockedSelect: true,
    moduleProfessorByModuleId,
  });

  if (nodes.length === 0) {
    return (
      <div className={`path-preview path-preview--empty${embedded ? " path-preview--embedded" : " card"}`}>
        <p className="muted" style={{ margin: 0 }}>
          A trilha ainda não possui módulos ativos.
        </p>
      </div>
    );
  }

  const doneCount = progress.completed_lesson_ids.length;
  const allDone = progress.current_lesson_id === null && doneCount > 0;
  const rootClass = [
    "path-preview",
    embedded ? "path-preview--embedded" : "card",
    compact ? "path-preview--compact" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rootClass}>
      <div className="path-preview__head">
        <h3 style={{ margin: 0 }}>Trilha</h3>
        {!compact && (
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
            {allDone
              ? "Turma concluiu todas as aulas."
              : `${doneCount} aula(s) concluída(s) · clique para abrir a aula`}
          </p>
        )}
        {compact && (
          <p className="muted path-preview__meta">
            {allDone ? "Concluída" : `${doneCount} concluída(s)`}
          </p>
        )}
      </div>

      <div className="path-preview__body">
        <TrackPath nodes={nodes} selectedId={selectedLessonId} />
      </div>
    </div>
  );
}
