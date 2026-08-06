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

      <section className="student-assessments-panel__hero" aria-hidden>
        <div className="student-assessments-panel__hero-top">
          <Skeleton variant="text" width={48} height={10} />
          <Skeleton variant="rect" width={72} height={20} />
        </div>
        <div style={{ marginTop: 8 }}>
          <Skeleton variant="text" width="70%" height={16} />
        </div>
        <div style={{ marginTop: 6 }}>
          <Skeleton variant="text" width={140} height={12} />
        </div>
        <div style={{ marginTop: 14 }}>
          <Skeleton variant="text" width={56} height={10} />
          <div style={{ marginTop: 6 }}>
            <Skeleton variant="text" width="100%" height={14} />
          </div>
          <div style={{ marginTop: 6 }}>
            <Skeleton variant="text" width="92%" height={14} />
          </div>
          <div style={{ marginTop: 6 }}>
            <Skeleton variant="text" width="80%" height={14} />
          </div>
        </div>
        <div style={{ marginTop: 12 }}>
          <Skeleton variant="text" width={56} height={10} />
          <div style={{ marginTop: 6 }}>
            <Skeleton variant="text" width="75%" height={14} />
          </div>
        </div>
      </section>

      <div className="student-assessments-panel__tree">
        {Array.from({ length: 2 }).map((_, index) => (
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
