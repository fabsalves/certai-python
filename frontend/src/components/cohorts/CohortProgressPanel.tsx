import type { CohortProgress } from "../../lib/cohorts";
import { sortedLessons, sortedModules, type Track } from "../../lib/tracks";
import { LessonReportCapture } from "./LessonReportCapture";

interface Props {
  cohortId: string;
  track: Track;
  progress: CohortProgress;
  selectedLessonId: string | null;
  canComplete: boolean;
  professorName?: string;
  onCompleted: () => void;
}

function findLesson(track: Track, lessonId: string) {
  for (const mod of sortedModules(track)) {
    const lesson = sortedLessons(mod).find((l) => l.id === lessonId);
    if (lesson) return { module: mod, lesson };
  }
  return null;
}

export function CohortProgressPanel({
  cohortId,
  track,
  progress,
  selectedLessonId,
  canComplete,
  professorName,
  onCompleted,
}: Props) {
  const activeLessonId = selectedLessonId ?? progress.current_lesson_id;
  const selected = activeLessonId ? findLesson(track, activeLessonId) : null;
  const isCurrent = activeLessonId === progress.current_lesson_id;
  const isDone = activeLessonId
    ? progress.completed_lesson_ids.includes(activeLessonId)
    : false;
  const allDone = progress.current_lesson_id === null && progress.completed_lesson_ids.length > 0;

  if (allDone && !selected) {
    return (
      <div id="cohort-progress-panel" className="cohort-progress-panel">
        <div className="empty-state cohort-progress-panel__empty">
          <p>Turma concluiu a trilha.</p>
          <p className="muted" style={{ marginTop: 6 }}>
            Todas as aulas ativas foram encerradas. Clique em uma aula na trilha para revisar.
          </p>
        </div>
      </div>
    );
  }

  if (!selected) {
    return (
      <div id="cohort-progress-panel" className="cohort-progress-panel">
        <p className="muted cohort-progress-panel__hint">
          Selecione uma aula na trilha ao lado para ver detalhes ou encerrar a aula atual.
        </p>
      </div>
    );
  }

  return (
    <section id="cohort-progress-panel" className="cohort-progress-panel">
      <div className="cohort-progress-panel__head">
        <span className="tag">{selected.module.title}</span>
        <h2 style={{ margin: "8px 0 0" }}>{selected.lesson.title}</h2>
        <p className="muted" style={{ marginTop: 6, fontSize: 14 }}>
          {isDone
            ? "Aula já concluída pela turma."
            : isCurrent
              ? "Aula atual — grave ou escreva o relato, revise e encerre para liberar a próxima."
              : "Aguardando conclusão das aulas anteriores."}
        </p>
      </div>

      {isCurrent && activeLessonId && (
        <LessonReportCapture
          key={activeLessonId}
          cohortId={cohortId}
          lessonId={activeLessonId}
          canComplete={canComplete}
          professorName={professorName}
          onCompleted={onCompleted}
        />
      )}
    </section>
  );
}
