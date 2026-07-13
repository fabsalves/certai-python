import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { useRealtimeVoice } from "../hooks/useRealtimeVoice";
import { apiErrorMessage } from "../lib/api";
import { validateSession, type SessionValidateResponse } from "../lib/realtimeApi";

type PageState = "loading" | "ready" | "expired" | "error";

const pageLayout: CSSProperties = {
  minHeight: "100vh",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  padding: 24,
  gap: 20,
  background: "var(--surface-50, #f3f7f6)",
};

export function VoiceSession() {
  const { handoffToken = "" } = useParams<{ handoffToken: string }>();
  const audioRef = useRef<HTMLAudioElement>(null);

  const [pageState, setPageState] = useState<PageState>("loading");
  const [sessionInfo, setSessionInfo] = useState<SessionValidateResponse | null>(null);
  const [pageError, setPageError] = useState("");

  const { status, error, streamReady, connect, disconnect } = useRealtimeVoice(handoffToken);

  useEffect(() => {
    if (!handoffToken) {
      setPageState("error");
      setPageError("Link de voz inválido.");
      return;
    }

    let cancelled = false;
    setPageState("loading");
    setPageError("");

    void validateSession(handoffToken)
      .then((data) => {
        if (cancelled) return;
        setSessionInfo(data);
        setPageState("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        if (axios.isAxiosError(err) && err.response?.status === 401) {
          setPageState("expired");
          setPageError(
            apiErrorMessage(
              err,
              "Este link de voz expirou. Volte ao WhatsApp e peça um novo convite."
            )
          );
          return;
        }
        setPageState("error");
        setPageError(apiErrorMessage(err, "Não foi possível validar o link de voz."));
      });

    return () => {
      cancelled = true;
    };
  }, [handoffToken]);

  const busy = status === "connecting";
  const connected = status === "connected";

  if (pageState === "loading") {
    return (
      <div style={pageLayout}>
        <p className="muted">Validando link…</p>
      </div>
    );
  }

  if (pageState === "expired" || pageState === "error") {
    return (
      <div style={pageLayout}>
        <h1 style={{ fontSize: 24, marginBottom: 12 }}>Chamada de voz</h1>
        <p style={{ color: "var(--danger)", maxWidth: 420, textAlign: "center" }}>{pageError}</p>
      </div>
    );
  }

  return (
    <div style={pageLayout}>
      <div style={{ textAlign: "center", maxWidth: 420 }}>
        <h1 style={{ fontSize: 28, marginBottom: 8 }}>
          {sessionInfo?.assistant_name ?? "Lira"} — voz ao vivo
        </h1>
        <p className="muted" style={{ fontSize: 15 }}>
          Olá, {sessionInfo?.student_first_name}! Vamos conversar sobre{" "}
          <strong>{sessionInfo?.lesson_title}</strong>
          {sessionInfo?.track_title ? (
            <>
              {" "}
              da trilha <strong>{sessionInfo.track_title}</strong>
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
