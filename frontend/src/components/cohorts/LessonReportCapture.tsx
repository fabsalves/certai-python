import { type FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { formatDuration, useAudioRecorder } from "../../hooks/useAudioRecorder";
import { useApiAction } from "../../lib/useApiAction";

interface Props {
  cohortId: string;
  lessonId: string;
  canComplete: boolean;
  professorName?: string;
  onCompleted: () => void;
  transcribePath?: string;
  completePath?: string;
}

export function LessonReportCapture({
  cohortId,
  lessonId,
  canComplete,
  professorName,
  onCompleted,
  transcribePath,
  completePath,
}: Props) {
  const runAction = useApiAction();
  const { status, seconds, blob, error: recorderError, start, stop, reset } = useAudioRecorder();
  const [transcript, setTranscript] = useState("");
  const [transcribing, setTranscribing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const transcribedRef = useRef<Blob | null>(null);

  useEffect(() => {
    reset();
    setTranscript("");
    transcribedRef.current = null;
  }, [cohortId, lessonId, reset]);

  async function transcribeRecording(audio: Blob) {
    setTranscribing(true);
    await runAction({
      run: async () => {
        const form = new FormData();
        form.append("audio", audio, "relato-aula.webm");
        return api.post<{ transcript: string }>(
          transcribePath ?? `/cohorts/${cohortId}/transcribe-report`,
          form,
          {
            headers: { "Content-Type": "multipart/form-data" },
            params: { lesson_id: lessonId },
          },
        );
      },
      errorMessage: "Não foi possível transcrever o áudio. Tente gravar de novo ou digite o relato.",
      onSuccess: ({ data }) => setTranscript(data.transcript),
    });
    setTranscribing(false);
  }

  useEffect(() => {
    if (status !== "recorded" || !blob || transcribedRef.current === blob) return;
    transcribedRef.current = blob;
    transcribeRecording(blob);
  }, [status, blob]);

  async function submitReport(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    await runAction({
      run: () =>
        api.post(completePath ?? `/cohorts/${cohortId}/complete-lesson`, {
          lesson_id: lessonId,
          transcript,
        }),
      successMessage: "Aula encerrada. A turma avançou na trilha.",
      errorMessage: "Não foi possível encerrar a aula. Tente novamente.",
      onSuccess: () => {
        reset();
        transcribedRef.current = null;
        setTranscript("");
        onCompleted();
      },
    });
    setSubmitting(false);
  }

  if (!canComplete) {
    return (
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        Só {professorName ? `o professor ${professorName}` : "o professor deste módulo"} pode encerrar a aula.
      </p>
    );
  }

  return (
    <div className="lesson-report">
      <div className="lesson-report__audio">
        <p className="lesson-report__label">Relato da aula</p>
        {status === "idle" && (
          <button type="button" className="btn btn-ghost lesson-report__record" onClick={start}>
            <span className="lesson-report__mic" aria-hidden>●</span>
            Gravar áudio
          </button>
        )}
        {status === "recording" && (
          <div className="lesson-report__recording">
            <span className="lesson-report__pulse" aria-hidden />
            <span>Gravando {formatDuration(seconds)}</span>
            <button type="button" className="btn btn-primary btn-sm" onClick={stop}>
              Parar
            </button>
          </div>
        )}
        {status === "recorded" && (
          <div className="lesson-report__recording">
            {transcribing ? (
              <span className="muted">Transcrevendo…</span>
            ) : (
              <>
                <span className="muted">Gravação pronta — revise o texto abaixo</span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={reset}>
                  Regravar
                </button>
              </>
            )}
          </div>
        )}
        {recorderError && (
          <div className="form-error" style={{ marginTop: 10 }}>{recorderError}</div>
        )}
      </div>

      <form className="lesson-report__form" onSubmit={submitReport}>
        <div className="field">
          <label htmlFor="lesson-transcript">
            Texto do relato {transcribing ? "(transcrevendo…)" : "(revise antes de enviar)"}
          </label>
          <textarea
            id="lesson-transcript"
            className="input"
            rows={6}
            value={transcript}
            onChange={(ev) => setTranscript(ev.target.value)}
            disabled={transcribing}
            placeholder="Grave o áudio ou digite o que a turma viu, dúvidas comuns, pontos de atenção…"
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={submitting || transcribing}>
          {submitting ? "Encerrando…" : "Encerrar aula e avançar turma"}
        </button>
      </form>
    </div>
  );
}
