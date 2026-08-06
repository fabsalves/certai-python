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
  micMuted: boolean;
  audioRef: RefObject<HTMLAudioElement | null>;
  onConnect: () => void;
  onDisconnect: () => void;
  onToggleMic: () => void;
}

function MicIcon({ muted }: { muted: boolean }) {
  if (muted) {
    return (
      <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden focusable="false">
        <path
          fill="currentColor"
          d="M19.1 18.3 4.7 3.9 3.3 5.3l4.1 4.1V12a4.5 4.5 0 0 0 6.7 3.9l1.5 1.5A6.5 6.5 0 0 1 5.5 13H4a8 8 0 0 0 7 7.9V23h2v-2.1a8 8 0 0 0 3.8-1.5l3.9 3.9 1.4-1.4ZM12 14a2.5 2.5 0 0 1-2.5-2.5v-.7l3.9 3.9c-.44.2-.91.3-1.4.3Zm0-10a2.5 2.5 0 0 1 2.5 2.5v4.2l2 2V6.5A4.5 4.5 0 0 0 7.7 3.4l1.6 1.6A2.5 2.5 0 0 1 12 4Z"
        />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden focusable="false">
      <path
        fill="currentColor"
        d="M12 14a2.5 2.5 0 0 0 2.5-2.5v-5A2.5 2.5 0 0 0 12 4a2.5 2.5 0 0 0-2.5 2.5v5A2.5 2.5 0 0 0 12 14Zm5-2.5A5 5 0 0 1 7 11.5H5.5a6.5 6.5 0 0 0 6 6.4V21h1v-3.1a6.5 6.5 0 0 0 6-6.4H17Z"
      />
    </svg>
  );
}

function HangupIcon() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden focusable="false">
      <path
        fill="currentColor"
        d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1.1-.2 1.2.4 2.5.6 3.8.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.6.6 3.8.1.4 0 .8-.3 1.1L6.6 10.8Z"
        transform="rotate(135 12 12)"
      />
    </svg>
  );
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
  micMuted,
  audioRef,
  onConnect,
  onDisconnect,
  onToggleMic,
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
          <div className="voice-call__controls" role="group" aria-label="Controles da chamada">
            <button
              type="button"
              className={`voice-call__control${micMuted ? " voice-call__control--muted" : ""}`}
              onClick={onToggleMic}
              aria-pressed={micMuted}
              aria-label={micMuted ? "Ativar microfone" : "Silenciar microfone"}
            >
              <span className="voice-call__control-btn">
                <MicIcon muted={micMuted} />
              </span>
              <span className="voice-call__control-label">{micMuted ? "Mudo" : "Microfone"}</span>
            </button>
            <button
              type="button"
              className="voice-call__control voice-call__control--end"
              onClick={onDisconnect}
              aria-label="Encerrar chamada"
            >
              <span className="voice-call__control-btn">
                <HangupIcon />
              </span>
              <span className="voice-call__control-label">Encerrar</span>
            </button>
          </div>
        ) : null}
      </footer>

      <audio ref={audioRef} autoPlay playsInline className="voice-call__audio" />
    </div>
  );
}
