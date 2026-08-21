import { configureRemoteAudio } from "./audio";
import {
  collectFunctionCallsFromOutput,
  extractAssistantText,
  normalizeRealtimeResponseOutput,
  parseFunctionCallArgs,
  responseHasAudioOutput,
  responseId,
} from "./responseParsing";
import { REALTIME_MIC_CONSTRAINTS } from "../lib/realtimeMic";
import type { VoiceBackend, VoiceTurnPayload, VoiceUsagePayload } from "../voice/types";

const REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";
/**
 * Safety only if output_audio_buffer.stopped never arrives.
 * Primary path: ack end_conversation via function_call_output, then wait for stopped
 * (Realtime withholds stopped while a tool call is unanswered).
 */
const GRACEFUL_END_FALLBACK_MS = 20_000;
/** Usage lines are batched: a busy turn emits response.done + transcription together. */
const USAGE_FLUSH_DEBOUNCE_MS = 400;
/** Cap requeue on relay failure so an offline /usage cannot grow unbounded in memory. */
const USAGE_REQUEUE_MAX = 40;

export interface ResponseDoneInfo {
  hasAudioOutput: boolean;
}

export interface RealtimeWebRTCCallbacks {
  onStreamReady: () => void;
  onConnected: () => void;
  onTurnsAccepted: (count: number) => void;
  onGracefulEnd: () => void;
  onStreamCleared: () => void;
  onResponseStarted?: () => void;
  onResponseDone?: (info: ResponseDoneInfo) => void;
  onOutputAudioStopped?: () => void;
  onResponseInterrupted?: () => void;
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
  private usageQueue: VoiceUsagePayload[] = [];
  private usageFlushTimer: ReturnType<typeof setTimeout> | null = null;
  private relayedUsageKeys = new Set<string>();
  private sessionModel = "";
  private transcriptionModel = "";

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
    this.sessionModel = tokenData.realtime_model ?? "";
    this.transcriptionModel = tokenData.realtime_transcription_model ?? "";
    this.relayedStudentKeys.clear();
    this.relayedUsageKeys.clear();
    this.usageQueue = [];
    this.clearUsageFlushTimer();
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

  setMicMuted(muted: boolean): void {
    const track = this.micStream?.getAudioTracks()[0];
    if (track) track.enabled = !muted;
  }

  disconnect(): void {
    this.clearGracefulEndTimer();
    this.pendingGracefulEnd = false;
    // Fire-and-forget with keepalive: the last response.done closes the most
    // expensive turn of the call and must survive the page unloading.
    // Capture backend before nulling — flushUsage is async and would race.
    this.clearUsageFlushTimer();
    const backend = this.backend;
    void this.flushUsage(true, backend);
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
    this.relayedUsageKeys.clear();
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

  private clearUsageFlushTimer(): void {
    if (this.usageFlushTimer) {
      clearTimeout(this.usageFlushTimer);
      this.usageFlushTimer = null;
    }
  }

  /** Dedup by provider event: the same response.done may arrive twice. */
  private enqueueUsage(item: VoiceUsagePayload): void {
    const key = `${item.operation}:${item.provider_event_id}`;
    if (this.relayedUsageKeys.has(key)) return;
    this.relayedUsageKeys.add(key);

    this.usageQueue.push(item);
    if (this.usageFlushTimer) return;
    this.usageFlushTimer = setTimeout(() => {
      this.usageFlushTimer = null;
      void this.flushUsage();
    }, USAGE_FLUSH_DEBOUNCE_MS);
  }

  private async flushUsage(
    keepalive = false,
    backend: VoiceBackend | null = this.backend,
  ): Promise<void> {
    if (!backend || this.usageQueue.length === 0) return;
    const items = this.usageQueue.splice(0, this.usageQueue.length);
    try {
      await backend.persistUsage(items, keepalive);
    } catch (err) {
      // Metering must never break the call. Requeue for the next attempt, but
      // drop the dedup keys so the retry is not swallowed as a duplicate.
      console.warn("[realtime] usage relay failed", err);
      for (const item of items) {
        this.relayedUsageKeys.delete(`${item.operation}:${item.provider_event_id}`);
      }
      const room = Math.max(0, USAGE_REQUEUE_MAX - this.usageQueue.length);
      if (room > 0) {
        this.usageQueue.unshift(...items.slice(-room));
      }
    }
  }

  private ackFunctionCallOutputs(
    dc: RTCDataChannel,
    calls: Array<{ call_id: string }>,
    output: string,
  ): void {
    for (const call of calls) {
      if (!call.call_id) continue;
      try {
        dc.send(
          JSON.stringify({
            type: "conversation.item.create",
            item: {
              type: "function_call_output",
              call_id: call.call_id,
              output,
            },
          }),
        );
      } catch (err) {
        console.error("[realtime] function_call_output failed", call.call_id, err);
      }
    }
  }

  private async runServerTools(
    dc: RTCDataChannel,
    functionCalls: Array<{ name: string; call_id: string; arguments: string }>,
  ): Promise<boolean> {
    if (!this.backend) return false;
    const serverCalls = functionCalls.filter((call) => this.backend!.serverTools.has(call.name));
    if (serverCalls.length === 0) return false;

    for (const call of serverCalls) {
      try {
        const result = await this.backend.handleToolCall(
          call.name,
          call.call_id,
          parseFunctionCallArgs(call),
        );
        if (!result) continue;
        this.ackFunctionCallOutputs(dc, [{ call_id: result.call_id }], result.output);
      } catch (err) {
        console.error("[realtime] tool bridge failed", call.name, err);
      }
    }
    return true;
  }

  private beginGracefulEnd(
    dc: RTCDataChannel,
    endCalls: Array<{ name: string; call_id: string; arguments: string }>,
  ): void {
    // Realtime withholds output_audio_buffer.stopped while a tool call is unanswered.
    this.ackFunctionCallOutputs(dc, endCalls, "ended");
    console.log("[realtime] end_conversation acked; waiting for audio stopped");
    this.pendingGracefulEnd = true;
    this.scheduleGracefulEndFallback();
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
        event_id?: string;
        usage?: Record<string, unknown>;
      };
      const type = payload.type;

      if (type === "response.created") {
        this.callbacks?.onResponseStarted?.();
        return;
      }

      if (
        type === "response.cancel"
        || type === "response.cancelled"
        || type === "output_audio_buffer.cleared"
      ) {
        this.callbacks?.onResponseInterrupted?.();
        return;
      }

      if (type === "input_audio_buffer.speech_started") {
        this.callbacks?.onResponseInterrupted?.();
        return;
      }

      if (type === "output_audio_buffer.stopped") {
        this.callbacks?.onOutputAudioStopped?.();
        this.completeGracefulEnd("output_audio_buffer.stopped");
        return;
      }

      if (type === "conversation.item.input_audio_transcription.completed") {
        // Input transcription is billed on its own rate card, so its usage is
        // metered even when the transcript itself is empty and gets discarded.
        if (payload.usage) {
          this.enqueueUsage({
            provider: "openai",
            model: this.transcriptionModel,
            operation: "input_transcription",
            provider_event_id:
              payload.event_id ?? `transcription:${payload.item_id ?? crypto.randomUUID()}`,
            usage: payload.usage,
            occurred_at: new Date().toISOString(),
          });
        }

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
        const responseUsage = (payload.response as { usage?: Record<string, unknown> })
          ?.usage;
        if (responseUsage) {
          this.enqueueUsage({
            provider: "openai",
            model: this.sessionModel,
            operation: "realtime_response",
            provider_event_id: payload.event_id ?? `response:${doneResponseId}`,
            usage: responseUsage,
            occurred_at: new Date().toISOString(),
          });
        }
        const output = normalizeRealtimeResponseOutput(payload.response as { output?: unknown });
        this.callbacks?.onResponseDone?.({
          hasAudioOutput: responseHasAudioOutput(output),
        });
        const assistantText = extractAssistantText(output);
        const functionCalls = collectFunctionCallsFromOutput(output);

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

        // Server tools first (e.g. conclude_lesson), then client end_conversation.
        // Same hangup contract for pause and lesson close: ack end → wait stopped.
        const ranServerTools = await this.runServerTools(dc, functionCalls);
        const endCalls = functionCalls.filter((call) => call.name === "end_conversation");

        if (endCalls.length > 0) {
          this.beginGracefulEnd(dc, endCalls);
          return;
        }

        if (ranServerTools) {
          try {
            dc.send(JSON.stringify({ type: "response.create" }));
          } catch {
            /* ignore */
          }
        }
      }
    } catch (err) {
      console.error("[realtime] datachannel parse error", err);
    }
  }
}
