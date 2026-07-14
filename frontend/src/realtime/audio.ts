export function configureRemoteAudio(audioElement: HTMLAudioElement, stream: MediaStream) {
  audioElement.srcObject = stream;
  audioElement.autoplay = true;
  audioElement.setAttribute("playsinline", "true");
  void audioElement.play().catch(() => {
    /* autoplay policy — user gesture already happened on connect */
  });
}
