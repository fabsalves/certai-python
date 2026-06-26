import { useCallback, useEffect, useRef, useState } from "react";

export type RecorderStatus = "idle" | "recording" | "recorded";

interface UseAudioRecorderResult {
  status: RecorderStatus;
  seconds: number;
  blob: Blob | null;
  error: string;
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
}

export function useAudioRecorder(): UseAudioRecorderResult {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [seconds, setSeconds] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [error, setError] = useState("");

  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const reset = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
    recorderRef.current = null;
    chunksRef.current = [];
    cleanupStream();
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setStatus("idle");
    setSeconds(0);
    setBlob(null);
    setError("");
  }, [cleanupStream]);

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
        cleanupStream();
        if (timerRef.current) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        const recorded = new Blob(chunksRef.current, { type: mimeType });
        setBlob(recorded.size > 0 ? recorded : null);
        setStatus(recorded.size > 0 ? "recorded" : "idle");
      };

      recorder.start();
      setStatus("recording");
      timerRef.current = window.setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      cleanupStream();
      setError("Não foi possível acessar o microfone.");
      setStatus("idle");
    }
  }, [cleanupStream]);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }, []);

  return { status, seconds, blob, error, start, stop, reset };
}

function pad(n: number) {
  return String(n).padStart(2, "0");
}

export function formatDuration(totalSeconds: number) {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${pad(m)}:${pad(s)}`;
}
