import {
  endVoiceSession,
  fetchRealtimeToken,
  invokeRealtimeTool,
  relayTurns,
  sendHeartbeat,
} from "../lib/realtimeApi";
import {
  clearStoredVoiceSession,
  getStoredReconnectSessionId,
  setStoredVoiceSession,
} from "../lib/sessionRealtimeLock";
import type { VoiceBackend, VoiceSessionCredentials, VoiceTurnPayload } from "./types";

const SERVER_TOOLS = new Set(["score_understanding", "escalate_scope", "request_session_link"]);

export function createCertaiVoiceBackend(handoffToken: string): VoiceBackend {
  let voiceSessionId = "";
  let lockToken = "";

  return {
    serverTools: SERVER_TOOLS,

    getReconnectSessionId() {
      return getStoredReconnectSessionId(handoffToken);
    },

    async fetchSession() {
      const tokenData = await fetchRealtimeToken(
        handoffToken,
        getStoredReconnectSessionId(handoffToken),
      );
      voiceSessionId = tokenData.voice_session_id;
      lockToken = tokenData.lock_token;
      setStoredVoiceSession(voiceSessionId, lockToken, handoffToken);
      return tokenData as VoiceSessionCredentials;
    },

    async persistTurns(turns: VoiceTurnPayload[]) {
      if (!voiceSessionId || !lockToken || turns.length === 0) {
        return { accepted: 0 };
      }
      const result = await relayTurns(voiceSessionId, lockToken, turns);
      console.log("[realtime] turns relayed", result);
      return { accepted: result.accepted };
    },

    async handleToolCall(name, callId, args) {
      if (!SERVER_TOOLS.has(name) || !voiceSessionId || !lockToken) {
        return null;
      }
      const result = await invokeRealtimeTool(name, voiceSessionId, lockToken, callId, args);
      console.log("[realtime] tool bridge", name, result.output);
      return result;
    },

    async sendHeartbeat() {
      if (!voiceSessionId || !lockToken) return;
      await sendHeartbeat(voiceSessionId, lockToken);
    },

    async endSession() {
      if (!voiceSessionId || !lockToken) return;
      try {
        const result = await endVoiceSession(voiceSessionId, lockToken);
        console.log("[realtime] session ended", result);
      } catch (err) {
        console.error("[realtime] end session failed", err);
      } finally {
        clearStoredVoiceSession(voiceSessionId, handoffToken);
        voiceSessionId = "";
        lockToken = "";
      }
    },

    hasActiveSession() {
      return Boolean(voiceSessionId && lockToken);
    },

    clearSession() {
      voiceSessionId = "";
      lockToken = "";
    },
  };
}
