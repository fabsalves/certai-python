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
  realtime_transcription_model: string;
  play_session_opener: boolean;
}

export interface TurnRelayItem {
  idempotency_key: string;
  author: "student" | "agent";
  content: string;
  realtime_item_id: string;
  sequence: number;
}

export interface UsageRelayItem {
  provider: "openai";
  model: string;
  operation: "realtime_response" | "input_transcription";
  provider_event_id: string;
  usage: Record<string, unknown>;
  occurred_at: string;
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
): Promise<RealtimeTokenResponse> {
  const { data } = await realtimeHttp.post<RealtimeTokenResponse>("/token", {
    handoff_token: handoffToken,
    reconnect_from_session_id: reconnectFromSessionId ?? null,
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

/**
 * Relays billable usage. On teardown `keepalive` is required: axios rides on
 * XHR, which the browser cancels while unloading, so the last batch — the one
 * closing the most expensive turn — would be lost.
 */
export async function relayUsage(
  voiceSessionId: string,
  lockToken: string,
  items: UsageRelayItem[],
  keepalive = false,
): Promise<{ inserted: number }> {
  const body = {
    voice_session_id: voiceSessionId,
    lock_token: lockToken,
    items,
  };

  if (keepalive) {
    const response = await fetch("/api/v1/realtime/usage", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
    });
    if (!response.ok) throw new Error(`usage relay failed: ${response.status}`);
    return (await response.json()) as { inserted: number };
  }

  const { data } = await realtimeHttp.post<{ inserted: number }>("/usage", body);
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
