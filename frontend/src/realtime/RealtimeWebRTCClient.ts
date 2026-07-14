import { configureRemoteAudio } from "./audio";
import {
  collectFunctionCallsFromOutput,
  extractAssistantText,
  normalizeRealtimeResponseOutput,
  parseFunctionCallArgs,
  responseId,
} from "./responseParsing";
import { AssistantPlaybackGate } from "../lib/realtimePlayback";
import {
  hasRelayableTranscriptContent,
  logMicTrackDiagnostics,
  REALTIME_MIC_CONSTRAINTS,
  setMicInputEnabled,
} from "../lib/realtimeMic";
import type { VoiceBackend, VoiceTurnPayload } from "../voice/types";

const REALTIME_CALLS_URL = "https://api.openai.com/v1/realtime/calls";

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
  private assistantSpeaking = false;
  private muteWhileSpeaking = false;
  private relayedStudentKeys = new Set<string>();
  private pendingGracefulEnd = false;
  private playbackGate: AssistantPlaybackGate | null = null;

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
    this.muteWhileSpeaking = tokenData.mute_while_speaking;
    this.relayedStudentKeys.clear();
    this.pendingGracefulEnd = false;
    this.playbackGate?.cancel();
    this.playbackGate = new AssistantPlaybackGate(() => this.handleAssistantPlaybackEnded());

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
    logMicTrackDiagnostics(micStream);
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
    if (this.pc) {
      this.pc.getSenders().forEach((sender) => sender.track?.stop());
      this.pc.close();
      this.pc = null;
    }
    if (this.micStream) {
      this.micStream.getTracks().forEach((track) => track.stop());
      this.micStream = null;
    }
    this.playbackGate?.cancel();
    this.playbackGate = null;
    this.dc = null;
    this.relayedStudentKeys.clear();
    this.assistantSpeaking = false;
    this.pendingGracefulEnd = false;
    this.callbacks?.onStreamCleared();
    this.backend = null;
    this.callbacks = null;
  }

  private setAssistantSpeaking(speaking: boolean): void {
    this.assistantSpeaking = speaking;
    if (this.muteWhileSpeaking) {
      setMicInputEnabled(this.micStream, !speaking);
    }
  }

  private handleAssistantPlaybackEnded(): void {
    this.setAssistantSpeaking(false);
    if (this.pendingGracefulEnd) {
      this.pendingGracefulEnd = false;
      this.callbacks?.onGracefulEnd();
    }
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
        response_id?: string;
        item_id?: string;
      };
      const type = payload.type;
      const eventResponseId =
        typeof payload.response_id === "string"
          ? payload.response_id
          : responseId(payload.response as { id?: unknown } | undefined);

      if (type === "input_audio_buffer.speech_started") {
        const hadActiveResponse = this.assistantSpeaking;
        console.log("[realtime] speech_started", {
          at: new Date().toISOString(),
          hadActiveResponse,
          pendingGracefulEnd: this.pendingGracefulEnd,
        });
        if (!this.pendingGracefulEnd && hadActiveResponse) {
          try {
            dc.send(JSON.stringify({ type: "output_audio_buffer.clear" }));
          } catch {
            /* ignore */
          }
          this.playbackGate?.cancel();
          this.setAssistantSpeaking(false);
          console.log("[realtime] barge-in: output_audio_buffer.clear sent");
        }
        return;
      }

      if (type === "response.created") {
        this.playbackGate?.beginResponse(eventResponseId);
        this.setAssistantSpeaking(true);
        return;
      }

      if (type === "output_audio_buffer.started") {
        this.playbackGate?.markPlaybackStarted(eventResponseId);
        this.setAssistantSpeaking(true);
        return;
      }

      if (type === "output_audio_buffer.stopped") {
        this.playbackGate?.markPlaybackStopped(eventResponseId);
        return;
      }

      if (type === "response.cancelled") {
        this.playbackGate?.cancel();
        this.handleAssistantPlaybackEnded();
        return;
      }

      if (type === "conversation.item.input_audio_transcription.completed") {
        const transcript = (payload.transcript ?? "").trim();
        if (!hasRelayableTranscriptContent(transcript)) {
          console.log("[realtime] student transcript skipped (noise):", JSON.stringify(transcript));
          return;
        }

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
        this.playbackGate?.beginResponse(doneResponseId);

        const output = normalizeRealtimeResponseOutput(payload.response as { output?: unknown });
        const assistantText = extractAssistantText(output);
        const functionCalls = collectFunctionCallsFromOutput(output);
        const shouldEndConversation = functionCalls.some((call) => call.name === "end_conversation");

        const itemId = doneResponseId;
        const turns: VoiceTurnPayload[] = [];

        if (assistantText) {
          this.sequence += 1;
          turns.push({
            idempotency_key: `${this.voiceSessionId}:${itemId}:agent`,
            author: "agent",
            content: assistantText,
            realtime_item_id: itemId,
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
          this.playbackGate?.scheduleFallback(assistantText);
          return;
        }

        this.playbackGate?.scheduleFallback(assistantText);

        if (functionCalls.some((call) => backend.serverTools.has(call.name))) {
          await this.handleServerToolRoundtrip(dc, functionCalls);
        }
      }
    } catch (err) {
      console.error("[realtime] datachannel parse error", err);
    }
  }
}
