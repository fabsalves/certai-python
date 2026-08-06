import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function StudentAssessmentsSkeleton() {
  return (
    <SkeletonStatus
      label="Carregando avaliações…"
      className="student-assessments-panel"
    >
      <header className="student-assessments-panel__head">
        <Skeleton variant="text" width="45%" height={20} />
        <div style={{ marginTop: 8 }}>
          <Skeleton variant="text" width="60%" height={14} />
        </div>
      </header>

      <div className="student-assessments-panel__tree">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="student-assessments-skeleton__card">
            <Skeleton variant="text" width="30%" height={12} />
            <div style={{ marginTop: 8 }}>
              <Skeleton variant="text" width="55%" height={16} />
            </div>
            <div style={{ marginTop: 12 }}>
              <Skeleton variant="rect" width="100%" height={56} />
            </div>
          </div>
        ))}
      </div>
    </SkeletonStatus>
  );
}
