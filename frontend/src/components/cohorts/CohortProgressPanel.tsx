import { useCallback, useEffect, useState } from "react";
import type {
  CohortLessonNote,
  CohortProgress,
  SandboxRewind,
} from "../../lib/cohorts";
import { api } from "../../lib/api";
import { downloadApiFile } from "../../lib/download";
import { useApiAction } from "../../lib/useApiAction";
import { useConfirm } from "../../lib/confirm";
import { useFeedback } from "../../lib/feedback";
import { sortedLessons, sortedModules, type Track } from "../../lib/tracks";
import {
  FileAttachmentBlock,
  FileChip,
  fileKindFromName,
} from "../ui/FileAttachment";
import {
  ClaimUnassignedStudentsModal,
  type UnassignedStudentOption,
} from "./ClaimUnassignedStudentsModal";
import { LessonAssessmentDistribution } from "./LessonAssessmentDistribution";
import { LessonReportCapture } from "./LessonReportCapture";

interface Props {
  cohortId: string;
  track: Track;
  progress: CohortProgress;
  selectedLessonId: string | null;
  canComplete: boolean;
  professorName?: string;
  /** Set when a professor is viewing: scopes "done" to their own class. */
  viewerProfessorId?: string;
  /** A test cohort: its progression can be rewound. */
  isSandbox?: boolean;
  /** Only an org admin rewinds -- and only in a test cohort. */
  canRewind?: boolean;
  onCompleted: () => void;
  /** Bridge to Alunos dossier from lesson distribution. */
  onOpenStudent?: (studentId: string) => void;
}

function findLesson(track: Track, lessonId: string) {
  for (const mod of sortedModules(track)) {
    const lesson = sortedLessons(mod).find((l) => l.id === lessonId);
    if (lesson) return { module: mod, lesson };
  }
  return null;
}

const NOTE_INGESTION_LABELS: Record<string, string> = {
  pending: "Relato aguardando processamento…",
  processing: "Processando o relato da aula…",
  done: "Relato processado.",
  failed:
    "Falha no processamento do relato. Os convites aos alunos ficam retidos até o reprocessamento.",
};

export function CohortProgressPanel({
  cohortId,
  track,
  progress,
  selectedLessonId,
  canComplete,
  professorName,
  viewerProfessorId,
  isSandbox = false,
  canRewind = false,
  onCompleted,
  onOpenStudent,
}: Props) {
  const runAction = useApiAction();
  const confirm = useConfirm();
  const feedback = useFeedback();
  const activeLessonId = selectedLessonId ?? progress.current_lesson_id;
  const selected = activeLessonId ? findLesson(track, activeLessonId) : null;
  const isCurrent = activeLessonId === progress.current_lesson_id;

  const lessonClasses = activeLessonId
    ? progress.lesson_classes.find((item) => item.lesson_id === activeLessonId)
    : undefined;
  const classStatuses = lessonClasses?.classes ?? [];
  const ownStatus = viewerProfessorId
    ? classStatuses.find((item) => item.professor_id === viewerProfessorId)
    : undefined;
  // A professor sees their own class's state; everyone else the cohort's.
  const isDone = viewerProfessorId
    ? Boolean(ownStatus?.closed)
    : activeLessonId
      ? progress.completed_lesson_ids.includes(activeLessonId)
      : false;
  const isPartial = activeLessonId
    ? progress.partial_lesson_ids.includes(activeLessonId)
    : false;
  const ownClosedCount = viewerProfessorId
    ? progress.lesson_classes.filter((entry) =>
        entry.classes.some(
          (item) => item.professor_id === viewerProfessorId && item.closed,
        ),
      ).length
    : 0;
  const allDone = viewerProfessorId
    ? progress.current_lesson_id === null && ownClosedCount > 0
    : progress.current_lesson_id === null && progress.completed_lesson_ids.length > 0;

  // Content of this lesson that was closed without being taught. Operational
  // data the professor needs to see -- a professor sees their own class only.
  const pendingClasses = (
    viewerProfessorId
      ? classStatuses.filter((item) => item.professor_id === viewerProfessorId)
      : classStatuses
  ).filter((item) => item.closed && item.pending.trim());

  const [notes, setNotes] = useState<CohortLessonNote[]>([]);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [reingesting, setReingesting] = useState(false);
  const [rewinding, setRewinding] = useState<"undo" | "reset" | null>(null);
  const [unassigned, setUnassigned] = useState<UnassignedStudentOption[]>([]);
  const [claimModalOpen, setClaimModalOpen] = useState(false);
  const [claiming, setClaiming] = useState(false);

  const loadNotes = useCallback(() => {
    return api
      .get<CohortLessonNote[]>(`/cohorts/${cohortId}/lesson-notes`)
      .then(({ data }) => setNotes(data))
      .catch(() => setNotes([]));
  }, [cohortId]);

  const activeModuleId = selected?.module.id ?? null;

  const loadUnassigned = useCallback(() => {
    if (!canComplete || !activeModuleId) {
      setUnassigned([]);
      return Promise.resolve();
    }
    return api
      .get<UnassignedStudentOption[]>(
        `/cohorts/${cohortId}/modules/${activeModuleId}/unassigned-students`,
      )
      .then(({ data }) => setUnassigned(data))
      .catch(() => setUnassigned([]));
  }, [canComplete, cohortId, activeModuleId]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes, progress.completed_lesson_ids.length]);

  useEffect(() => {
    loadUnassigned();
  }, [loadUnassigned, progress.lesson_classes]);

  useEffect(() => {
    if (unassigned.length === 0) setClaimModalOpen(false);
  }, [unassigned.length]);

  async function claimStudents(studentIds: string[]) {
    if (!activeModuleId || studentIds.length === 0) return;
    setClaiming(true);
    await runAction({
      run: async () => {
        for (const studentId of studentIds) {
          await api.post(
            `/cohorts/${cohortId}/modules/${activeModuleId}/classes/me/students`,
            { student_id: studentId },
          );
        }
      },
      successMessage:
        studentIds.length === 1
          ? "Aluno vinculado à sua turma."
          : `${studentIds.length} alunos vinculados à sua turma.`,
      errorMessage: "Não foi possível vincular os alunos.",
      onSuccess: async () => {
        setClaimModalOpen(false);
        await loadUnassigned();
        onCompleted();
      },
    });
    setClaiming(false);
  }

  // Refresh while the worker ingests a report, so the status updates live.
  const hasIngestingNotes = notes.some(
    (item) => item.ingestion_status === "pending" || item.ingestion_status === "processing",
  );
  useEffect(() => {
    if (!hasIngestingNotes) return;
    const timer = window.setInterval(loadNotes, 4000);
    return () => window.clearInterval(timer);
  }, [hasIngestingNotes, loadNotes]);

  const lessonNotes = activeLessonId
    ? notes.filter((item) => item.lesson_id === activeLessonId)
    : [];
  const showProfessorNames = classStatuses.length > 1;

  async function reingestNote() {
    if (!activeLessonId) return;
    setReingesting(true);
    await runAction({
      run: () => api.post(`/cohorts/${cohortId}/lessons/${activeLessonId}/reingest`),
      successMessage: "Reprocessamento do relato enfileirado.",
      errorMessage: "Não foi possível reprocessar o relato.",
      onSuccess: () => loadNotes(),
    });
    setReingesting(false);
  }

  async function rewind(kind: "undo" | "reset") {
    const undo = kind === "undo";
    const ok = await confirm({
      title: undo ? "Desfazer último encerramento" : "Zerar andamento",
      message: undo
        ? "Reabre a última aula encerrada desta turma e apaga o relato, a conversa " +
          "e as avaliações dela. Os alunos, os professores e os custos continuam " +
          "como estão."
        : "Apaga todo o andamento desta turma. Saem as aulas encerradas, os relatos, " +
          "as conversas e as avaliações. Os alunos, os professores e os custos " +
          "continuam como estão.",
      confirmLabel: undo ? "Desfazer" : "Zerar",
      tone: "danger",
    });
    if (!ok) return;

    setRewinding(kind);
    await runAction({
      run: () =>
        api.post<SandboxRewind>(
          `/cohorts/${cohortId}/sandbox/${undo ? "undo-last-closure" : "reset"}`,
        ),
      successMessage: undo ? undefined : "Andamento zerado.",
      errorMessage: undo
        ? "Não foi possível desfazer o encerramento."
        : "Não foi possível zerar o andamento.",
      onSuccess: ({ data }) => {
        if (undo) {
          feedback.success(
            `Encerramento desfeito: ${data.lesson_title}` +
              (data.professor_name ? ` (${data.professor_name})` : ""),
          );
        }
        onCompleted();
      },
    });
    setRewinding(null);
  }

  async function downloadNoteFile(note: CohortLessonNote, kind: "attachment" | "audio") {
    if (!activeLessonId) return;
    const filename =
      kind === "attachment"
        ? (note.attachment_filename ?? "anexo")
        : note.audio_filename || "relato-aula.webm";
    setDownloading(`${note.module_professor_id}-${kind}`);
    await runAction({
      run: () =>
        downloadApiFile(
          `/cohorts/${cohortId}/lessons/${activeLessonId}/${kind}` +
            `?module_professor_id=${note.module_professor_id}`,
          filename,
        ),
      errorMessage:
        kind === "attachment"
          ? "Não foi possível baixar o anexo."
          : "Não foi possível baixar o áudio.",
    });
    setDownloading(null);
  }

  function audioMetaLabel(source: CohortLessonNote["audio_source"]): string {
    if (source === "recording") return "Áudio gravado";
    if (source === "file") return "Áudio anexado";
    return "Áudio do relato";
  }

  if (allDone && !selected) {
    return (
      <div id="cohort-progress-panel" className="cohort-progress-panel">
        <div className="empty-state cohort-progress-panel__empty">
          <p>
            {viewerProfessorId
              ? "Você encerrou todas as suas aulas."
              : "Turma concluiu a trilha."}
          </p>
          <p className="muted" style={{ marginTop: 6 }}>
            {viewerProfessorId
              ? "Não há próxima aula para a sua turma. Clique em uma aula na trilha para revisar."
              : "Todas as aulas ativas foram encerradas. Clique em uma aula na trilha para revisar."}
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
            ? viewerProfessorId
              ? "Aula já encerrada com a sua turma."
              : "Aula já concluída por todos os professores."
            : isCurrent
              ? "Aula atual. Grave ou escreva o relato, revise e encerre para liberar a próxima."
              : isPartial
                ? "Encerrada por parte dos professores."
                : "Aguardando conclusão das aulas anteriores."}
        </p>
      </div>

      {showProfessorNames && (
        <ul className="cohort-progress-panel__classes">
          {classStatuses.map((item) => (
            <li key={item.module_professor_id}>
              <span>{item.professor_name}</span>
              <span className={item.closed ? "tag" : "muted"}>
                {item.closed ? "encerrada" : "pendente"}
              </span>
            </li>
          ))}
        </ul>
      )}

      {lessonClasses?.delayed && (
        <p className="cohort-progress-panel__delayed">
          Há professor com aula pendente enquanto a turma já avançou. Os alunos dele
          seguem parados nesta aula.
        </p>
      )}

      {canComplete && unassigned.length > 0 && (
        <div className="cohort-progress-panel__unassigned">
          <p className="cohort-progress-panel__unassigned-title">
            {unassigned.length} aluno(s) sem turma neste módulo. O encerramento fica
            bloqueado até vinculá-los.
          </p>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => setClaimModalOpen(true)}
          >
            Adicionar à minha turma
          </button>
        </div>
      )}

      <ClaimUnassignedStudentsModal
        open={claimModalOpen}
        moduleTitle={selected.module.title}
        students={unassigned}
        busy={claiming}
        onClose={() => setClaimModalOpen(false)}
        onConfirm={claimStudents}
      />

      {pendingClasses.length > 0 && (
        <div className="coverage-pending">
          <p className="coverage-pending__title">
            Conteúdo desta aula que ficou pendente
          </p>
          {pendingClasses.map((item) => (
            <p key={item.module_professor_id} className="coverage-pending__item">
              {showProfessorNames && (
                <span className="coverage-pending__who">{item.professor_name}: </span>
              )}
              {item.pending}
            </p>
          ))}
          <p className="coverage-pending__hint">
            A Lira não cobra isso dos alunos. Informe no relato quando fechar em
            uma aula seguinte.
          </p>
        </div>
      )}

      {activeLessonId && (
        <LessonAssessmentDistribution
          cohortId={cohortId}
          lessonId={activeLessonId}
          onOpenStudent={onOpenStudent}
        />
      )}

      {lessonNotes.map((note) => (
        <div key={note.module_professor_id}>
          {note.ingestion_status !== "done" && (
            <div
              className={note.ingestion_status === "failed" ? "form-error" : "muted"}
              style={{ fontSize: 14 }}
            >
              <p style={{ margin: 0 }}>
                {showProfessorNames && `${note.professor_name}: `}
                {NOTE_INGESTION_LABELS[note.ingestion_status] ?? note.ingestion_status}
              </p>
              {note.ingestion_status === "failed" && canComplete && (
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ marginTop: 8 }}
                  disabled={reingesting}
                  onClick={reingestNote}
                >
                  {reingesting ? "Enfileirando…" : "Reprocessar relato"}
                </button>
              )}
            </div>
          )}

          {(note.has_attachment || note.has_audio) && (
            <FileAttachmentBlock
              label={
                showProfessorNames
                  ? `Arquivos do relato · ${note.professor_name}`
                  : "Arquivos do relato"
              }
            >
              {note.has_attachment && (
                <FileChip
                  filename={note.attachment_filename ?? "anexo"}
                  kind={fileKindFromName(note.attachment_filename)}
                  meta="Documento anexado"
                  onDownload={() => downloadNoteFile(note, "attachment")}
                  downloading={downloading === `${note.module_professor_id}-attachment`}
                />
              )}
              {note.has_audio && (
                <FileChip
                  filename={note.audio_filename || "relato-aula.webm"}
                  kind="audio"
                  meta={audioMetaLabel(note.audio_source)}
                  onDownload={() => downloadNoteFile(note, "audio")}
                  downloading={downloading === `${note.module_professor_id}-audio`}
                />
              )}
            </FileAttachmentBlock>
          )}
        </div>
      ))}

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

      {isSandbox && canRewind && (
        <div className="sandbox-actions">
          <p className="sandbox-actions__title">Turma de teste</p>
          <p className="sandbox-actions__hint">
            O andamento desta turma pode voltar atrás quantas vezes precisar. Os
            alunos, os professores e os custos de IA continuam como estão.
          </p>
          <div className="sandbox-actions__row">
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={rewinding !== null}
              onClick={() => void rewind("undo")}
            >
              {rewinding === "undo" ? "Desfazendo…" : "Desfazer último encerramento"}
            </button>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={rewinding !== null}
              onClick={() => void rewind("reset")}
            >
              {rewinding === "reset" ? "Zerando…" : "Zerar andamento"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
