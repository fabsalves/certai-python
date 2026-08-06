import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function PlaygroundPageSkeleton() {
  return (
    <SkeletonStatus
      label="Carregando playground…"
      className="playground-shell"
    >
      <div className="playground-stage">
        <div className="playground-stage__bar">
          <Skeleton variant="circle" width={36} height={36} />
        </div>
        <div className="playground-stage__body">
          <div className="playground-page-skeleton__stage">
            <Skeleton variant="text" width="40%" height={16} />
            <Skeleton variant="rect" width="100%" height={220} />
            <Skeleton variant="rect" width="70%" height={44} />
          </div>
        </div>
      </div>

      <aside className="playground-rail">
        <div className="playground-rail__tabs">
          <Skeleton variant="text" width={64} height={14} />
          <Skeleton variant="text" width={72} height={14} />
          <Skeleton variant="text" width={68} height={14} />
        </div>
        <div className="card path-preview">
          <div className="editor-layout-skeleton__path">
            <Skeleton variant="text" width="50%" height={16} />
            {Array.from({ length: 3 }).map((_, index) => (
              <div key={index} className="editor-layout-skeleton__path-block">
                <Skeleton variant="text" width="45%" height={14} />
                <Skeleton variant="rect" width="100%" height={36} />
              </div>
            ))}
          </div>
        </div>
      </aside>
    </SkeletonStatus>
  );
}
