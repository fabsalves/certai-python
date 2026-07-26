import { TrackPath } from "./TrackPath";
import { buildPathFromTrack } from "./trackPathUtils";
import type { Track } from "../../lib/tracks";

interface Props {
  track: Track;
  selectedLessonId: string | null;
  onSelectLesson: (lessonId: string, moduleId: string) => void;
}

export function TrackPathPreview({ track, selectedLessonId, onSelectLesson }: Props) {
  const nodes = buildPathFromTrack(track, {
    selectedLessonId,
    onSelectLesson,
    showInactive: true,
  });

  if (nodes.length === 0) {
    return (
      <div className="path-preview path-preview--empty card">
        <p className="muted" style={{ margin: 0 }}>
          Adicione módulos e aulas para ver o percurso.
        </p>
      </div>
    );
  }

  return (
    <div className={`path-preview card${!track.is_active ? " path-preview--track-inactive" : ""}`}>
      <div className="path-preview__head">
        <h3 style={{ margin: 0 }}>Percurso</h3>
        {!track.is_active ? (
          <p className="path-preview__notice">
            Trilha desativada. Turmas novas não podem usar; você ainda edita e visualiza tudo aqui.
          </p>
        ) : (
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 13 }}>
            Como a turma percorre as aulas
          </p>
        )}
      </div>
      <div className="path-preview__body">
        <TrackPath nodes={nodes} selectedId={selectedLessonId} />
      </div>
    </div>
  );
}
