import axios from "axios";

const realtimeHttp = axios.create({ baseURL: "/api/v1/realtime" });

export interface SessionValidateResponse {
  valid: boolean;
  student_first_name: string;
  lesson_title: string;
  track_title: string;
  assistant_name: string;
  expires_at: number;
}

export interface RealtimeTokenResponse {
  ephemeral_token: string;
  expires_at: number;
  realtime_model: string;
  realtime_voice: string;
  play_session_opener: boolean;
}

export async function validateSession(handoffToken: string): Promise<SessionValidateResponse> {
  const { data } = await realtimeHttp.post<SessionValidateResponse>("/session/validate", {
    handoff_token: handoffToken,
  });
  return data;
}

export async function fetchRealtimeToken(handoffToken: string): Promise<RealtimeTokenResponse> {
  const { data } = await realtimeHttp.post<RealtimeTokenResponse>("/token", {
    handoff_token: handoffToken,
  });
  return data;
}
