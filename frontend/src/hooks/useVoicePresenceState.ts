import { useEffect, useState } from "react";
import type { RealtimeVoiceStatus } from "../voice/types";

export type VoicePresence =
  | "idle"
  | "connecting"
  | "preparing"
  | "listening"
  | "speaking"
  | "error"
  | "ended";

const PRESENCE_LABELS: Record<VoicePresence, string> = {
  idle: "Pronta para conversar",
  connecting: "Conectando…",
  preparing: "Preparando áudio…",
  listening: "Pode falar",
  speaking: "Lira está falando",
  error: "Erro na conexão",
  ended: "",
};

export function getVoicePresenceLabel(presence: VoicePresence): string {
  return PRESENCE_LABELS[presence] ?? PRESENCE_LABELS.idle;
}

export function useVoicePresenceState({
  status,
  streamReady,
  assistantSpeaking,
}: {
  status: RealtimeVoiceStatus;
  streamReady: boolean;
  assistantSpeaking: boolean;
}) {
  const [presence, setPresence] = useState<VoicePresence>("idle");

  useEffect(() => {
    function syncPresence() {
      if (status === "ended") {
        setPresence("ended");
        return;
      }
      if (status === "error") {
        setPresence("error");
        return;
      }
      if (status === "") {
        setPresence("idle");
        return;
      }
      if (status === "connecting") {
        setPresence("connecting");
        return;
      }
      if (status === "connected") {
        if (!streamReady) {
          setPresence("preparing");
          return;
        }
        if (assistantSpeaking) {
          setPresence("speaking");
          return;
        }
        setPresence("listening");
        return;
      }
      setPresence("idle");
    }

    syncPresence();
    const id = window.setInterval(syncPresence, 120);
    return () => window.clearInterval(id);
  }, [status, streamReady, assistantSpeaking]);

  return {
    presence,
    label: getVoicePresenceLabel(presence),
  };
}
