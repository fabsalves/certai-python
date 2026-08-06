import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

/** Initial auth bootstrap while the shell decides the route. */
export function AppBootSkeleton() {
  return (
    <SkeletonStatus label="Carregando…" className="app-boot-skeleton">
      <Skeleton variant="text" width={160} height={22} />
      <Skeleton variant="text" width={240} height={14} />
      <div className="app-boot-skeleton__cards">
        <Skeleton variant="rect" width="100%" height={88} />
        <Skeleton variant="rect" width="100%" height={88} />
      </div>
    </SkeletonStatus>
  );
}
