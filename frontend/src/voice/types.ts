export type RealtimeVoiceStatus = "" | "connecting" | "connected" | "ended" | "error";

export interface VoiceSessionCredentials {
  ephemeral_token: string;
  voice_session_id: string;
  lock_token: string;
  play_session_opener: boolean;
}

export interface VoiceTurnPayload {
  idempotency_key: string;
  author: "student" | "agent";
  content: string;
  realtime_item_id: string;
  sequence: number;
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
