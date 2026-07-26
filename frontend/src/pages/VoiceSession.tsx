import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { VoiceCallUI } from "../components/voice/VoiceCallUI";
import { useRealtimeVoice } from "../hooks/useRealtimeVoice";
import { useVoicePresenceState } from "../hooks/useVoicePresenceState";
import { apiErrorMessage } from "../lib/api";
import { realtimeUnsupportedReason } from "../lib/realtimeSupport";
import { validateSession, type SessionValidateResponse } from "../lib/realtimeApi";
import { createCertaiVoiceBackend } from "../voice/certaiVoiceBackend";

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

const retryButton: CSSProperties = {
  minHeight: 48,
  minWidth: 200,
};

export function VoiceSession() {
  const { handoffToken = "" } = useParams<{ handoffToken: string }>();
  const audioRef = useRef<HTMLAudioElement>(null);

  const [pageState, setPageState] = useState<PageState>("loading");
  const [sessionInfo, setSessionInfo] = useState<SessionValidateResponse | null>(null);
  const [pageError, setPageError] = useState("");

  const voiceBackend = useMemo(
    () => (handoffToken ? createCertaiVoiceBackend(handoffToken) : null),
    [handoffToken],
  );
  const { status, error, streamReady, assistantSpeaking, connect, disconnect } =
    useRealtimeVoice(voiceBackend);
  const { presence, label: presenceLabel } = useVoicePresenceState({
    status,
    streamReady,
    assistantSpeaking,
  });

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
              "Este link de voz expirou. Você precisará de um novo convite para continuar.",
            ),
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

  if (pageState === "expired") {
    return (
      <div style={pageLayout}>
        <h1 style={{ fontSize: 24, marginBottom: 12 }}>Chamada de voz</h1>
        <p style={{ color: "var(--danger)", maxWidth: 420, textAlign: "center", lineHeight: 1.45 }}>
          {pageError}
        </p>
      </div>
    );
  }

  if (pageState === "error") {
    return (
      <div style={pageLayout}>
        <h1 style={{ fontSize: 24, marginBottom: 12 }}>Chamada de voz</h1>
        <p style={{ color: "var(--danger)", maxWidth: 420, textAlign: "center", lineHeight: 1.45 }}>
          {pageError}
        </p>
        <button
          type="button"
          className="btn btn-primary"
          style={retryButton}
          onClick={() => window.location.reload()}
        >
          Tentar novamente
        </button>
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
      presence={presence}
      presenceLabel={presenceLabel}
      error={error}
      unsupportedReason={realtimeUnsupportedReason() ?? undefined}
      audioRef={audioRef}
      onConnect={() => void connect(audioRef.current)}
      onDisconnect={disconnect}
    />
  );
}
