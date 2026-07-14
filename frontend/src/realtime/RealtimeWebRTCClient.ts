import { configureRemoteAudio } from "./audio";
import {
  collectFunctionCallsFromOutput,
  extractAssistantText,
  normalizeRealtimeResponseOutput,
  parseFunctionCallArgs,
  responseId,
} from "./responseParsing";
import { REALTIME_MIC_CONSTRAINTS } from "../lib/realtimeMic";
import type { VoiceBackend, VoiceTurnPayload } from "../voice/types";

const REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";
const GRACEFUL_END_FALLBACK_MS = 5_000;

export interface RealtimeWebRTCCallbacks {
  onStreamReady: () => void;
  onConnected: () => void;
  onTurnsAccepted: (count: number) => void;
  onGracefulEnd: () => void;
  onStreamCleared: () => void;
}

/** WebRTC transport for OpenAI Realtime voice (data channel + remote audio track). */
export class RealtimeWebRTCClient {
  private pc: RTCPeerConnection | null = null;
  private dc: RTCDataChannel | null = null;
  private micStream: MediaStream | null = null;
  private sequence = 0;
  private voiceSessionId = "";
  private relayedStudentKeys = new Set<string>();
  private pendingGracefulEnd = false;
  private gracefulEndTimer: ReturnType<typeof setTimeout> | null = null;

  private backend: VoiceBackend | null = null;
  private callbacks: RealtimeWebRTCCallbacks | null = null;

  get isConnected(): boolean {
    return this.pc !== null;
  }

  async connect(
    audioElement: HTMLAudioElement | null,
    backend: VoiceBackend,
    callbacks: RealtimeWebRTCCallbacks,
    tokenData: Awaited<ReturnType<VoiceBackend["fetchSession"]>>,
  ): Promise<void> {
    this.backend = backend;
    this.callbacks = callbacks;
    this.voiceSessionId = tokenData.voice_session_id;
    this.relayedStudentKeys.clear();
    this.clearGracefulEndTimer();
    this.pendingGracefulEnd = false;

    const pc = new RTCPeerConnection();
    this.pc = pc;

    pc.ontrack = (event) => {
      if (audioElement && event.streams[0]) {
        configureRemoteAudio(audioElement, event.streams[0]);
        this.callbacks?.onStreamReady();
      }
    };

    const micStream = await navigator.mediaDevices.getUserMedia({
      audio: REALTIME_MIC_CONSTRAINTS,
    });
    this.micStream = micStream;
    pc.addTrack(micStream.getTracks()[0]);

    const dc = pc.createDataChannel("oai-events");
    this.dc = dc;
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
      void this.handleDataChannelMessage(event);
    };

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    const sdpRes = await fetch(REALTIME_CALLS_URL, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${tokenData.ephemeral_token}`,
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
    this.callbacks?.onConnected();
  }

  disconnect(): void {
    this.clearGracefulEndTimer();
    this.pendingGracefulEnd = false;
    if (this.pc) {
      this.pc.getSenders().forEach((sender) => sender.track?.stop());
      this.pc.close();
      this.pc = null;
    }
    if (this.micStream) {
      this.micStream.getTracks().forEach((track) => track.stop());
      this.micStream = null;
    }
    this.dc = null;
    this.relayedStudentKeys.clear();
    this.callbacks?.onStreamCleared();
    this.backend = null;
    this.callbacks = null;
  }

  private clearGracefulEndTimer(): void {
    if (this.gracefulEndTimer) {
      clearTimeout(this.gracefulEndTimer);
      this.gracefulEndTimer = null;
    }
  }

  private scheduleGracefulEndFallback(): void {
    this.clearGracefulEndTimer();
    this.gracefulEndTimer = setTimeout(() => {
      this.gracefulEndTimer = null;
      this.completeGracefulEnd("fallback");
    }, GRACEFUL_END_FALLBACK_MS);
  }

  private completeGracefulEnd(source: string): void {
    if (!this.pendingGracefulEnd) return;
    this.clearGracefulEndTimer();
    this.pendingGracefulEnd = false;
    console.log("[realtime] graceful end", source);
    this.callbacks?.onGracefulEnd();
  }

  private async persistTurns(turns: VoiceTurnPayload[]): Promise<void> {
    if (!this.backend || turns.length === 0) return;
    try {
      const result = await this.backend.persistTurns(turns);
      if (result.accepted > 0) {
        this.callbacks?.onTurnsAccepted(result.accepted);
      }
    } catch (err) {
      console.error("[realtime] turn relay failed", err);
    }
  }

  private async handleServerToolRoundtrip(
    dc: RTCDataChannel,
    functionCalls: Array<{ name: string; call_id: string; arguments: string }>,
  ): Promise<void> {
    if (!this.backend) return;
    const serverCalls = functionCalls.filter((call) => this.backend!.serverTools.has(call.name));
    if (serverCalls.length === 0) return;

    for (const call of serverCalls) {
      try {
        const result = await this.backend.handleToolCall(
          call.name,
          call.call_id,
          parseFunctionCallArgs(call),
        );
        if (!result) continue;
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
      } catch (err) {
        console.error("[realtime] tool bridge failed", call.name, err);
      }
    }

    try {
      dc.send(JSON.stringify({ type: "response.create" }));
    } catch {
      /* ignore */
    }
  }

  private async handleDataChannelMessage(event: MessageEvent): Promise<void> {
    const dc = this.dc;
    const backend = this.backend;
    if (!dc || !backend) return;

    try {
      const payload = JSON.parse(event.data as string) as {
        type?: string;
        transcript?: string;
        response?: unknown;
        item_id?: string;
      };
      const type = payload.type;

      if (type === "output_audio_buffer.stopped") {
        this.completeGracefulEnd("output_audio_buffer.stopped");
        return;
      }

      if (type === "conversation.item.input_audio_transcription.completed") {
        const transcript = (payload.transcript ?? "").trim();
        if (!transcript) return;

        const itemId = payload.item_id || `student-${Date.now()}`;
        const idempotencyKey = `${this.voiceSessionId}:${itemId}:student`;
        if (this.relayedStudentKeys.has(idempotencyKey)) return;
        this.relayedStudentKeys.add(idempotencyKey);

        console.log("[realtime] student transcript:", transcript);
        this.sequence += 1;
        await this.persistTurns([
          {
            idempotency_key: idempotencyKey,
            author: "student",
            content: transcript,
            realtime_item_id: `${itemId}:student`,
            sequence: this.sequence,
          },
        ]);
        return;
      }

      if (type === "response.done") {
        const doneResponseId = responseId(payload.response);
        const output = normalizeRealtimeResponseOutput(payload.response as { output?: unknown });
        const assistantText = extractAssistantText(output);
        const functionCalls = collectFunctionCallsFromOutput(output);
        const shouldEndConversation = functionCalls.some((call) => call.name === "end_conversation");

        const turns: VoiceTurnPayload[] = [];

        if (assistantText) {
          this.sequence += 1;
          turns.push({
            idempotency_key: `${this.voiceSessionId}:${doneResponseId}:agent`,
            author: "agent",
            content: assistantText,
            realtime_item_id: doneResponseId,
            sequence: this.sequence,
          });
        }

        console.log("[realtime] response.done", payload.response);
        if (assistantText) {
          console.log("[realtime] turn agent:", assistantText);
        }

        await this.persistTurns(turns);

        if (shouldEndConversation) {
          this.pendingGracefulEnd = true;
          this.scheduleGracefulEndFallback();
          return;
        }

        if (functionCalls.some((call) => backend.serverTools.has(call.name))) {
          await this.handleServerToolRoundtrip(dc, functionCalls);
        }
      }
    } catch (err) {
      console.error("[realtime] datachannel parse error", err);
    }
  }
}
