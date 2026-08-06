import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function CohortStudentsSkeleton() {
  return (
    <SkeletonStatus label="Carregando alunos…" className="cohort-students">
      <div className="cohort-students__toolbar">
        <Skeleton variant="text" width="55%" height={14} />
        <Skeleton variant="rect" width={140} height={36} />
      </div>

      <div className="cohort-students__controls">
        <Skeleton variant="rect" width="100%" height={40} />
        <div style={{ display: "flex", gap: 8 }}>
          <Skeleton variant="rect" width={72} height={32} />
          <Skeleton variant="rect" width={72} height={32} />
        </div>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
        {Array.from({ length: 5 }).map((_, index) => (
          <Skeleton key={index} variant="rect" width={84} height={28} />
        ))}
      </div>

      <div className="cohort-students__layout">
        <div className="cohort-students__list-col">
          <ul className="cohort-students__list">
            {Array.from({ length: 6 }).map((_, index) => (
              <li key={index} className="cohort-students-skeleton__row">
                <Skeleton variant="text" width="60%" height={16} />
                <Skeleton variant="rect" width={72} height={20} />
              </li>
            ))}
          </ul>
        </div>
        <div className="card cohort-students__detail">
          <div className="editor-layout-skeleton__body">
            <Skeleton variant="text" width="50%" height={18} />
            <Skeleton variant="text" width="70%" height={14} />
            <Skeleton variant="rect" width="100%" height={72} />
            <Skeleton variant="rect" width="100%" height={72} />
          </div>
        </div>
      </div>
    </SkeletonStatus>
  );
}
