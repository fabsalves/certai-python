import { useRef } from "react";
import { useRealtimeVoice } from "../hooks/useRealtimeVoice";

export function VoiceSession() {
  const audioRef = useRef<HTMLAudioElement>(null);
  const { status, error, streamReady, connect, disconnect } = useRealtimeVoice();

  const busy = status === "connecting";
  const connected = status === "connected";

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
        gap: 20,
        background: "var(--surface-50, #f3f7f6)",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 420 }}>
        <h1 style={{ fontSize: 28, marginBottom: 8 }}>Lira — voz (POC)</h1>
        <p className="muted" style={{ fontSize: 15 }}>
          Etapa A: WebRTC direto com OpenAI Realtime. Abra o console do navegador para ver as transcrições.
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
        }}
        aria-hidden
      />

      <p style={{ fontSize: 14, color: "var(--ink-muted, #6b7c78)" }}>
        {status === "connecting" && "Conectando…"}
        {status === "connected" && (streamReady ? "Conectado — fale com a Lira" : "Conectado — aguardando áudio…")}
        {status === "error" && "Erro na conexão"}
        {!status && "Toque para iniciar a chamada"}
      </p>

      {error && (
        <div
          style={{
            color: "var(--danger)",
            background: "var(--danger-50, #fdecea)",
            padding: "10px 14px",
            borderRadius: 8,
            fontSize: 14,
            maxWidth: 420,
            textAlign: "center",
          }}
        >
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: 12 }}>
        {!connected ? (
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => void connect(audioRef.current)}
            style={{ minWidth: 160, minHeight: 48, fontSize: 16 }}
          >
            {busy ? "Conectando…" : "Iniciar chamada"}
          </button>
        ) : (
          <button
            type="button"
            className="btn"
            onClick={disconnect}
            style={{ minWidth: 160, minHeight: 48, fontSize: 16 }}
          >
            Encerrar
          </button>
        )}
      </div>

      <audio ref={audioRef} autoPlay playsInline style={{ display: "none" }} />
    </div>
  );
}
