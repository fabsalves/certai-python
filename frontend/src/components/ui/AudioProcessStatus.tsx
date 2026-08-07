/** Shared recording/processing strip used by lesson report and lesson content import. */

interface WaveformProps {
  levels?: number[];
  /** CSS-animated bars when there is no live mic input (transcribing / extracting). */
  processing?: boolean;
  barCount?: number;
}

export function AudioWaveform({
  levels,
  processing = false,
  barCount = 24,
}: WaveformProps) {
  const bars =
    levels ?? Array.from({ length: barCount }, (_, index) => 0.2 + (index % 5) * 0.12);

  return (
    <div
      className={`lesson-report__waveform${processing ? " lesson-report__waveform--processing" : ""}`}
      aria-hidden
    >
      {bars.map((level, index) => (
        <span
          key={index}
          className="lesson-report__wave-bar"
          style={
            processing
              ? { animationDelay: `${(index % 8) * 0.08}s` }
              : { transform: `scaleY(${Math.max(0.15, level)})` }
          }
        />
      ))}
    </div>
  );
}

interface ProcessStatusProps {
  label: string;
}

/** Processing state with the same visual language as live recording. */
export function AudioProcessStatus({ label }: ProcessStatusProps) {
  return (
    <div className="lesson-report__recording" aria-live="polite">
      <AudioWaveform processing />
      <span className="lesson-report__rec-label">
        <span className="lesson-report__pulse lesson-report__pulse--brand" aria-hidden />
        {label}
      </span>
    </div>
  );
}
