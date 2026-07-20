import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderStatus = "idle" | "recording" | "recorded";

const WAVEFORM_BARS = 24;
const IDLE_LEVELS = () => Array.from({ length: WAVEFORM_BARS }, () => 0.08);

interface UseAudioRecorderResult {
  status: RecorderStatus;
  seconds: number;
  blob: Blob | null;
  levels: number[];
  error: string;
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
}

export function useAudioRecorder(): UseAudioRecorderResult {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [seconds, setSeconds] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [levels, setLevels] = useState<number[]>(IDLE_LEVELS);
  const [error, setError] = useState("");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const rafRef = useRef<number | null>(null);

  const stopAnalyser = useCallback(() => {
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    analyserRef.current = null;
    if (audioContextRef.current) {
      void audioContextRef.current.close().catch(() => undefined);
      audioContextRef.current = null;
    }
    setLevels(IDLE_LEVELS());
  }, []);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const startAnalyser = useCallback((stream: MediaStream) => {
    stopAnalyser();
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return;

      const ctx = new AudioCtx();
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.55;
      source.connect(analyser);
      audioContextRef.current = ctx;
      analyserRef.current = analyser;

      const data = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        const node = analyserRef.current;
        if (!node) return;
        node.getByteFrequencyData(data);
        const next: number[] = [];
        const step = Math.max(1, Math.floor(data.length / WAVEFORM_BARS));
        for (let i = 0; i < WAVEFORM_BARS; i += 1) {
          const sample = data[i * step] ?? 0;
          // Keep a visible floor so the bars still breathe when quiet.
          next.push(Math.min(1, 0.12 + (sample / 255) * 0.88));
        }
        setLevels(next);
        rafRef.current = requestAnimationFrame(tick);
      };
      rafRef.current = requestAnimationFrame(tick);
    } catch {
      // Waveform is decorative; recording continues without it.
    }
  }, [stopAnalyser]);

  const reset = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    chunksRef.current = [];
    stopAnalyser();
    cleanupStream();
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setStatus("idle");
    setSeconds(0);
    setBlob(null);
    setError("");
  }, [cleanupStream, stopAnalyser]);

  useEffect(() => () => reset(), [reset]);

  const start = useCallback(async () => {
    setError("");
    setBlob(null);
    setSeconds(0);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType });
      recorderRef.current = recorder;

      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      recorder.onstop = () => {
        stopAnalyser();
        cleanupStream();
        if (timerRef.current) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        const recorded = new Blob(chunksRef.current, { type: mimeType });
        setBlob(recorded.size > 0 ? recorded : null);
        setStatus(recorded.size > 0 ? "recorded" : "idle");
      };

      startAnalyser(stream);
      recorder.start();
      setStatus("recording");
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      stopAnalyser();
      cleanupStream();
      setError("Não foi possível acessar o microfone.");
      setStatus("idle");
    }
  }, [cleanupStream, startAnalyser, stopAnalyser]);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }, []);

  return { status, seconds, blob, levels, error, start, stop, reset };
}

function pad(n: number) {
  return String(n).padStart(2, "0");
}

export function formatDuration(totalSeconds: number) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${pad(m)}:${pad(s)}`;
}
