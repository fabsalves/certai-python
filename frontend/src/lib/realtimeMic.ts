/** True when transcript has letters or digits (not only punctuation/whitespace). */
export function hasRelayableTranscriptContent(transcript: string): boolean {
  const trimmed = transcript.trim();
  if (!trimmed) return false;
  return /[\p{L}\p{N}]/u.test(trimmed);
}

export const REALTIME_MIC_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: true,
  noiseSuppression: true,
  autoGainControl: true,
};

export function setMicInputEnabled(stream: MediaStream | null, enabled: boolean): void {
  stream?.getAudioTracks().forEach((track) => {
    track.enabled = enabled;
  });
}

export function logMicTrackDiagnostics(stream: MediaStream, label = "[realtime] mic"): void {
  const track = stream.getAudioTracks()[0];
  if (!track) {
    console.warn(`${label} no audio track on stream`);
    return;
  }

  console.log(`${label} constraints`, track.getConstraints());
  console.log(`${label} settings`, track.getSettings());
  if (typeof track.getCapabilities === "function") {
    console.log(`${label} capabilities`, track.getCapabilities());
  }
}
