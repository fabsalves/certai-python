import { useEffect, useState } from "react";
import type { CohortLessonNote, CohortProgress } from "../../lib/cohorts";
import { api } from "../../lib/api";
import { downloadApiFile } from "../../lib/download";
import { useApiAction } from "../../lib/useApiAction";
import { sortedLessons, sortedModules, type Track } from "../../lib/tracks";
import {
  FileAttachmentBlock,
  FileChip,
  fileKindFromName,
} from "../ui/FileAttachment";
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
  const runAction = useApiAction();
  const activeLessonId = selectedLessonId ?? progress.current_lesson_id;
  const selected = activeLessonId ? findLesson(track, activeLessonId) : null;
  const isCurrent = activeLessonId === progress.current_lesson_id;
  const isDone = activeLessonId
    ? progress.completed_lesson_ids.includes(activeLessonId)
    : false;
  const allDone = progress.current_lesson_id === null && progress.completed_lesson_ids.length > 0;

  const [notes, setNotes] = useState<CohortLessonNote[]>([]);
  const [downloading, setDownloading] = useState<"attachment" | "audio" | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get<CohortLessonNote[]>(`/cohorts/${cohortId}/lesson-notes`)
      .then(({ data }) => {
        if (!cancelled) setNotes(data);
      })
      .catch(() => {
        if (!cancelled) setNotes([]);
      });
    return () => {
      cancelled = true;
    };
  }, [cohortId, progress.completed_lesson_ids.length]);

  const note = activeLessonId
    ? notes.find((item) => item.lesson_id === activeLessonId)
    : undefined;

  async function downloadAttachment() {
    if (!activeLessonId || !note?.has_attachment) return;
    setDownloading("attachment");
    await runAction({
      run: () =>
        downloadApiFile(
          `/cohorts/${cohortId}/lessons/${activeLessonId}/attachment`,
          note.attachment_filename ?? "anexo",
        ),
      errorMessage: "Não foi possível baixar o anexo.",
    });
    setDownloading(null);
  }

  async function downloadAudio() {
    if (!activeLessonId || !note?.has_audio) return;
    setDownloading("audio");
    await runAction({
      run: () =>
        downloadApiFile(`/cohorts/${cohortId}/lessons/${activeLessonId}/audio`, "relato-aula.webm"),
      errorMessage: "Não foi possível baixar o áudio.",
    });
    setDownloading(null);
  }

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

      {isDone && note && (note.has_attachment || note.has_audio) && (
        <FileAttachmentBlock label="Arquivos do relato">
          {note.has_attachment && (
            <FileChip
              filename={note.attachment_filename ?? "anexo"}
              kind={fileKindFromName(note.attachment_filename)}
              meta="Documento anexado"
              onDownload={downloadAttachment}
              downloading={downloading === "attachment"}
            />
          )}
          {note.has_audio && (
            <FileChip
              filename="relato-aula.webm"
              kind="audio"
              meta="Áudio gravado"
              onDownload={downloadAudio}
              downloading={downloading === "audio"}
            />
          )}
        </FileAttachmentBlock>
      )}

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
