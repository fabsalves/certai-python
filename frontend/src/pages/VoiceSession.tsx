import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { VoiceCallUI } from "../components/voice/VoiceCallUI";
import { useRealtimeVoice } from "../hooks/useRealtimeVoice";
import { apiErrorMessage } from "../lib/api";
import { realtimeUnsupportedReason } from "../lib/realtimeSupport";
import { validateSession, type SessionValidateResponse } from "../lib/realtimeApi";

type PageState = "loading" | "ready" | "expired" | "error";

const pageLayout: CSSProperties = {
  minHeight: "100dvh",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  padding: "max(24px, env(safe-area-inset-top)) 24px max(24px, env(safe-area-inset-bottom))",
  gap: 20,
  background: "var(--surface-50, #f3f7f6)",
};

const DEFAULT_WHATSAPP_URL = "https://wa.me/5519982863180";

export function VoiceSession() {
  const { handoffToken = "" } = useParams<{ handoffToken: string }>();
  const audioRef = useRef<HTMLAudioElement>(null);

  const [pageState, setPageState] = useState<PageState>("loading");
  const [sessionInfo, setSessionInfo] = useState<SessionValidateResponse | null>(null);
  const [pageError, setPageError] = useState("");

  const { status, error, streamReady, turnCount, connect, disconnect } = useRealtimeVoice(handoffToken);

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
        <p style={{ color: "var(--danger)", maxWidth: 420, textAlign: "center", lineHeight: 1.45 }}>
          {pageError}
        </p>
        <a
          href={sessionInfo?.whatsapp_support_url ?? DEFAULT_WHATSAPP_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="btn"
          style={{ minHeight: 48, minWidth: 200, textDecoration: "none" }}
        >
          Voltar ao WhatsApp
        </a>
      </div>
    );
  }

  return (
    <VoiceCallUI
      assistantName={sessionInfo?.assistant_name ?? "Lira"}
      studentFirstName={sessionInfo?.student_first_name ?? ""}
      lessonTitle={sessionInfo?.lesson_title ?? ""}
      trackTitle={sessionInfo?.track_title}
      status={status}
      streamReady={streamReady}
      turnCount={turnCount}
      error={error}
      whatsappSupportUrl={sessionInfo?.whatsapp_support_url ?? DEFAULT_WHATSAPP_URL}
      unsupportedReason={realtimeUnsupportedReason() ?? undefined}
      onConnect={() => void connect(audioRef.current)}
      onDisconnect={disconnect}
      audioElement={
        <audio ref={audioRef} autoPlay playsInline style={{ display: "none" }} />
      }
    />
  );
}
