import type { RefObject } from "react";
import type { RealtimeVoiceStatus } from "../../voice/types";
import type { VoicePresence } from "../../hooks/useVoicePresenceState";

export interface VoiceCallUIProps {
  assistantName: string;
  studentFirstName: string;
  lessonTitle: string;
  trackTitle?: string;
  status: RealtimeVoiceStatus;
  presence: VoicePresence;
  presenceLabel: string;
  error: string;
  unsupportedReason?: string;
  audioRef: RefObject<HTMLAudioElement | null>;
  onConnect: () => void;
  onDisconnect: () => void;
}

function VoicePresenceCircle({ presence }: { presence: VoicePresence }) {
  return (
    <div className={`voice-presence voice-presence--${presence}`} aria-hidden>
      <div className="voice-presence__halo" />
      <div className="voice-presence__core" />
    </div>
  );
}

function VoiceStatusPill({ presence, label }: { presence: VoicePresence; label: string }) {
  if (!label) return null;

  return (
    <div
      className={`voice-status-pill voice-status-pill--${presence}`}
      role="status"
      aria-live="polite"
    >
      <span className="voice-status-pill__dot" aria-hidden />
      <span className="voice-status-pill__label">{label}</span>
    </div>
  );
}

export function VoiceCallUI({
  assistantName,
  studentFirstName,
  lessonTitle,
  trackTitle,
  status,
  presence,
  presenceLabel,
  error,
  unsupportedReason,
  audioRef,
  onConnect,
  onDisconnect,
}: VoiceCallUIProps) {
  const busy = status === "connecting";
  const connected = status === "connected";
  const ended = status === "ended";
  const blocked = Boolean(unsupportedReason);

  if (ended) {
    return (
      <div className="voice-call voice-call--ended">
        <div style={{ textAlign: "center", maxWidth: 420, width: "100%" }}>
          <h1 className="voice-call__name">Conversa encerrada</h1>
          <p className="voice-call__farewell">Até a próxima! Volte quando quiser continuar.</p>
        </div>
        <audio ref={audioRef} autoPlay playsInline className="voice-call__audio" />
      </div>
    );
  }

  return (
    <div className="voice-call">
      <header className="voice-call__context">
        <h1 className="voice-call__name">{assistantName}</h1>
        <p className="voice-call__subtitle">Chamada ao vivo</p>
        <p className="voice-call__greeting">
          Olá, {studentFirstName}! Vamos conversar sobre <strong>{lessonTitle}</strong>
          {trackTitle ? (
            <>
              {" "}
              da trilha <strong>{trackTitle}</strong>
            </>
          ) : null}
          .
        </p>
      </header>

      <main className="voice-call__stage">
        <VoicePresenceCircle presence={presence} />
        {!blocked && <VoiceStatusPill presence={presence} label={presenceLabel} />}
      </main>

      <footer className="voice-call__footer">
        {error && !blocked && (
          <div className="voice-call__alert" role="alert">
            {error}
          </div>
        )}

        {blocked && (
          <div className="voice-call__alert" role="alert">
            {unsupportedReason}
          </div>
        )}

        {!connected && !blocked ? (
          <button
            type="button"
            className="btn btn-primary voice-call__action"
            disabled={busy}
            onClick={onConnect}
          >
            {busy ? "Conectando…" : "Iniciar chamada"}
          </button>
        ) : connected ? (
          <button type="button" className="btn voice-call__action" onClick={onDisconnect}>
            Encerrar
          </button>
        ) : null}
      </footer>

      <audio ref={audioRef} autoPlay playsInline className="voice-call__audio" />
    </div>
  );
}
