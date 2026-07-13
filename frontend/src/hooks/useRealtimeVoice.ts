import { useCallback, useEffect, useRef, useState } from "react";
import {
  endVoiceSession,
  fetchRealtimeToken,
  relayTurns,
  sendHeartbeat,
  type RealtimeTokenResponse,
  type TurnRelayItem,
} from "../lib/realtimeApi";
import {
  clearStoredVoiceSession,
  getStoredReconnectSessionId,
  setStoredVoiceSession,
} from "../lib/sessionRealtimeLock";

const REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";
const HEARTBEAT_INTERVAL_MS = 30_000;

export type RealtimeVoiceStatus = "" | "connecting" | "connected" | "error";

function normalizeRealtimeResponseOutput(response: { output?: unknown } | undefined): unknown[] {
  const raw = response?.output;
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === "object" && Array.isArray((raw as { items?: unknown[] }).items)) {
    return (raw as { items: unknown[] }).items;
  }
  return [];
}

function extractAssistantText(output: unknown[]): string {
  const parts: string[] = [];
  for (const item of output) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;

    if (row.type === "output_text" && typeof row.text === "string") {
      parts.push(row.text);
    }

    if (Array.isArray(row.content)) {
      for (const part of row.content) {
        if (!part || typeof part !== "object") continue;
        const p = part as Record<string, unknown>;
        const partType = p.type;

        if ((partType === "output_text" || partType === "text") && typeof p.text === "string") {
          parts.push(p.text);
        } else if (
          (partType === "output_audio" || partType === "audio" || partType === "audio_output") &&
          typeof p.transcript === "string"
        ) {
          parts.push(p.transcript);
        } else if (typeof p.transcript === "string" && p.transcript.trim()) {
          parts.push(p.transcript);
        }
      }
    }

    if (typeof row.transcript === "string" && row.transcript.trim()) {
      parts.push(row.transcript);
    }
  }
  return parts.join(" ").trim();
}

function responseId(response: unknown): string {
  if (!response || typeof response !== "object") return `turn-${Date.now()}`;
  const id = (response as { id?: unknown }).id;
  return typeof id === "string" && id ? id : `turn-${Date.now()}`;
}

export function useRealtimeVoice(handoffToken: string) {
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastUserTranscriptRef = useRef("");
  const sequenceRef = useRef(0);
  const voiceSessionIdRef = useRef("");
  const lockTokenRef = useRef("");

  const [status, setStatus] = useState<RealtimeVoiceStatus>("");
  const [error, setError] = useState("");
  const [streamReady, setStreamReady] = useState(false);
  const [turnCount, setTurnCount] = useState(0);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatRef.current) {
      clearInterval(heartbeatRef.current);
      heartbeatRef.current = null;
    }
  }, []);

  const persistTurns = useCallback(async (turns: TurnRelayItem[]) => {
    const voiceSessionId = voiceSessionIdRef.current;
    const lockToken = lockTokenRef.current;
    if (!voiceSessionId || !lockToken || turns.length === 0) return;

    try {
      const result = await relayTurns(voiceSessionId, lockToken, turns);
      if (result.accepted > 0) {
        setTurnCount((prev) => prev + result.accepted);
      }
      console.log("[realtime] turns relayed", result);
    } catch (err) {
      console.error("[realtime] turn relay failed", err);
    }
  }, []);

  const endSession = useCallback(async () => {
    const voiceSessionId = voiceSessionIdRef.current;
    const lockToken = lockTokenRef.current;
    if (!voiceSessionId || !lockToken) return;

    try {
      const result = await endVoiceSession(voiceSessionId, lockToken);
      console.log("[realtime] session ended", result);
    } catch (err) {
      console.error("[realtime] end session failed", err);
    } finally {
      clearStoredVoiceSession(voiceSessionId, handoffToken);
      voiceSessionIdRef.current = "";
      lockTokenRef.current = "";
    }
  }, [handoffToken]);

  const disconnect = useCallback(() => {
    stopHeartbeat();
    void endSession();

    if (pcRef.current) {
      pcRef.current.getSenders().forEach((sender) => sender.track?.stop());
      pcRef.current.close();
      pcRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
    lastUserTranscriptRef.current = "";
    setStreamReady(false);
    setStatus("");
    setError("");
  }, [endSession, stopHeartbeat]);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    heartbeatRef.current = setInterval(() => {
      const voiceSessionId = voiceSessionIdRef.current;
      const lockToken = lockTokenRef.current;
      if (!voiceSessionId || !lockToken) return;
      void sendHeartbeat(voiceSessionId, lockToken).catch((err) => {
        console.error("[realtime] heartbeat failed", err);
      });
    }, HEARTBEAT_INTERVAL_MS);
  }, [stopHeartbeat]);

  const connect = useCallback(async (audioElement: HTMLAudioElement | null) => {
    if (!handoffToken) {
      setError("Link de voz inválido");
      setStatus("error");
      return;
    }
    if (status === "connecting" || status === "connected") return;

    setStatus("connecting");
    setError("");
    setStreamReady(false);

    try {
      const reconnectFromSessionId = getStoredReconnectSessionId(handoffToken);
      const tokenData: RealtimeTokenResponse = await fetchRealtimeToken(
        handoffToken,
        reconnectFromSessionId,
      );
      const ephemeralToken = tokenData.ephemeral_token;

      voiceSessionIdRef.current = tokenData.voice_session_id;
      lockTokenRef.current = tokenData.lock_token;
      setStoredVoiceSession(tokenData.voice_session_id, tokenData.lock_token, handoffToken);
      startHeartbeat();

      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      pc.ontrack = (event) => {
        if (audioElement && audioElement.srcObject !== event.streams[0]) {
          audioElement.srcObject = event.streams[0];
          audioElement.autoplay = true;
          void audioElement.play().catch(() => {
            /* autoplay policy — user gesture already happened on connect */
          });
          setStreamReady(true);
        }
      };

      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      micStreamRef.current = micStream;
      pc.addTrack(micStream.getTracks()[0]);

      const voiceSessionId = tokenData.voice_session_id;
      const dc = pc.createDataChannel("oai-events");
      dc.onopen = () => {
        if (!tokenData.play_session_opener) return;
        try {
          dc.send(JSON.stringify({ type: "response.create" }));
          console.log("[realtime] session_opener response.create");
        } catch {
          /* ignore */
        }
      };

      dc.onmessage = (event) => {
        void (async () => {
          try {
            const payload = JSON.parse(event.data as string) as {
              type?: string;
              transcript?: string;
              response?: unknown;
            };
            const type = payload.type;

            if (type === "conversation.item.input_audio_transcription.completed") {
              const transcript = (payload.transcript ?? "").trim();
              lastUserTranscriptRef.current = transcript;
              console.log("[realtime] student transcript:", transcript);
              return;
            }

            if (type === "response.done") {
              const output = normalizeRealtimeResponseOutput(
                payload.response as { output?: unknown },
              );
              const assistantText = extractAssistantText(output);
              const userTranscript = lastUserTranscriptRef.current;
              lastUserTranscriptRef.current = "";

              const itemId = responseId(payload.response);
              const turns: TurnRelayItem[] = [];

              if (userTranscript) {
                sequenceRef.current += 1;
                turns.push({
                  idempotency_key: `${voiceSessionId}:${itemId}:student`,
                  author: "student",
                  content: userTranscript,
                  realtime_item_id: `${itemId}:student`,
                  sequence: sequenceRef.current,
                });
              }
              if (assistantText) {
                sequenceRef.current += 1;
                turns.push({
                  idempotency_key: `${voiceSessionId}:${itemId}:agent`,
                  author: "agent",
                  content: assistantText,
                  realtime_item_id: itemId,
                  sequence: sequenceRef.current,
                });
              }

              console.log("[realtime] response.done", payload.response);
              if (userTranscript) {
                console.log("[realtime] turn student:", userTranscript);
              }
              if (assistantText) {
                console.log("[realtime] turn agent:", assistantText);
              }

              await persistTurns(turns);
            }
          } catch (err) {
            console.error("[realtime] datachannel parse error", err);
          }
        })();
      };

      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      const sdpRes = await fetch(REALTIME_CALLS_URL, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${ephemeralToken}`,
          "Content-Type": "application/sdp",
        },
        body: offer.sdp,
      });

      if (!sdpRes.ok) {
        const errText = await sdpRes.text();
        throw new Error(sdpRes.status === 401 ? "Token inválido ou expirado" : errText || sdpRes.statusText);
      }

      const answerSdp = await sdpRes.text();
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });
      setStatus("connected");
    } catch (err) {
      stopHeartbeat();
      if (voiceSessionIdRef.current && lockTokenRef.current) {
        void endSession();
      }
      voiceSessionIdRef.current = "";
      lockTokenRef.current = "";
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
      if (micStreamRef.current) {
        micStreamRef.current.getTracks().forEach((track) => track.stop());
        micStreamRef.current = null;
      }
      const message = err instanceof Error ? err.message : "Erro ao conectar Realtime";
      setError(message);
      setStatus("error");
    }
  }, [endSession, handoffToken, persistTurns, startHeartbeat, status, stopHeartbeat]);

  useEffect(() => () => {
    stopHeartbeat();
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
    void endSession();
  }, [endSession, stopHeartbeat]);

  return {
    status,
    error,
    streamReady,
    turnCount,
    connect,
    disconnect,
  };
}
