const STORAGE_PREFIX = "certai-realtime-voice-";

function sessionKey(voiceSessionId: string) {
  return `${STORAGE_PREFIX}session-${voiceSessionId}`;
}

function reconnectKey(handoffToken: string) {
  return `${STORAGE_PREFIX}reconnect-${handoffToken.slice(-16)}`;
}

export function getStoredLockToken(voiceSessionId: string): string | null {
  if (!voiceSessionId) return null;
  try {
    return sessionStorage.getItem(sessionKey(voiceSessionId));
  } catch {
    return null;
  }
}

export function setStoredVoiceSession(
  voiceSessionId: string,
  lockToken: string,
  handoffToken: string,
) {
  if (!voiceSessionId || !lockToken) return;
  try {
    sessionStorage.setItem(sessionKey(voiceSessionId), lockToken);
    sessionStorage.setItem(reconnectKey(handoffToken), voiceSessionId);
  } catch {
    /* ignore */
  }
}

export function getStoredReconnectSessionId(handoffToken: string): string | null {
  if (!handoffToken) return null;
  try {
    return sessionStorage.getItem(reconnectKey(handoffToken));
  } catch {
    return null;
  }
}

export function clearStoredVoiceSession(voiceSessionId: string, handoffToken: string) {
  if (!voiceSessionId) return;
  try {
    sessionStorage.removeItem(sessionKey(voiceSessionId));
    if (handoffToken) {
      sessionStorage.removeItem(reconnectKey(handoffToken));
    }
  } catch {
    /* ignore */
  }
}
