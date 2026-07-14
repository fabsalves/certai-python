import { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import {
  endVoiceSession,
  fetchRealtimeToken,
  invokeRealtimeTool,
  relayTurns,
  sendHeartbeat,
  type RealtimeTokenResponse,
  type TurnRelayItem,
} from "../lib/realtimeApi";
import {
  isRealtimeVoiceSupported,
  isRealtimeMobileDevice,
  micPermissionErrorMessage,
} from "../lib/realtimeSupport";
import {
  hasRelayableTranscriptContent,
  logMicTrackDiagnostics,
  REALTIME_MIC_CONSTRAINTS,
  setMicInputEnabled,
} from "../lib/realtimeMic";
import { AssistantPlaybackGate } from "../lib/realtimePlayback";
import {
  clearStoredVoiceSession,
  getStoredReconnectSessionId,
  setStoredVoiceSession,
} from "../lib/sessionRealtimeLock";
import { apiErrorMessage } from "../lib/api";

const REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";
const HEARTBEAT_INTERVAL_MS = 30_000;
const SERVER_TOOLS = new Set(["score_understanding", "escalate_scope"]);

export type RealtimeVoiceStatus = "" | "connecting" | "connected" | "ended" | "error";

function parseFunctionCallArgs(call: { arguments?: unknown }): Record<string, unknown> {
  try {
    const raw = call.arguments;
    return typeof raw === "string" ? JSON.parse(raw || "{}") : (raw as Record<string, unknown>) || {};
  } catch {
    return {};
  }
}

function pushNormalizedFunctionCall(
  out: Array<{ name: string; call_id: string; arguments: string }>,
  raw: Record<string, unknown>,
) {
  const name = (raw.name || (raw.function as { name?: string } | undefined)?.name) as string | undefined;
  if (!name) return;
  const call_id = String(raw.call_id || raw.id || "");
  const args = raw.arguments ?? (raw.function as { arguments?: unknown } | undefined)?.arguments ?? "{}";
  out.push({
    name,
    call_id,
    arguments: typeof args === "string" ? args : JSON.stringify(args),
  });
}

function collectFunctionCallsFromOutput(output: unknown[]): Array<{
  name: string;
  call_id: string;
  arguments: string;
}> {
  const out: Array<{ name: string; call_id: string; arguments: string }> = [];
  for (const item of output) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;

    if (row.type === "function" && row.function) {
      pushNormalizedFunctionCall(out, row);
      continue;
    }
    if (row.type === "function_call") {
      pushNormalizedFunctionCall(out, row);
      continue;
    }
    if (row.type === "message" && Array.isArray(row.content)) {
      for (const part of row.content) {
        if (part && typeof part === "object" && (part as { type?: string }).type === "function_call") {
          pushNormalizedFunctionCall(out, part as Record<string, unknown>);
        }
      }
    }
    if (row.type === "message" && Array.isArray(row.tool_calls)) {
      for (const tc of row.tool_calls) {
        pushNormalizedFunctionCall(out, tc as Record<string, unknown>);
      }
    }
  }
  return out;
}

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

function configureRemoteAudio(audioElement: HTMLAudioElement, stream: MediaStream) {
  audioElement.srcObject = stream;
  audioElement.autoplay = true;
  audioElement.setAttribute("playsinline", "true");
  void audioElement.play().catch(() => {
    /* autoplay policy — user gesture already happened on connect */
  });
}

export function useRealtimeVoice(handoffToken: string) {
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const sequenceRef = useRef(0);
  const voiceSessionIdRef = useRef("");
  const lockTokenRef = useRef("");
  const assistantSpeakingRef = useRef(false);
  const muteWhileSpeakingRef = useRef(false);
  const relayedStudentKeysRef = useRef(new Set<string>());
  const pendingGracefulEndRef = useRef(false);
  const playbackGateRef = useRef<AssistantPlaybackGate | null>(null);

  const setAssistantSpeaking = useCallback((speaking: boolean) => {
    assistantSpeakingRef.current = speaking;
    if (muteWhileSpeakingRef.current) {
      setMicInputEnabled(micStreamRef.current, !speaking);
    }
  }, []);

  const teardownMedia = useCallback(() => {
    if (pcRef.current) {
      pcRef.current.getSenders().forEach((sender) => sender.track?.stop());
      pcRef.current.close();
      pcRef.current = null;
    }
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
    }
    playbackGateRef.current?.cancel();
    playbackGateRef.current = null;
    dcRef.current = null;
    relayedStudentKeysRef.current.clear();
    assistantSpeakingRef.current = false;
    pendingGracefulEndRef.current = false;
    setStreamReady(false);
  }, []);

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

  const handleServerToolRoundtrip = useCallback(
    async (
      dc: RTCDataChannel,
      functionCalls: Array<{ name: string; call_id: string; arguments: string }>,
    ) => {
      const voiceSessionId = voiceSessionIdRef.current;
      const lockToken = lockTokenRef.current;
      const serverCalls = functionCalls.filter((call) => SERVER_TOOLS.has(call.name));
      if (!voiceSessionId || !lockToken || serverCalls.length === 0) return;

      for (const call of serverCalls) {
        try {
          const result = await invokeRealtimeTool(
            call.name,
            voiceSessionId,
            lockToken,
            call.call_id,
            parseFunctionCallArgs(call),
          );
          dc.send(
            JSON.stringify({
              type: "conversation.item.create",
              item: {
                type: "function_call_output",
                call_id: result.call_id,
                output: result.output,
              },
            }),
          );
          console.log("[realtime] tool bridge", call.name, result.output);
        } catch (err) {
          console.error("[realtime] tool bridge failed", call.name, err);
        }
      }

      try {
        dc.send(JSON.stringify({ type: "response.create" }));
      } catch {
        /* ignore */
      }
    },
    [],
  );

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

  const finishCall = useCallback(
    async (options?: { skipEndApi?: boolean }) => {
      stopHeartbeat();
      if (!options?.skipEndApi) {
        await endSession();
      }
      teardownMedia();
      setError("");
      setStatus("ended");
    },
    [endSession, stopHeartbeat, teardownMedia],
  );

  const handleAssistantPlaybackEnded = useCallback(() => {
    setAssistantSpeaking(false);
    if (pendingGracefulEndRef.current) {
      pendingGracefulEndRef.current = false;
      void finishCall();
    }
  }, [finishCall, setAssistantSpeaking]);

  const disconnect = useCallback(() => {
    void finishCall();
  }, [finishCall]);

  const pingHeartbeat = useCallback(() => {
    const voiceSessionId = voiceSessionIdRef.current;
    const lockToken = lockTokenRef.current;
    if (!voiceSessionId || !lockToken) return;
    void sendHeartbeat(voiceSessionId, lockToken).catch((err) => {
      console.error("[realtime] heartbeat failed", err);
    });
  }, []);

  const startHeartbeat = useCallback(() => {
    stopHeartbeat();
    pingHeartbeat();
    heartbeatRef.current = setInterval(pingHeartbeat, HEARTBEAT_INTERVAL_MS);
  }, [pingHeartbeat, stopHeartbeat]);

  const connect = useCallback(async (audioElement: HTMLAudioElement | null) => {
    if (!handoffToken) {
      setError("Link de voz inválido");
      setStatus("error");
      return;
    }
    if (!isRealtimeVoiceSupported()) {
      setError("Seu navegador não suporta chamada de voz ao vivo.");
      setStatus("error");
      return;
    }
    if (status === "connecting" || status === "connected") return;

    pendingGracefulEndRef.current = false;
    playbackGateRef.current?.cancel();
    playbackGateRef.current = new AssistantPlaybackGate(handleAssistantPlaybackEnded);

    setStatus("connecting");
    setError("");
    setStreamReady(false);

    try {
      const reconnectFromSessionId = getStoredReconnectSessionId(handoffToken);
      const deviceProfile = isRealtimeMobileDevice() ? "mobile" : "desktop";
      console.log("[realtime] device_profile:", deviceProfile);
      const tokenData: RealtimeTokenResponse = await fetchRealtimeToken(
        handoffToken,
        reconnectFromSessionId,
        deviceProfile,
      );
      const ephemeralToken = tokenData.ephemeral_token;

      voiceSessionIdRef.current = tokenData.voice_session_id;
      lockTokenRef.current = tokenData.lock_token;
      muteWhileSpeakingRef.current = tokenData.mute_while_speaking;
      relayedStudentKeysRef.current.clear();
      setStoredVoiceSession(tokenData.voice_session_id, tokenData.lock_token, handoffToken);
      startHeartbeat();

      const pc = new RTCPeerConnection();
      pcRef.current = pc;

      pc.ontrack = (event) => {
        if (audioElement && event.streams[0]) {
          configureRemoteAudio(audioElement, event.streams[0]);
          setStreamReady(true);
        }
      };

      const micStream = await navigator.mediaDevices.getUserMedia({
        audio: REALTIME_MIC_CONSTRAINTS,
      });
      micStreamRef.current = micStream;
      logMicTrackDiagnostics(micStream);
      pc.addTrack(micStream.getTracks()[0]);

      const voiceSessionId = tokenData.voice_session_id;
      const dc = pc.createDataChannel("oai-events");
      dcRef.current = dc;
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
              response_id?: string;
              item_id?: string;
            };
            const type = payload.type;
            const eventResponseId =
              typeof payload.response_id === "string"
                ? payload.response_id
                : responseId(payload.response as { id?: unknown } | undefined);

            if (type === "input_audio_buffer.speech_started") {
              const hadActiveResponse = assistantSpeakingRef.current;
              console.log("[realtime] speech_started", {
                at: new Date().toISOString(),
                hadActiveResponse,
                pendingGracefulEnd: pendingGracefulEndRef.current,
              });
              if (!pendingGracefulEndRef.current && hadActiveResponse) {
                try {
                  dc.send(JSON.stringify({ type: "output_audio_buffer.clear" }));
                } catch {
                  /* ignore */
                }
                playbackGateRef.current?.cancel();
                setAssistantSpeaking(false);
                console.log("[realtime] barge-in: output_audio_buffer.clear sent");
              }
              return;
            }

            if (type === "response.created") {
              playbackGateRef.current?.beginResponse(eventResponseId);
              setAssistantSpeaking(true);
              return;
            }

            if (type === "output_audio_buffer.started") {
              playbackGateRef.current?.markPlaybackStarted(eventResponseId);
              setAssistantSpeaking(true);
              return;
            }

            if (type === "output_audio_buffer.stopped") {
              playbackGateRef.current?.markPlaybackStopped(eventResponseId);
              return;
            }

            if (type === "response.cancelled") {
              playbackGateRef.current?.cancel();
              handleAssistantPlaybackEnded();
              return;
            }

            if (type === "conversation.item.input_audio_transcription.completed") {
              const transcript = (payload.transcript ?? "").trim();
              if (!hasRelayableTranscriptContent(transcript)) {
                console.log("[realtime] student transcript skipped (noise):", JSON.stringify(transcript));
                return;
              }

              const itemId = payload.item_id || `student-${Date.now()}`;
              const idempotencyKey = `${voiceSessionId}:${itemId}:student`;
              if (relayedStudentKeysRef.current.has(idempotencyKey)) return;
              relayedStudentKeysRef.current.add(idempotencyKey);

              console.log("[realtime] student transcript:", transcript);
              sequenceRef.current += 1;
              await persistTurns([
                {
                  idempotency_key: idempotencyKey,
                  author: "student",
                  content: transcript,
                  realtime_item_id: `${itemId}:student`,
                  sequence: sequenceRef.current,
                },
              ]);
              return;
            }

            if (type === "response.done") {
              const doneResponseId = responseId(payload.response);
              playbackGateRef.current?.beginResponse(doneResponseId);

              const output = normalizeRealtimeResponseOutput(
                payload.response as { output?: unknown },
              );
              const assistantText = extractAssistantText(output);
              const functionCalls = collectFunctionCallsFromOutput(output);
              const shouldEndConversation = functionCalls.some((call) => call.name === "end_conversation");

              const itemId = doneResponseId;
              const turns: TurnRelayItem[] = [];

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
              if (assistantText) {
                console.log("[realtime] turn agent:", assistantText);
              }

              await persistTurns(turns);

              if (shouldEndConversation) {
                pendingGracefulEndRef.current = true;
                playbackGateRef.current?.scheduleFallback(assistantText);
                return;
              }

              playbackGateRef.current?.scheduleFallback(assistantText);

              if (functionCalls.some((call) => SERVER_TOOLS.has(call.name))) {
                await handleServerToolRoundtrip(dc, functionCalls);
              }
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
      pingHeartbeat();
    } catch (err) {
      stopHeartbeat();
      playbackGateRef.current?.cancel();
      if (voiceSessionIdRef.current && lockTokenRef.current) {
        void endSession();
      }
      voiceSessionIdRef.current = "";
      lockTokenRef.current = "";
      teardownMedia();

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
  }, [
    endSession,
    finishCall,
    handoffToken,
    handleAssistantPlaybackEnded,
    handleServerToolRoundtrip,
    persistTurns,
    pingHeartbeat,
    setAssistantSpeaking,
    startHeartbeat,
    status,
    stopHeartbeat,
    teardownMedia,
  ]);

  useEffect(() => () => {
    stopHeartbeat();
    playbackGateRef.current?.cancel();
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
