import axios from "axios";

const realtimeHttp = axios.create({ baseURL: "/api/v1/realtime" });

export interface SessionValidateResponse {
  valid: boolean;
  student_first_name: string;
  lesson_title: string;
  track_title: string;
  assistant_name: string;
  expires_at: number;
  whatsapp_support_url: string;
}

export interface RealtimeTokenResponse {
  ephemeral_token: string;
  expires_at: number;
  voice_session_id: string;
  lock_token: string;
  realtime_model: string;
  realtime_voice: string;
  play_session_opener: boolean;
  mute_while_speaking: boolean;
}

export interface TurnRelayItem {
  idempotency_key: string;
  author: "student" | "agent";
  content: string;
  realtime_item_id: string;
  sequence: number;
}

export interface TurnsRelayResponse {
  accepted: number;
  duplicates: number;
  conversation_id: string;
}

export interface EndSessionResponse {
  ok: boolean;
  status: string;
  turn_count: number;
}

export interface ToolBridgeResponse {
  call_id: string;
  output: string;
}

export async function validateSession(handoffToken: string): Promise<SessionValidateResponse> {
  const { data } = await realtimeHttp.post<SessionValidateResponse>("/session/validate", {
    handoff_token: handoffToken,
  });
  return data;
}

export async function fetchRealtimeToken(
  handoffToken: string,
  reconnectFromSessionId?: string | null,
  deviceProfile: "mobile" | "desktop" = "desktop",
): Promise<RealtimeTokenResponse> {
  const { data } = await realtimeHttp.post<RealtimeTokenResponse>("/token", {
    handoff_token: handoffToken,
    reconnect_from_session_id: reconnectFromSessionId ?? null,
    device_profile: deviceProfile,
  });
  return data;
}

export async function relayTurns(
  voiceSessionId: string,
  lockToken: string,
  turns: TurnRelayItem[],
): Promise<TurnsRelayResponse> {
  const { data } = await realtimeHttp.post<TurnsRelayResponse>("/turns", {
    voice_session_id: voiceSessionId,
    lock_token: lockToken,
    turns,
  });
  return data;
}

export async function sendHeartbeat(
  voiceSessionId: string,
  lockToken: string,
): Promise<{ ok: boolean }> {
  const { data } = await realtimeHttp.post<{ ok: boolean }>("/heartbeat", {
    voice_session_id: voiceSessionId,
    lock_token: lockToken,
  });
  return data;
}

export async function endVoiceSession(
  voiceSessionId: string,
  lockToken: string,
  options?: { finalSequence?: number; reason?: string },
): Promise<EndSessionResponse> {
  const { data } = await realtimeHttp.post<EndSessionResponse>("/end", {
    voice_session_id: voiceSessionId,
    lock_token: lockToken,
    reason: options?.reason ?? "explicit",
    final_sequence: options?.finalSequence ?? null,
  });
  return data;
}

export async function invokeRealtimeTool(
  toolName: string,
  voiceSessionId: string,
  lockToken: string,
  callId: string,
  args: Record<string, unknown>,
): Promise<ToolBridgeResponse> {
  const { data } = await realtimeHttp.post<ToolBridgeResponse>(`/tools/${toolName}`, {
    voice_session_id: voiceSessionId,
    lock_token: lockToken,
    call_id: callId,
    arguments: args,
  });
  return data;
}
