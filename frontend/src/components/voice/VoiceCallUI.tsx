import type { CSSProperties, ReactNode } from "react";
import type { RealtimeVoiceStatus } from "../../hooks/useRealtimeVoice";

const pageLayout: CSSProperties = {
  minHeight: "100dvh",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  padding: "max(24px, env(safe-area-inset-top)) 24px max(24px, env(safe-area-inset-bottom))",
  gap: 20,
  background: "var(--surface-50, #f3f7f6)",
  boxSizing: "border-box",
};

const actionButton: CSSProperties = {
  width: 240,
  height: 52,
  padding: "0 24px",
  fontSize: 17,
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  boxSizing: "border-box",
  touchAction: "manipulation",
};

export interface VoiceCallUIProps {
  assistantName: string;
  studentFirstName: string;
  lessonTitle: string;
  trackTitle?: string;
  status: RealtimeVoiceStatus;
  streamReady: boolean;
  error: string;
  unsupportedReason?: string;
  onConnect: () => void;
  onDisconnect: () => void;
  audioElement: ReactNode;
}

export function VoiceCallUI({
  assistantName,
  studentFirstName,
  lessonTitle,
  trackTitle,
  status,
  streamReady,
  error,
  unsupportedReason,
  onConnect,
  onDisconnect,
  audioElement,
}: VoiceCallUIProps) {
  const busy = status === "connecting";
  const connected = status === "connected";
  const ended = status === "ended";
  const blocked = Boolean(unsupportedReason);

  if (ended) {
    return (
      <div style={pageLayout}>
        <div style={{ textAlign: "center", maxWidth: 420, width: "100%" }}>
          <h1 style={{ fontSize: 28, marginBottom: 8, color: "var(--brand, #0d6b5c)" }}>
            Conversa encerrada
          </h1>
          <p className="muted" style={{ fontSize: 16, lineHeight: 1.5 }}>
            Até a próxima! Volte quando quiser continuar.
          </p>
        </div>

        {audioElement}
      </div>
    );
  }

  return (
    <div style={pageLayout}>
      <div style={{ textAlign: "center", maxWidth: 420, width: "100%" }}>
        <h1 style={{ fontSize: 28, marginBottom: 4 }}>{assistantName}</h1>
        <p className="muted" style={{ fontSize: 14, marginBottom: 8 }}>
          Chamada ao vivo
        </p>
        <p className="muted" style={{ fontSize: 15, lineHeight: 1.5 }}>
          Olá, {studentFirstName}! Vamos conversar sobre <strong>{lessonTitle}</strong>
          {trackTitle ? (
            <>
              {" "}
              da trilha <strong>{trackTitle}</strong>
            </>
          ) : null}
          .
        </p>
      </div>

      <div
        style={{
          width: 120,
          height: 120,
          borderRadius: "50%",
          background: connected ? "var(--brand, #0d6b5c)" : "var(--ink-muted, #6b7c78)",
          opacity: connected && streamReady ? 1 : 0.65,
          transition: "opacity 0.3s",
          boxShadow: connected ? "0 0 0 12px rgba(13,107,92,0.15)" : "none",
          flexShrink: 0,
        }}
        aria-hidden
      />

      <p style={{ fontSize: 15, color: "var(--ink-muted, #6b7c78)", textAlign: "center" }}>
        {blocked && unsupportedReason}
        {!blocked && status === "connecting" && "Conectando…"}
        {!blocked && status === "connected" && (streamReady ? "Conectado. Pode falar." : "Conectado. Aguardando áudio…")}
        {!blocked && status === "error" && "Erro na conexão"}
        {!blocked && !status && "Toque para iniciar a chamada"}
      </p>

      {error && !blocked && (
        <div
          style={{
            color: "var(--danger)",
            background: "var(--danger-50, #fdecea)",
            padding: "12px 16px",
            borderRadius: 8,
            fontSize: 14,
            maxWidth: 420,
            textAlign: "center",
            lineHeight: 1.45,
          }}
        >
          {error}
        </div>
      )}

      {blocked && (
        <div
          style={{
            color: "var(--danger)",
            background: "var(--danger-50, #fdecea)",
            padding: "12px 16px",
            borderRadius: 8,
            fontSize: 14,
            maxWidth: 420,
            textAlign: "center",
            lineHeight: 1.45,
          }}
        >
          {unsupportedReason}
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "center", width: "100%" }}>
        {!connected && !blocked ? (
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={onConnect}
            style={actionButton}
          >
            {busy ? "Conectando…" : "Iniciar chamada"}
          </button>
        ) : connected ? (
          <button type="button" className="btn" onClick={onDisconnect} style={actionButton}>
            Encerrar
          </button>
        ) : null}
      </div>

      {audioElement}
    </div>
  );
}
