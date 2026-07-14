export function isRealtimeVoiceSupported(): boolean {
  if (typeof window === "undefined") return false;
  return (
    typeof RTCPeerConnection !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function"
  );
}

/** Coarse mobile profile for VAD tuning (speakerphone echo). */
export function isRealtimeMobileDevice(): boolean {
  if (typeof window === "undefined") return false;
  const ua = navigator.userAgent;
  if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua)) {
    return true;
  }
  const coarsePointer = window.matchMedia("(pointer: coarse)").matches;
  const narrowViewport = window.matchMedia("(max-width: 768px)").matches;
  return coarsePointer && narrowViewport;
}

export function realtimeUnsupportedReason(): string | null {
  if (isRealtimeVoiceSupported()) return null;
  return "Seu navegador não suporta chamada de voz ao vivo.";
}

export function micPermissionErrorMessage(err: unknown): string | null {
  if (!(err instanceof DOMException)) return null;
  if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
    return "Permissão de microfone negada. Ative o microfone nas configurações do navegador ou continue pelo WhatsApp.";
  }
  if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
    return "Nenhum microfone encontrado neste dispositivo.";
  }
  return null;
}
