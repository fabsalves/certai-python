import { type FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../../lib/api";
import { formatDuration, useAudioRecorder } from "../../hooks/useAudioRecorder";
import { useApiAction } from "../../lib/useApiAction";
import {
  FileAttachmentBlock,
  FileChip,
  FilePicker,
  fileKindFromName,
} from "../ui/FileAttachment";

const AUDIO_ACCEPT =
  ".mp3,.m4a,.wav,.ogg,.webm,.mpeg,audio/*,audio/webm,audio/mpeg,audio/mp4,audio/ogg,audio/wav";

type AudioSource = "recording" | "file" | null;

interface Props {
  cohortId: string;
  lessonId: string;
  canComplete: boolean;
  professorName?: string;
  onCompleted: () => void;
  transcribePath?: string;
  completePath?: string;
}

function RecordingWaveform({ levels }: { levels: number[] }) {
  return (
    <div className="lesson-report__waveform" aria-hidden>
      {levels.map((level, index) => (
        <span
          key={index}
          className="lesson-report__wave-bar"
          style={{ transform: `scaleY(${Math.max(0.15, level)})` }}
        />
      ))}
    </div>
  );
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
  const {
    status,
    seconds,
    blob,
    levels,
    error: recorderError,
    start,
    stop,
    reset,
  } = useAudioRecorder();
  const [transcript, setTranscript] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioSource, setAudioSource] = useState<AudioSource>(null);
  const [transcribing, setTranscribing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const transcribedRef = useRef<Blob | File | null>(null);

  useEffect(() => {
    reset();
    setTranscript("");
    setAttachment(null);
    setAudioFile(null);
    setAudioSource(null);
    transcribedRef.current = null;
  }, [cohortId, lessonId, reset]);

  async function transcribeAudioBlob(audio: Blob, filename: string) {
    setTranscribing(true);
    await runAction({
      run: async () => {
        const form = new FormData();
        form.append("audio", audio, filename);
        return api.post<{ transcript: string }>(
          transcribePath ?? `/cohorts/${cohortId}/transcribe-report`,
          form,
          {
            headers: { "Content-Type": "multipart/form-data" },
            params: { lesson_id: lessonId },
          },
        );
      },
      errorMessage:
        "Não foi possível transcrever o áudio. Tente gravar/anexar de novo ou digite o relato.",
      onSuccess: ({ data }) => setTranscript(data.transcript),
    });
    setTranscribing(false);
  }

  useEffect(() => {
    if (status === "recording") {
      setAudioFile(null);
      setAudioSource("recording");
    }
  }, [status]);

  useEffect(() => {
    if (status !== "recorded" || !blob || transcribedRef.current === blob) return;
    setAudioFile(null);
    setAudioSource("recording");
    transcribedRef.current = blob;
    void transcribeAudioBlob(blob, "relato-aula.webm");
  }, [status, blob]);

  async function handleAttachAudio(file: File | null) {
    if (!file) return;
    reset();
    setAudioFile(file);
    setAudioSource("file");
    transcribedRef.current = file;
    await transcribeAudioBlob(file, file.name);
  }

  function clearAudio() {
    reset();
    setAudioFile(null);
    setAudioSource(null);
    transcribedRef.current = null;
  }

  async function startRecording() {
    setAudioFile(null);
    transcribedRef.current = null;
    await start();
  }

  async function submitReport(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    const form = new FormData();
    form.append("lesson_id", lessonId);
    form.append("transcript", transcript);
    if (attachment) {
      form.append("attachment", attachment);
    }
    if (audioSource === "file" && audioFile) {
      form.append("audio", audioFile, audioFile.name);
      form.append("audio_source", "file");
    } else if (audioSource === "recording" && blob) {
      form.append("audio", blob, "relato-aula.webm");
      form.append("audio_source", "recording");
    }
    await runAction({
      run: () =>
        api.post(completePath ?? `/cohorts/${cohortId}/complete-lesson`, form, {
          headers: { "Content-Type": "multipart/form-data" },
        }),
      successMessage:
        "Aula encerrada. Estamos processando o relato. Os convites saem para os alunos quando terminar.",
      errorMessage: "Não foi possível encerrar a aula. Tente novamente.",
      onSuccess: () => {
        clearAudio();
        setTranscript("");
        setAttachment(null);
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

  const busy = transcribing || submitting;
  const showChooser = status === "idle" && audioSource !== "file";
  const showRecording = status === "recording";
  const showRecorded = status === "recorded" && audioSource === "recording";
  const showAttached = audioSource === "file" && audioFile != null;

  return (
    <div className="lesson-report">
      <div className="lesson-report__audio">
        <p className="lesson-report__label">Relato da aula</p>
        <p className="lesson-report__hint">
          Grave ou anexe um áudio — o texto entra no relato para você revisar. Só um áudio por vez.
        </p>

        {showChooser && (
          <div className="lesson-report__actions">
            <button
              type="button"
              className="btn btn-ghost lesson-report__record"
              onClick={() => void startRecording()}
              disabled={busy}
            >
              <span className="lesson-report__mic" aria-hidden>●</span>
              Gravar áudio
            </button>
            <FilePicker
              id="lesson-audio"
              accept={AUDIO_ACCEPT}
              buttonLabel="Anexar áudio"
              buttonClassName="btn btn-ghost lesson-report__record"
              disabled={busy}
              onChange={(file) => void handleAttachAudio(file)}
            />
          </div>
        )}

        {showRecording && (
          <div className="lesson-report__recording" aria-live="polite">
            <RecordingWaveform levels={levels} />
            <span className="lesson-report__rec-label">
              <span className="lesson-report__pulse" aria-hidden />
              Gravando {formatDuration(seconds)}
            </span>
            <button type="button" className="btn btn-primary btn-sm" onClick={stop}>
              Parar
            </button>
          </div>
        )}

        {showRecorded && (
          <div className="lesson-report__recording">
            {transcribing ? (
              <span className="muted">Transcrevendo gravação…</span>
            ) : (
              <>
                <span className="muted">Gravação ativa. Revise o texto abaixo.</span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={clearAudio} disabled={busy}>
                  Remover
                </button>
                <FilePicker
                  id="lesson-audio-switch"
                  accept={AUDIO_ACCEPT}
                  buttonLabel="Trocar por arquivo"
                  disabled={busy}
                  onChange={(file) => void handleAttachAudio(file)}
                />
              </>
            )}
          </div>
        )}

        {showAttached && (
          <div className="lesson-report__attached">
            <FileChip
              filename={audioFile.name}
              kind="audio"
              meta={transcribing ? "Transcrevendo…" : "Áudio anexado (ativo)"}
              onClear={busy ? undefined : clearAudio}
              clearLabel="Remover"
            />
            {!transcribing && (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                disabled={busy}
                onClick={() => void startRecording()}
              >
                Trocar por gravação
              </button>
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
            placeholder="Grave ou anexe um áudio, ou digite o que a turma viu, dúvidas comuns, pontos de atenção…"
          />
        </div>

        <FileAttachmentBlock
          label="Anexo opcional"
          hint="DOCX ou TXT. Fica guardado junto com o relato."
        >
          {attachment ? (
            <FileChip
              filename={attachment.name}
              kind={fileKindFromName(attachment.name)}
              meta="Será enviado ao encerrar"
              onClear={() => setAttachment(null)}
              clearLabel="Remover"
            />
          ) : (
            <FilePicker
              id="lesson-attachment"
              accept=".docx,.txt,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              buttonLabel="Anexar documento"
              disabled={busy}
              onChange={setAttachment}
            />
          )}
        </FileAttachmentBlock>

        <button type="submit" className="btn btn-primary" disabled={busy}>
          {submitting ? "Encerrando…" : "Encerrar aula e avançar turma"}
        </button>
      </form>
    </div>
  );
}
