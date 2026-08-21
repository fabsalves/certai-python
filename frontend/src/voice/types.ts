export type RealtimeVoiceStatus = "" | "connecting" | "connected" | "ended" | "error";

export interface VoiceSessionCredentials {
  ephemeral_token: string;
  voice_session_id: string;
  lock_token: string;
  realtime_model: string;
  realtime_transcription_model: string;
  play_session_opener: boolean;
}

export interface VoiceTurnPayload {
  idempotency_key: string;
  author: "student" | "agent";
  content: string;
  realtime_item_id: string;
  sequence: number;
}

/** One provider event whose usage is billable. Raw payload; the backend maps it. */
export interface VoiceUsagePayload {
  provider: "openai";
  model: string;
  operation: "realtime_response" | "input_transcription";
  provider_event_id: string;
  usage: Record<string, unknown>;
  occurred_at: string;
}

export interface VoiceToolBridgeResult {
  call_id: string;
  output: string;
}

export interface VoiceTurnPersistResult {
  accepted: number;
}

export interface VoiceBackend {
  serverTools: ReadonlySet<string>;
  getReconnectSessionId(): string | null;
  fetchSession(): Promise<VoiceSessionCredentials>;
  persistTurns(turns: VoiceTurnPayload[]): Promise<VoiceTurnPersistResult>;
  /** `keepalive` lets the last batch survive the page unloading. */
  persistUsage(items: VoiceUsagePayload[], keepalive?: boolean): Promise<void>;
  handleToolCall(
    name: string,
    callId: string,
    args: Record<string, unknown>,
  ): Promise<VoiceToolBridgeResult | null>;
  sendHeartbeat(): Promise<void>;
  endSession(): Promise<void>;
  hasActiveSession(): boolean;
  clearSession(): void;
}
