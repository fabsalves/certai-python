import { Skeleton, SkeletonStatus } from "../ui/Skeleton";

export function LessonAssessmentDistSkeleton() {
  return (
    <SkeletonStatus
      label="Carregando avaliações da turma…"
      className="cohort-assessment-dist"
    >
      <Skeleton variant="text" width={160} height={14} />
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
        {Array.from({ length: 3 }).map((_, index) => (
          <div
            key={index}
            style={{ display: "flex", justifyContent: "space-between", gap: 12 }}
          >
            <Skeleton variant="text" width="45%" height={14} />
            <Skeleton variant="text" width={28} height={14} />
          </div>
        ))}
      </div>
    </SkeletonStatus>
  );
}
