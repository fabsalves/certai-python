import { PageHeader } from "../layout/PageHeader";
import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function TracksListSkeleton() {
  return (
    <SkeletonStatus label="Carregando trilhas…">
      <PageHeader
        title="Trilhas"
        description="Monte o percurso completo: trilha, módulos com nível e aulas em sequência."
        actions={<Skeleton variant="rect" width={120} height={40} />}
      />

      <div className="tracks-list">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="card tracks-list__item list-skeleton-card">
            <div className="tracks-list__head">
              <div style={{ flex: 1, minWidth: 0 }}>
                <Skeleton variant="text" width="58%" height={22} />
                <div style={{ marginTop: 8 }}>
                  <Skeleton variant="text" width="48%" height={14} />
                </div>
              </div>
              <Skeleton variant="rect" width={88} height={24} />
            </div>
            <div className="tracks-list__meta">
              <Skeleton variant="text" width="40%" height={13} />
            </div>
          </div>
        ))}
      </div>
    </SkeletonStatus>
  );
}
