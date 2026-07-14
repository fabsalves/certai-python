/** Estima duração de fala para fallback quando output_audio_buffer.stopped não chega. */
export function estimatePlaybackFallbackMs(assistantText: string): number {
  const chars = assistantText.trim().length;
  return Math.min(15_000, Math.max(1_500, 900 + chars * 55));
}

/**
 * Aguarda fim da reprodução remota (WebRTC).
 * Primário: output_audio_buffer.stopped no data channel.
 * Fallback: timeout proporcional ao texto da resposta.
 */
export class AssistantPlaybackGate {
  private fallbackTimer: ReturnType<typeof setTimeout> | null = null;
  private activeResponseId: string | null = null;
  private completed = false;

  constructor(private readonly onPlaybackEnded: () => void) {}

  beginResponse(responseId: string | null) {
    this.activeResponseId = responseId;
    this.completed = false;
    this.clearFallback();
  }

  markPlaybackStarted(responseId?: string | null) {
    if (responseId) this.activeResponseId = responseId;
  }

  markPlaybackStopped(responseId?: string | null) {
    if (!this.matchesResponse(responseId)) return;
    this.finish("output_audio_buffer.stopped");
  }

  scheduleFallback(assistantText: string) {
    this.clearFallback();
    const ms = estimatePlaybackFallbackMs(assistantText);
    this.fallbackTimer = setTimeout(() => {
      this.fallbackTimer = null;
      console.log("[realtime] playback fallback", { ms, responseId: this.activeResponseId });
      this.finish("fallback");
    }, ms);
  }

  cancel() {
    this.clearFallback();
    this.activeResponseId = null;
    this.completed = false;
  }

  private matchesResponse(responseId?: string | null): boolean {
    if (!this.activeResponseId) return true;
    if (!responseId) return true;
    return this.activeResponseId === responseId;
  }

  private finish(source: string) {
    if (this.completed) return;
    this.completed = true;
    this.clearFallback();
    this.activeResponseId = null;
    console.log("[realtime] assistant playback ended", source);
    this.onPlaybackEnded();
  }

  private clearFallback() {
    if (this.fallbackTimer) {
      clearTimeout(this.fallbackTimer);
      this.fallbackTimer = null;
    }
  }
}
