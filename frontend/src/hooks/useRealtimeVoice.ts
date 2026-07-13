import axios from "axios";
import { useCallback, useEffect, useRef, useState } from "react";

const REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";

export type RealtimeVoiceStatus = "" | "connecting" | "connected" | "error";

export interface RealtimeTokenResponse {
  ephemeral_token: string;
  expires_at: number;
  realtime_model: string;
  realtime_voice: string;
  play_session_opener: boolean;
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
      continue;
    }
    if (row.type === "message" && Array.isArray(row.content)) {
      for (const part of row.content) {
        if (!part || typeof part !== "object") continue;
        const p = part as Record<string, unknown>;
        if ((p.type === "output_text" || p.type === "text") && typeof p.text === "string") {
          parts.push(p.text);
        }
      }
    }
  }
  return parts.join("").trim();
}

async function fetchRealtimeToken(): Promise<RealtimeTokenResponse> {
  const { data } = await axios.post<RealtimeTokenResponse>("/api/v1/realtime/token");
  return data;
}

export function useRealtimeVoice() {
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const lastUserTranscriptRef = useRef("");

  const [status, setStatus] = useState<RealtimeVoiceStatus>("");
  const [error, setError] = useState("");
  const [streamReady, setStreamReady] = useState(false);

  const disconnect = useCallback(() => {
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
  }, []);

  const connect = useCallback(async (audioElement: HTMLAudioElement | null) => {
    if (status === "connecting" || status === "connected") return;

    setStatus("connecting");
    setError("");
    setStreamReady(false);

    try {
      const tokenData = await fetchRealtimeToken();
      const ephemeralToken = tokenData.ephemeral_token;

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
        try {
          const payload = JSON.parse(event.data as string) as { type?: string; transcript?: string; response?: unknown };
          const type = payload.type;

          if (type === "conversation.item.input_audio_transcription.completed") {
            const transcript = (payload.transcript ?? "").trim();
            lastUserTranscriptRef.current = transcript;
            console.log("[realtime] student transcript:", transcript);
            return;
          }

          if (type === "response.done") {
            const output = normalizeRealtimeResponseOutput(payload.response as { output?: unknown });
            const assistantText = extractAssistantText(output);
            const userTranscript = lastUserTranscriptRef.current;
            lastUserTranscriptRef.current = "";

            console.log("[realtime] response.done", payload.response);
            if (userTranscript) {
              console.log("[realtime] turn student:", userTranscript);
            }
            if (assistantText) {
              console.log("[realtime] turn agent:", assistantText);
            }
          }
        } catch (err) {
          console.error("[realtime] datachannel parse error", err);
        }
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
      disconnect();
      const message = err instanceof Error ? err.message : "Erro ao conectar Realtime";
      setError(message);
      setStatus("error");
    }
  }, [disconnect, status]);

  useEffect(() => () => disconnect(), [disconnect]);

  return {
    status,
    error,
    streamReady,
    connect,
    disconnect,
  };
}
