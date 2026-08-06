import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

interface Props {
  label?: string;
  rows?: number;
}

/** Inline skeleton for playground side panels (context, scores, chat history). */
export function PlaygroundPanelSkeleton({
  label = "Carregando…",
  rows = 4,
}: Props) {
  return (
    <SkeletonStatus label={label} className="playground-panel-skeleton">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index} className="playground-panel-skeleton__row">
          <Skeleton variant="text" width={`${55 + (index % 3) * 12}%`} height={14} />
          <Skeleton variant="rect" width="100%" height={index === 0 ? 64 : 40} />
        </div>
      ))}
    </SkeletonStatus>
  );
}
