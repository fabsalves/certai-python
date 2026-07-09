import { useId, useRef, type ChangeEvent, type ReactNode } from "react";

function FileGlyph({ kind }: { kind?: "doc" | "audio" | "pdf" }) {
  if (kind === "audio") {
    return (
      <svg className="file-chip__icon" width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
        <path
          d="M4.5 7.5v3M7 5.5v7M9.5 4v10M12 6.5v5M14.5 8v2"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  return (
    <svg className="file-chip__icon" width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
      <path
        d="M5 2.5h5.5L14 6v9.5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-12a1 1 0 0 1 1-1Z"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
      />
      <path d="M10.5 2.5V6H14" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

export function fileKindFromName(filename: string | null | undefined): "doc" | "audio" | "pdf" {
  const ext = (filename ?? "").split(".").pop()?.toLowerCase();
  if (ext === "webm" || ext === "mp3" || ext === "wav" || ext === "ogg" || ext === "m4a") return "audio";
  if (ext === "pdf") return "pdf";
  return "doc";
}

interface FileChipProps {
  filename: string;
  meta?: string;
  kind?: "doc" | "audio" | "pdf";
  onDownload?: () => void;
  downloading?: boolean;
  onClear?: () => void;
  clearLabel?: string;
}

export function FileChip({
  filename,
  meta,
  kind,
  onDownload,
  downloading,
  onClear,
  clearLabel = "Remover",
}: FileChipProps) {
  return (
    <div className="file-chip">
      <FileGlyph kind={kind ?? fileKindFromName(filename)} />
      <div className="file-chip__body">
        <span className="file-chip__name" title={filename}>
          {filename}
        </span>
        {meta && <span className="file-chip__meta">{meta}</span>}
      </div>
      <div className="file-chip__actions">
        {onDownload && (
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={downloading}
            onClick={onDownload}
          >
            {downloading ? "Baixando…" : "Baixar"}
          </button>
        )}
        {onClear && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClear}>
            {clearLabel}
          </button>
        )}
      </div>
    </div>
  );
}

interface FilePickerProps {
  id?: string;
  accept: string;
  disabled?: boolean;
  buttonLabel?: string;
  onChange: (file: File | null) => void;
}

export function FilePicker({
  id,
  accept,
  disabled,
  buttonLabel = "Escolher arquivo",
  onChange,
}: FilePickerProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const inputRef = useRef<HTMLInputElement>(null);

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    onChange(e.target.files?.[0] ?? null);
  }

  function openPicker() {
    if (inputRef.current) {
      inputRef.current.value = "";
      inputRef.current.click();
    }
  }

  return (
    <div className="file-picker">
      <input
        id={inputId}
        ref={inputRef}
        className="file-picker__input"
        type="file"
        accept={accept}
        disabled={disabled}
        onChange={handleChange}
      />
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        disabled={disabled}
        onClick={openPicker}
      >
        {buttonLabel}
      </button>
    </div>
  );
}

interface FileAttachmentBlockProps {
  label: string;
  hint?: string;
  children: ReactNode;
}

export function FileAttachmentBlock({ label, hint, children }: FileAttachmentBlockProps) {
  return (
    <div className="file-attachment">
      <p className="file-attachment__label">{label}</p>
      {hint && <p className="file-attachment__hint">{hint}</p>}
      <div className="file-attachment__body">{children}</div>
    </div>
  );
}
