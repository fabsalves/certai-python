import { useEffect, useRef, useState } from "react";
import { api, apiErrorMessage } from "../../lib/api";
import { downloadApiFile } from "../../lib/download";
import { formatDuration, useAudioRecorder } from "../../hooks/useAudioRecorder";
import { AudioProcessStatus, AudioWaveform } from "../ui/AudioProcessStatus";
import { FileChip, FilePicker, fileKindFromName } from "../ui/FileAttachment";

const AUDIO_ACCEPT =
  ".mp3,.m4a,.wav,.ogg,.webm,.mpeg,audio/*,audio/webm,audio/mpeg,audio/mp4,audio/ogg,audio/wav";

const DOC_ACCEPT =
  ".txt,.docx,.pdf,.pptx,text/plain,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation";

type Mode = "idle" | "recording" | "processing";

/** @deprecated alias — use ContentSource */
export type LessonContentSource = ContentSource;

export type ContentSource = {
  filename: string;
  contentType?: string | null;
  kind?: string | null;
};

interface Props {
  /** Unique prefix for file input ids */
  idPrefix: string;
  importUrl: string;
  downloadUrl: string;
  disabled?: boolean;
  currentContent: string;
  source: ContentSource | null;
  onImported: (text: string, source: ContentSource) => void;
  fieldLabel?: string;
  hint?: string;
}

export function ContentSourceImport({
  idPrefix,
  importUrl,
  downloadUrl,
  disabled = false,
  currentContent,
  source,
  onImported,
  fieldLabel = "Preencher a partir de áudio ou arquivo",
  hint = "Grave ou anexe. O texto novo é acrescentado ao que já existe; o arquivo fonte fica o último anexado.",
}: Props) {
  const { status, seconds, blob, levels, error: recorderError, start, stop, reset } =
    useAudioRecorder();
  const [mode, setMode] = useState<Mode>("idle");
  const [processLabel, setProcessLabel] = useState("Processando…");
  const [error, setError] = useState("");
  const [lastFileName, setLastFileName] = useState("");
  const [downloading, setDownloading] = useState(false);
  const processedBlobRef = useRef<Blob | null>(null);
  const currentContentRef = useRef(currentContent);
  currentContentRef.current = currentContent;

  useEffect(() => {
    if (status === "recording") setMode("recording");
  }, [status]);

  useEffect(() => {
    if (status !== "recorded" || !blob || processedBlobRef.current === blob) return;
    processedBlobRef.current = blob;
    void runImport(blob, "gravacao.webm", "Transcrevendo…");
  }, [status, blob]);

  async function runImport(file: Blob, filename: string, label: string) {
    setError("");
    setProcessLabel(label);
    setMode("processing");
    setLastFileName(filename);
    try {
      const form = new FormData();
      form.append("source", file, filename);
      form.append("base_text", currentContentRef.current);
      const { data } = await api.post<{
        text: string;
        content_source_filename?: string | null;
        content_source_content_type?: string | null;
        content_source_kind?: string | null;
      }>(importUrl, form);
      const text = (data.text || "").trim();
      if (!text) {
        setError("Nenhum texto foi obtido. Tente outro arquivo ou grave de novo.");
      } else {
        onImported(text, {
          filename: data.content_source_filename || filename,
          contentType: data.content_source_content_type,
          kind: data.content_source_kind,
        });
      }
    } catch (err) {
      setError(apiErrorMessage(err, "Não foi possível importar o conteúdo."));
    } finally {
      reset();
      processedBlobRef.current = null;
      setMode("idle");
    }
  }

  async function handleAttachAudio(file: File | null) {
    if (!file) return;
    reset();
    processedBlobRef.current = null;
    await runImport(file, file.name, "Transcrevendo…");
  }

  async function handleAttachDoc(file: File | null) {
    if (!file) return;
    reset();
    processedBlobRef.current = null;
    await runImport(file, file.name, "Extraindo…");
  }

  async function startRecording() {
    setError("");
    processedBlobRef.current = null;
    await start();
  }

  async function downloadSource() {
    if (!source?.filename) return;
    setDownloading(true);
    try {
      await downloadApiFile(downloadUrl, source.filename);
    } catch (err) {
      setError(apiErrorMessage(err, "Não foi possível baixar o arquivo."));
    } finally {
      setDownloading(false);
    }
  }

  function clearError() {
    setError("");
  }

  const busy = disabled || mode === "processing";
  const showChooser = mode === "idle" && status !== "recording";
  const sourceMeta =
    source?.kind === "audio" ? "Áudio fonte" : source?.kind === "document" ? "Arquivo fonte" : "Fonte";

  return (
    <div className="lesson-report lesson-content-import">
      <div className="lesson-report__audio">
        <p className="lesson-report__label">{fieldLabel}</p>
        <p className="lesson-report__hint">{hint}</p>

        {source && mode === "idle" && status !== "recording" && (
          <div className="lesson-content-import__source">
            <FileChip
              filename={source.filename}
              kind={fileKindFromName(source.filename)}
              meta={sourceMeta}
              onDownload={() => void downloadSource()}
              downloading={downloading}
            />
          </div>
        )}

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
              id={`${idPrefix}-audio`}
              accept={AUDIO_ACCEPT}
              buttonLabel="Anexar áudio"
              buttonClassName="btn btn-ghost lesson-report__record"
              disabled={busy}
              onChange={(file) => void handleAttachAudio(file)}
            />
            <FilePicker
              id={`${idPrefix}-doc`}
              accept={DOC_ACCEPT}
              buttonLabel="Anexar arquivo"
              buttonClassName="btn btn-ghost lesson-report__record"
              disabled={busy}
              onChange={(file) => void handleAttachDoc(file)}
            />
          </div>
        )}

        {mode === "recording" && (
          <div className="lesson-report__recording" aria-live="polite">
            <AudioWaveform levels={levels} />
            <span className="lesson-report__rec-label">
              <span className="lesson-report__pulse" aria-hidden />
              Gravando {formatDuration(seconds)}
            </span>
            <button type="button" className="btn btn-primary btn-sm" onClick={stop}>
              Parar
            </button>
          </div>
        )}

        {mode === "processing" && (
          <div className="lesson-content-import__processing">
            <AudioProcessStatus label={processLabel} />
            {lastFileName ? (
              <FileChip
                filename={lastFileName}
                kind={fileKindFromName(lastFileName)}
                meta="Em processamento"
              />
            ) : null}
          </div>
        )}

        {(error || recorderError) && (
          <div className="form-error" style={{ marginTop: 10 }} role="alert">
            {error || recorderError}
            {error ? (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ marginLeft: 8 }}
                onClick={clearError}
              >
                Fechar
              </button>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

/** Lesson content import — thin wrapper around ContentSourceImport. */
export function LessonContentImport({
  lessonId,
  disabled,
  currentContent,
  source,
  onImported,
}: {
  lessonId: string;
  disabled?: boolean;
  currentContent: string;
  source: ContentSource | null;
  onImported: (text: string, source: ContentSource) => void;
}) {
  return (
    <ContentSourceImport
      idPrefix={`lesson-content-${lessonId}`}
      importUrl={`/tracks/lessons/${lessonId}/import-text`}
      downloadUrl={`/tracks/lessons/${lessonId}/content-source`}
      disabled={disabled}
      currentContent={currentContent}
      source={source}
      onImported={onImported}
      hint="Grave ou anexe. O texto novo é acrescentado ao conteúdo; o arquivo fonte fica o último anexado. Edite e salve a aula se quiser ajustar."
    />
  );
}
