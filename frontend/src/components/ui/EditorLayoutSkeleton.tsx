import { Skeleton, SkeletonStatus } from "./Skeleton";

interface Props {
  label?: string;
  tabCount?: number;
  className?: string;
}

/** Shared toolbar + panel + path sidebar used by track/cohort editors. */
export function EditorLayoutSkeleton({
  label = "Carregando…",
  tabCount = 3,
  className = "track-editor",
}: Props) {
  return (
    <SkeletonStatus label={label} className={className}>
      <div className="track-editor__toolbar">
        <Skeleton variant="text" width={88} height={16} />
        <div className="track-editor__toolbar-actions">
          <Skeleton variant="rect" width={120} height={24} />
          <Skeleton variant="text" width={100} height={14} />
        </div>
      </div>

      <div className="track-editor__layout">
        <div className="track-editor__main">
          <div className="card track-editor-panel">
            <div className="editor-layout-skeleton__tabs">
              {Array.from({ length: tabCount }).map((_, index) => (
                <Skeleton key={index} variant="text" width={72} height={16} />
              ))}
            </div>
            <div className="editor-layout-skeleton__body">
              <Skeleton variant="text" width="40%" height={14} />
              <Skeleton variant="rect" width="100%" height={44} />
              <Skeleton variant="rect" width="100%" height={44} />
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <Skeleton variant="text" width="70%" height={14} />
                <Skeleton variant="text" width="55%" height={14} />
                <Skeleton variant="text" width="62%" height={14} />
              </div>
              <Skeleton variant="rect" width={140} height={40} />
            </div>
          </div>
        </div>

        <aside className="track-editor__preview">
          <div className="card path-preview">
            <div className="editor-layout-skeleton__path">
              <Skeleton variant="text" width="50%" height={16} />
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="editor-layout-skeleton__path-block">
                  <Skeleton variant="text" width="45%" height={14} />
                  <Skeleton variant="rect" width="100%" height={36} />
                  <Skeleton variant="rect" width="100%" height={36} />
                </div>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </SkeletonStatus>
  );
}
