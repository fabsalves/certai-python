import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { RealtimeWebRTCClient } from "../realtime/RealtimeWebRTCClient";
import { apiErrorMessage } from "../lib/api";
import { isRealtimeVoiceSupported, micPermissionErrorMessage } from "../lib/realtimeSupport";
import type { RealtimeVoiceStatus, VoiceBackend } from "../voice/types";

export type { RealtimeVoiceStatus } from "../voice/types";

const HEARTBEAT_INTERVAL_MS = 30_000;

function logAssistantSpeaking(event: string, speaking: boolean) {
  console.log(`[voice-presence] ${event} → assistantSpeaking=${speaking}`);
}

/** Thin hook — orchestrates VoiceBackend + RealtimeWebRTCClient. */
export function useRealtimeVoice(backend: VoiceBackend | null) {
  const [status, setStatus] = useState<RealtimeVoiceStatus>("");
  const [error, setError] = useState("");
  const [streamReady, setStreamReady] = useState(false);
  const [turnCount, setTurnCount] = useState(0);
  const [assistantSpeaking, setAssistantSpeaking] = useState(false);

  const clientRef = useRef<RealtimeWebRTCClient | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const markAssistantSpeaking = useCallback((event: string) => {
    logAssistantSpeaking(event, true);
    setAssistantSpeaking(true);
  }, []);

  const clearAssistantSpeaking = useCallback((event: string) => {
    logAssistantSpeaking(event, false);
    setAssistantSpeaking(false);
  }, []);

  const client = useMemo(() => {
    const instance = new RealtimeWebRTCClient();
    clientRef.current = instance;
    return instance;
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const pingHeartbeat = useCallback(() => {
    if (!backend) return;
    void backend.sendHeartbeat().catch((err) => {
      console.error("[realtime] heartbeat failed", err);
    });
  }, [backend]);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    pingHeartbeat();
    heartbeatRef.current = setInterval(pingHeartbeat, HEARTBEAT_INTERVAL_MS);
  }, [pingHeartbeat, stopHeartbeat]);

  const finishCall = useCallback(
    async (options?: { skipEndApi?: boolean }) => {
      stopHeartbeat();
      if (!options?.skipEndApi) {
        await backend?.endSession();
      }
      client.disconnect();
      setStreamReady(false);
      clearAssistantSpeaking("call.finished");
      setError("");
      setStatus("ended");
    },
    [backend, clearAssistantSpeaking, client, stopHeartbeat],
  );

  const connect = useCallback(
    async (audioElement: HTMLAudioElement | null) => {
      if (!backend) return;
      if (!isRealtimeVoiceSupported()) {
        setError("Seu navegador não suporta chamada de voz ao vivo.");
        setStatus("error");
        return;
      }
      if (status === "connecting" || status === "connected") return;

      setStatus("connecting");
      setError("");
      setStreamReady(false);
      clearAssistantSpeaking("connect.reset");

      try {
        const tokenData = await backend.fetchSession();
        startHeartbeat();

        await client.connect(audioElement, backend, {
          onStreamReady: () => setStreamReady(true),
          onConnected: () => {
            setStatus("connected");
            pingHeartbeat();
          },
          onTurnsAccepted: (count) => setTurnCount((prev) => prev + count),
          onGracefulEnd: () => {
            void finishCall();
          },
          onStreamCleared: () => {
            setStreamReady(false);
            clearAssistantSpeaking("stream.cleared");
          },
          onResponseStarted: () => {
            markAssistantSpeaking("response.created");
          },
          onResponseDone: ({ hasAudioOutput }) => {
            if (!hasAudioOutput) {
              clearAssistantSpeaking("response.done (no-audio)");
              return;
            }
            console.log(
              "[voice-presence] response.done (has-audio) → ignored, waiting for output_audio_buffer.stopped",
            );
          },
          onOutputAudioStopped: () => {
            clearAssistantSpeaking("output_audio_buffer.stopped");
          },
          onResponseInterrupted: () => {
            clearAssistantSpeaking("response.interrupted");
          },
        }, tokenData);
      } catch (err) {
        stopHeartbeat();
        client.disconnect();
        if (backend.hasActiveSession()) {
          void backend.endSession();
        } else {
          backend.clearSession();
        }

        const micMessage = micPermissionErrorMessage(err);
        if (micMessage) {
          setError(micMessage);
          setStatus("error");
          return;
        }
        if (axios.isAxiosError(err) && err.response?.status === 409) {
          setError(
            apiErrorMessage(
              err,
              "Sessão aberta em outro dispositivo ou aba. Encerre a outra chamada e tente de novo.",
            ),
          );
          setStatus("error");
          return;
        }

        const message = err instanceof Error ? err.message : "Erro ao conectar Realtime";
        setError(message);
        setStatus("error");
      }
    },
    [
      backend,
      clearAssistantSpeaking,
      client,
      finishCall,
      markAssistantSpeaking,
      pingHeartbeat,
      startHeartbeat,
      status,
      stopHeartbeat,
    ],
  );

  const disconnect = useCallback(() => {
    void finishCall();
  }, [finishCall]);

  useEffect(() => {
    return () => {
      stopHeartbeat();
      clientRef.current?.disconnect();
      void backend?.endSession();
    };
  }, [backend, stopHeartbeat]);

  return {
    status,
    error,
    streamReady,
    turnCount,
    assistantSpeaking,
    connect,
    disconnect,
  };
}
